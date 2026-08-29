"""
Test Audit Logging
Verifies that the audit service can log basic events correctly.
"""
import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.models.base import AuditBase
from src.services.audit_service import audit_service
from src.core.tenant_context import set_tenant_id
from src.config.settings import settings

audit_test_engine = create_async_engine(settings.audit_database_url, echo=False)
AuditTestSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=audit_test_engine)

@pytest_asyncio.fixture(autouse=True)
async def setup_audit_db():
    async with audit_test_engine.begin() as conn:
        await conn.run_sync(AuditBase.metadata.create_all)
        
    async with audit_test_engine.connect() as conn:
        trans = await conn.begin()
        global AuditTestSessionLocal
        AuditTestSessionLocal = async_sessionmaker(bind=conn, expire_on_commit=False)
        
        from unittest.mock import patch
        with patch("src.services.audit_service.audit_session_maker", new=AuditTestSessionLocal):
            yield
            
        await trans.rollback()

@pytest.mark.asyncio
async def test_audit_log_creation():
    """Test that an audit log can be created successfully."""
    tenant_id = uuid4()
    set_tenant_id(tenant_id)
    actor_id = uuid4()
    
    # Log an action
    await audit_service.log(
        action="LOGIN",
        target_table="users",
        actor_id=actor_id,
        actor_role="staff"
    )
    
    # Verify chain is valid (meaning the log was inserted and hashed correctly)
    is_valid = await audit_service.verify_chain(tenant_id)
    assert is_valid[0] is True, "Audit log creation failed or chain invalid"
