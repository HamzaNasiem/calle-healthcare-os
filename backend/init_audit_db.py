import asyncio
import os
import sys

from src.db.audit_engine import audit_engine
from src.models.audit_log import AuditBase

async def init():
    async with audit_engine.begin() as conn:
        await conn.run_sync(AuditBase.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(init())
