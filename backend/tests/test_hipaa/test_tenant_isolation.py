"""
Test Tenant Isolation (World Class)
Ensures that ContextVar works and the SQLAlchemy with_loader_criteria hook actually intercepts live queries.
"""
import pytest
import pytest_asyncio
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from src.core.tenant_context import set_tenant_id, get_tenant_id
from src.models.base import Base
from src.models.tenant import Tenant
from src.models.patient import Patient
# Note: The do_orm_execute hook is globally attached in src.db.engine
import src.db.engine

from src.config.settings import settings

test_engine = create_async_engine(settings.database_url, echo=False)
TestSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest_asyncio.fixture(autouse=True)
async def db_transaction():
    """Run tests in a transaction that is rolled back to isolate state."""
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        # Bind the session to the connection
        global TestSessionLocal
        TestSessionLocal = async_sessionmaker(bind=conn, expire_on_commit=False)
        yield
        await trans.rollback()


@pytest.mark.asyncio
async def test_real_cross_tenant_isolation():
    tenant1_id = uuid4()
    tenant2_id = uuid4()
    
    # 1. Insert data for both tenants
    # We will temporarily disable the tenant ID for raw inserts by setting it to None.
    set_tenant_id(None)
    
    async with TestSessionLocal() as session:
        t1 = Tenant(id=tenant1_id, name="Clinic 1", slug="clinic-1", security_officer_email="sec1@c1.com", owner_email="owner1@c1.com")
        t2 = Tenant(id=tenant2_id, name="Clinic 2", slug="clinic-2", security_officer_email="sec2@c2.com", owner_email="owner2@c2.com")
        session.add_all([t1, t2])
        await session.flush()
        
        # Add a patient for Tenant 1
        p1 = Patient(
            id=uuid4(),
            tenant_id=tenant1_id,
            phone_hash="hash1",
            row_hash="test1"
        )
        p1.full_name = "Alice Smith"
        p1.dob = "1990-01-01"
        p1.phone = "+1234567890"

        # Add a patient for Tenant 2
        p2 = Patient(
            id=uuid4(),
            tenant_id=tenant2_id,
            phone_hash="hash2",
            row_hash="test2"
        )
        p2.full_name = "Bob Jones"
        p2.dob = "1980-01-01"
        p2.phone = "+1987654321"

        session.add_all([p1, p2])
        await session.commit()
        
    # 2. Test Tenant 1 Context
    set_tenant_id(tenant1_id)
    async with TestSessionLocal() as session:
        result = await session.execute(select(Patient))
        patients = result.scalars().all()
        assert len(patients) == 1
        assert patients[0].full_name == "Alice Smith"
        assert patients[0].tenant_id == tenant1_id

    # 3. Test Tenant 2 Context
    set_tenant_id(tenant2_id)
    async with TestSessionLocal() as session:
        result = await session.execute(select(Patient))
        patients = result.scalars().all()
        assert len(patients) == 1
        assert patients[0].full_name == "Bob Jones"
        assert patients[0].tenant_id == tenant2_id
