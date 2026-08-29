import asyncio
from uuid import uuid4
from sqlalchemy import text
import hashlib
from src.services.audit_service import audit_service
from src.core.tenant_context import set_tenant_id
from tests.test_hipaa.test_audit_logging import audit_test_engine, AuditTestSessionLocal, AuditBase
import src.services.audit_service as audit_module

async def run():
    async with audit_test_engine.begin() as conn:
        await conn.run_sync(AuditBase.metadata.create_all)
    
    audit_module.audit_session_maker = AuditTestSessionLocal
    
    tenant_id = uuid4()
    set_tenant_id(tenant_id)
    actor_id = uuid4()
    
    await audit_service.log('READ', 'patients', actor_id, 'staff')
    
    async with AuditTestSessionLocal() as session:
        rows = await session.execute(text("SELECT action, actor_id, previous_hash, created_at, row_hash FROM audit_logs"))
        for r in rows.fetchall():
            action, actor_id_db, prev_hash, created_at, row_hash = r
            print(f'DB ROW: action={action}, actor={actor_id_db}, prev={prev_hash}, created={created_at}, hash={row_hash}')
            
            import datetime
            if isinstance(created_at, str):
                created_at = datetime.datetime.fromisoformat(created_at)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=datetime.timezone.utc)
            timestamp = created_at.isoformat()
            
            actor_id_str = str(actor_id_db) if actor_id_db else 'SYSTEM'
            if isinstance(actor_id_db, bytes):
                import uuid
                actor_id_str = str(uuid.UUID(bytes=actor_id_db))
                
            hash_input = f"{action}:{actor_id_str}:{prev_hash}:{timestamp}"
            computed_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
            print(f"VERIFY INPUT: {hash_input}")
            print(f"COMPUTED: {computed_hash}")
            print(f"STORED:   {row_hash}")
            print(f"MATCH:    {computed_hash == row_hash}")
            
    print('Valid:', await audit_service.verify_chain(tenant_id))
    
asyncio.run(run())
