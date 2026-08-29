import asyncio
import os
import sys

from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.database import async_engine
from src.core.logger import log


async def apply_rls():
    migration_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations", "rls_policies.sql")
    if not os.path.exists(migration_file):
        log.error(f"Migration file not found: {migration_file}")
        return

    with open(migration_file) as f:
        sql = f.read()

    log.info("Applying Row Level Security (RLS) policies to database...")
    async with async_engine.begin() as conn:
        try:
            await conn.execute(text(sql))
            log.info("RLS policies applied successfully.")
        except Exception as e:
            log.error(f"Error executing RLS migration SQL script: {e}")
            raise e

if __name__ == "__main__":
    asyncio.run(apply_rls())
