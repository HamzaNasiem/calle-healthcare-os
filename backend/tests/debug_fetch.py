import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.api.v1.prior_auth import _fetch_patient_name
from sqlalchemy import text
import traceback

async def main():
    try:
        engine = create_async_engine("postgresql+asyncpg://calle_user:L9zYPT9GzEEcPOV2grP3TtDrX9fXmKwV@dpg-da9dirm7bikc7390tqrg-a.oregon-postgres.render.com:5432/bytelytic_clinic_db?sslmode=require", echo=True)
        SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with SessionLocal() as db:
            patient_id = uuid.UUID('a7c19370-2505-4604-a01f-f78a8a3b96e4')
            
            # try direct sql
            try:
                res = await db.execute(
                    text("SELECT name FROM patients WHERE id = :pid"),
                    {"pid": patient_id}
                )
                print("Direct SQL:", res.fetchone())
            except Exception as e:
                print("Direct SQL failed:", e)
            
            name = await _fetch_patient_name(db, patient_id)
            print(f"Fetch patient name returned: {name}")
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
