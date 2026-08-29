import asyncio
from src.db.engine import engine
from sqlalchemy import text

async def run():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
        tables = [r[0] for r in res]
        print(f"Tables: {tables}")
        if 'alembic_version' in tables:
            await conn.execute(text('DROP TABLE alembic_version;'))
            print("Dropped alembic_version")

asyncio.run(run())
