import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.db.engine import engine

async def main():
    async with AsyncSession(engine) as db:
        try:
            res = await db.execute(text("SELECT name FROM patients WHERE CAST(id AS text) = :pid"), {"pid": 'a7c19370-2505-4604-a01f-f78a8a3b96e4'})
            print("CAST text:", res.fetchone())
        except Exception as e:
            print("CAST text err:", e)
        
        try:
            res2 = await db.execute(text("SELECT name FROM patients WHERE id::text = :pid"), {"pid": 'a7c19370-2505-4604-a01f-f78a8a3b96e4'})
            print("id::text:", res2.fetchone())
        except Exception as e:
            print("id::text err:", e)

if __name__ == '__main__':
    asyncio.run(main())
