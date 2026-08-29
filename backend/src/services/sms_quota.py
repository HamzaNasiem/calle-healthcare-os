from datetime import UTC, datetime

from sqlalchemy import func, select

from src.core.logger import log
from src.db.engine import async_session_maker
from src.models.sms_log import SmsLog


class SmsQuotaManager:
    """
    Prevents SMS Toll Fraud (Denial of Wallet).
    Ensures a single phone number cannot be spammed with SMS messages,
    capping at a strict daily limit.
    """
    MAX_SMS_PER_PHONE_PER_DAY = 5

    @classmethod
    async def check_quota(cls, phone: str, tenant_id: str) -> bool:
        """
        Returns True if the quota is healthy, False if exceeded.
        """
        try:
            now = datetime.now(UTC)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            async with async_session_maker() as session:
                stmt = select(func.count(SmsLog.id)).where(
                    SmsLog.to_number == phone,
                    SmsLog.tenant_id == tenant_id,
                    SmsLog.created_at >= start_of_day
                )
                result = await session.execute(stmt)
                count = result.scalar() or 0
                
                if count >= cls.MAX_SMS_PER_PHONE_PER_DAY:
                    log.warning(f"[SECURITY] SMS Quota exceeded for phone {phone} on tenant {tenant_id}. Count: {count}")
                    return False
                    
            return True
        except Exception as e:
            log.error(f"Error checking SMS quota for {phone}: {str(e)}")
            # Fail closed to protect the wallet
            return False

sms_quota = SmsQuotaManager()
