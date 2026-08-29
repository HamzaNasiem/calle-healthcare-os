from datetime import UTC, datetime
from fastapi import APIRouter
from sqlalchemy import text

from src.config.settings import settings
from src.db.engine import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "calle_configured": bool(settings.calle_api_key),
        "calle_dry_run": settings.calle_dry_run,
        "timestamp": datetime.now(UTC).isoformat(),
        "message": "Bytelytic OS API is online"
    }
