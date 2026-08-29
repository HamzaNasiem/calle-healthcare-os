import asyncio
from src.db.engine import engine
from sqlalchemy import text

async def run():
    async with engine.begin() as conn:
        await conn.execute(text('DROP TABLE IF EXISTS alembic_version;'))
    print('Done')

asyncio.run(run())
