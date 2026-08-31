import asyncio
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import engine
from src.api.v1.prior_auth import _fetch_patient_name

async def main():
    async with AsyncSession(engine) as db:
        pid = uuid.UUID('a7c19370-2505-4604-a01f-f78a8a3b96e4')
        print(f"Calling _fetch_patient_name for {pid}")
        name = await _fetch_patient_name(db, pid)
        print(f"Result: {name}")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
