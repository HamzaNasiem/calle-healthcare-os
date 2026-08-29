"""
Test Audit Logging (World Class)
Tests the actual hashing logic and chain breakage detection of the Audit Service.
"""
import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

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
async def test_audit_log_hash_chain():
    """Test that the hash is computed correctly and chain breaks when modified."""
    tenant_id = uuid4()
    set_tenant_id(tenant_id)
    actor_id = uuid4()
    
    # 1. Log 3 actions
    await audit_service.log(action="READ", target_table="patients", actor_id=actor_id, actor_role="staff")
    await audit_service.log(action="UPDATE", target_table="patients", actor_id=actor_id, actor_role="staff")
    await audit_service.log(action="DELETE", target_table="patients", actor_id=actor_id, actor_role="staff")
    
    # 2. Verify chain is valid
    is_valid = await audit_service.verify_chain(tenant_id)
    assert is_valid[0] is True, "Chain should be valid for unaltered logs."
    
    # 3. Simulate an attacker modifying the middle log (Sequence Number 2)
    async with AuditTestSessionLocal() as session:
        # Get the sequence number of the middle log
        result = await session.execute(
            text("SELECT sequence_number FROM audit_logs WHERE tenant_id = :tenant_id ORDER BY sequence_number ASC OFFSET 1 LIMIT 1"),
            {"tenant_id": str(tenant_id)}
        )
        middle_seq = result.scalar()
        
        # Change the action from UPDATE to READ
        result = await session.execute(
            text("UPDATE audit_logs SET action = 'READ' WHERE sequence_number = :seq AND tenant_id = :tenant_id"),
            {"seq": middle_seq, "tenant_id": str(tenant_id)}
        )
        assert result.rowcount == 1, f"Expected 1 row updated, got {result.rowcount}"
        await session.commit()
        
    # 4. Verify chain detects the breakage!
    is_valid_after_hack = await audit_service.verify_chain(tenant_id)
    assert is_valid_after_hack[0] is False, "Chain MUST break if a row is modified."
