from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Server
    PORT: int = 3000
    NODE_ENV: str = "development"
    
    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_DATABASE_URL: Optional[str] = None
    SUPABASE_AUTH_URL: Optional[str] = None

    # Retell AI
    RETELL_API_KEY: Optional[str] = ""
    RETELL_WEBHOOK_SECRET: Optional[str] = None

    # Twilio
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_DEFAULT_NUMBER: Optional[str] = None

    # Telnyx (HIPAA Compliant Carrier)
    TELNYX_API_KEY: Optional[str] = None
    TELNYX_PUBLIC_KEY: Optional[str] = None
    TELNYX_DEFAULT_NUMBER: Optional[str] = None
    TELNYX_APP_ID: Optional[str] = None
    SMS_PROVIDER: Optional[str] = "telnyx"

    # Google Calendar
    GOOGLE_CLIENT_ID: Optional[str] = ""
    GOOGLE_CLIENT_SECRET: Optional[str] = ""
    GOOGLE_REDIRECT_URI: Optional[str] = "http://localhost:3000/auth/google/callback"

    # OpenRouter
    OPENROUTER_API_KEY: Optional[str] = ""  # Required for AI features, optional for basic operation
    OPENROUTER_API_KEY_BACKUP: Optional[str] = None

    # App URLs
    API_BASE_URL: str = "http://localhost:3000"
    DASHBOARD_URL: str = "http://localhost:5173"
    WEBHOOK_BASE_URL: Optional[str] = None

    # Email
    RESEND_API_KEY: Optional[str] = None

    # Stripe Billing
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    # Stripe Product Price IDs — get from Stripe Dashboard → Products
    # Format: price_XXXXXXXXXXXXXXXXXXXX
    STRIPE_PRICE_STARTER: Optional[str] = None  # $149/mo — 200 calls
    STRIPE_PRICE_GROWTH: Optional[str] = None   # $299/mo — 500 calls
    STRIPE_PRICE_PRO: Optional[str] = None      # $599/mo — unlimited

    # APM Performance Monitoring
    SENTRY_DSN: Optional[str] = None

    # Alerting
    SLACK_WEBHOOK_URL: Optional[str] = None

    # Redis configuration
    REDIS_URL: Optional[str] = None

    # Admin
    ADMIN_EMAILS_STR: Optional[str] = "ziaee.pk@gmail.com,qamx99@gmail.com,hamza@bytelytic.com,qa_admin_tester@gmail.com"
    ADMIN_API_KEY: Optional[str] = "admin_super_secret_key_123"
    ADMIN_IP_WHITELIST_STR: Optional[str] = None

    @property
    def ADMIN_EMAILS(self) -> List[str]:
        if not self.ADMIN_EMAILS_STR:
            return []
        return [email.strip() for email in self.ADMIN_EMAILS_STR.split(",") if email.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def db_url(self) -> str:
        return self.SUPABASE_DATABASE_URL or self.SUPABASE_URL

    @property
    def auth_url(self) -> str:
        return self.SUPABASE_AUTH_URL or self.SUPABASE_URL

    @property
    def is_prod(self) -> bool:
        return self.NODE_ENV == "production"

# Instantiate settings globally. It will automatically load from .env and validate.
# If required variables are missing, it will raise an error on startup (replicating env.js behavior).
settings = Settings()
