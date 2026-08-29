"""
Database Engine
Configures the asyncpg engine and session factory for the main application database.
Also attaches the auto-tenant-filter ORM hook required for HIPAA isolation.
"""
import hashlib
from collections.abc import AsyncGenerator
import ssl

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapper, Session, with_loader_criteria

from src.config.settings import settings
from src.models.base import IntegrityMixin, SoftDeleteMixin

connect_args = {
    "statement_cache_size": 0,
    "prepared_statement_cache_size": 0,
    "prepared_statement_name_func": lambda: "",
}
if settings.DATABASE_SSL:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_ctx

# Create Async Engine
engine = create_async_engine(
    settings.database_url,
    pool_size=5,          # Lower base pool for auto-scaling safety
    max_overflow=5,       # Cap total connections per container to 10
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=10,      # Fail fast if DB is overwhelmed (Load shedding)
    echo=False,  # Never True in production to avoid PHI leakage in logs
    connect_args=connect_args,
)

# Create session maker with expire_on_commit=False (CRITICAL for async SQLAlchemy)
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# 🛡️ SOFT DELETE AUTO-FILTER 🛡️
@event.listens_for(Session, "do_orm_execute")
def _add_soft_delete_filter(execute_state):
    """
    Safely injects WHERE is_deleted = False at the ORM level.
    """
    if execute_state.is_select or execute_state.is_update or execute_state.is_delete:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.is_deleted == False,
                include_aliases=True
            )
        )
        
        # Add Tenant Isolation Filter
        from src.core.tenant_context import get_tenant_id
        from src.models.base import TenantMixin
        try:
            current_tenant = get_tenant_id()
            if current_tenant:
                execute_state.statement = execute_state.statement.options(
                    with_loader_criteria(
                        TenantMixin,
                        lambda cls: cls.tenant_id == current_tenant,
                        include_aliases=True
                    )
                )
        except RuntimeError:
            # Context var not set, skip filter (e.g. for system-level queries)
            pass

# 🛡️ ROW HASH GENERATOR (HIPAA SAFEGUARD) 🛡️
@event.listens_for(Mapper, "before_insert")
@event.listens_for(Mapper, "before_update")
def receive_before_insert_update(mapper, connection, target):
    if isinstance(target, IntegrityMixin):
        state = target.__dict__.copy()
        state.pop("_sa_instance_state", None)
        state.pop("row_hash", None)
        
        # Sort keys for consistent hash
        stable_repr = "".join(f"{k}={v}" for k, v in sorted(state.items()))
        target.row_hash = hashlib.sha256(stable_repr.encode('utf-8')).hexdigest()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to provide a database session for FastAPI endpoints."""
    async with async_session_maker() as session:
        yield session
