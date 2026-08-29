from dotenv import load_dotenv

load_dotenv()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    PORT: int = 8000
    NODE_ENV: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/bytelytic_clinic_db"
    audit_database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/bytelytic_clinic_db"
    DATABASE_URL: str | None = None # alias
    AUDIT_DATABASE_URL: str | None = None # alias
    DATABASE_SSL: bool = False
    AUDIT_DATABASE_SSL: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.DATABASE_URL and not getattr(self, "database_url", None):
            self.database_url = self.DATABASE_URL
        if self.AUDIT_DATABASE_URL and not getattr(self, "audit_database_url", None):
            self.audit_database_url = self.AUDIT_DATABASE_URL

        # Coerce scheme to postgresql+asyncpg and check for sslmode=require
        if self.database_url:
            if "sslmode=require" in self.database_url:
                self.DATABASE_SSL = True
                # Strip sslmode=require and clean up query string
                url_clean = self.database_url.replace("sslmode=require", "")
                url_clean = url_clean.replace("?&", "?").replace("&&", "&").rstrip("?").rstrip("&")
                self.database_url = url_clean
                
            if self.database_url.startswith("postgresql://"):
                self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif self.database_url.startswith("postgres://"):
                self.database_url = self.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
                
        if self.audit_database_url:
            if "sslmode=require" in self.audit_database_url:
                self.AUDIT_DATABASE_SSL = True
                url_clean = self.audit_database_url.replace("sslmode=require", "")
                url_clean = url_clean.replace("?&", "?").replace("&&", "&").rstrip("?").rstrip("&")
                self.audit_database_url = url_clean
                
            if self.audit_database_url.startswith("postgresql://"):
                self.audit_database_url = self.audit_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif self.audit_database_url.startswith("postgres://"):
                self.audit_database_url = self.audit_database_url.replace("postgres://", "postgresql+asyncpg://", 1)
            
        self.DATABASE_URL = self.database_url
        self.AUDIT_DATABASE_URL = self.audit_database_url

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_auth_token: str | None = None
    redis_ssl: bool = False
    
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_USE_TLS: bool = False
    # Direct Redis URL (optional — if set, overrides host/port construction)
    REDIS_URL: str | None = None

    @property
    def redis_url(self) -> str | None:
        """Build Redis URL from components if REDIS_URL env var not set directly."""
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_PASSWORD:
            scheme = "rediss" if self.REDIS_USE_TLS else "redis"
            return f"{scheme}://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # JWT
    jwt_private_key: str = "-----BEGIN RSA PRIVATE KEY-----\nMIIEogIBAAKCAQEAxy0VIwi6LqzlI5jJ6vrFU5ZLF7ymUMirsQjki4m1m+xVha9x\nU+hdO8IDCL3UnQyqrcK9zZ1Mn8IKMn9Sl5tzqCb7lPHQnj5OQUbw8macb7W5zlHY\nvDVmhYFH3EVpJzF/pWePxmVDJltQ5CdOuzEFO9e30YRfb5bnFuCg28Q1bjKJ6GNr\nkbqs/XYCL6MZjn8F0dKnMBg/gwhrt9QqwdgW/LZOIVKDuEhqch4iePAXY+Hd+Vgv\nWjGKA/fQmybYWEHVkSuIFS+0nt3DDvXX5PTP20m9G7FpbdKuiUpGLg4E0hSYzo82\nh5n3CjBt3ir7gRBBtbnat5/J2Lc3UfK5DWPitwIDAQABAoIBAAZ4A94569YVPnHs\nBe7QSzVeRb0VHu+zvMPIrqeLhu7z+4kWfB9GBjUpJXEUvUGGhkqTbxes+q6bnjoq\noXOUFGsLLROW0Pg6vM7o721oAL+uDsVRKjFeqKBAZSWVyYcA2Az2spg2dLpbr+Jh\nFnEE9A8QAAPZgUH+DC5ViFPq6PNVuRZ2a6S4/VdJffHXDQc6N/Qn6bMNXwCNgf/N\nDgon+oa+qhXJLYpR0qixtuyP3cCuLqqVzLHw3mlya20yW9HYdEcXEaEACK2C2Mo2\nyFNu5QE4IqLkyneIWsNkHRzeqnzO9RTcixki5L+H1UCN4uWjUGy4FomQN9fJWgjB\n78Dy2dUCgYEA/2ZjXq2S4j2ymADXrP2+/5g9Qw/iIwCjoqTTgf5Ioh7nX7f7Aqfl\nlXfOPrQ6bfE4yOY5FzOPRaWqwsTbpdwDUnbq2cEAUbXIENSH1RRNSS+Quk5SmGID\nGz81HSePTGPa7keC95WHrQ0Q2oXpcYa8ZIMdJHutegGd0e9kdGE1CcUCgYEAx6Tg\n0684M5fpwPrG/WZx0038XJzs60RU9p7QFpuB52YspN7vykAHycpWq7+QKMAvFZVw\n2I7XoCiPOBlPtJh5q96dr3aQPpUxFQZX0OBDaBuekYCGZyrc1HKRs7OX/qw7e8No\n3EzwNKZG3uOx/+bwNfRuA+l4EO/pfS+QT8BgTksCgYBLF4qd+sDWHjfVc2H2bgDr\nW5KflhryGa0DFB1P+jjW2elDfm+h/0WEZd5RF2KakrMUdoRQqwsz+hqz+3dtU7vy\nUh6I+bMjUyRItoRdhQOYQhD2hjLItQCe0T3HnasHVdC4AHSkYOWsXswWxAq4I1pe\n3yIBaQ+/cJw7bnyFr1MN1QKBgGPqOXbXx3nSunMRTst9HNRSwE0dYFjyTs9KdfwK\ngb3sXcV5qWqAFyW/dRbpfV1XqXjU3LAU9Qc7pUm/KSvJ74K7nBE3dkNL6U+LaCGq\nSzHsOLS7LQiu4+wTFqZn6FbVncN37Z/rhX/kA64DKI9Y5bkrBnBAxQ089I7pYgD3\n13r3AoGAce0swkARGukaXCGCGUH5WvBY7GsgchNj7fHrjp5ESsJxgG/8oc+Tix+8\nsdA9MeGKUh923B393CnKRl5THj9/tt9jWnBB0X8jcG45F1y4QaETHtY6xPPNnAYF\nGCq0YHvuWAsyBA2NvhwC/umX/jv9u9FwVdlyOc8vpsSNJgysfrE=\n"
    jwt_public_key: str = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxy0VIwi6LqzlI5jJ6vrF\nU5ZLF7ymUMirsQjki4m1m+xVha9xU+hdO8IDCL3UnQyqrcK9zZ1Mn8IKMn9Sl5tz\nqCb7lPHQnj5OQUbw8macb7W5zlHYvDVmhYFH3EVpJzF/pWePxmVDJltQ5CdOuzEF\nO9e30YRfb5bnFuCg28Q1bjKJ6GNrkbqs/XYCL6MZjn8F0dKnMBg/gwhrt9QqwdgW\n/LZOIVKDuEhqch4iePAXY+Hd+VgvWjGKA/fQmybYWEHVkSuIFS+0nt3DDvXX5PTP\n20m9G7FpbdKuiUpGLg4E0hSYzo82h5n3CjBt3ir7gRBBtbnat5/J2Lc3UfK5DWPi\ntwIDAQAB\n-----END PUBLIC KEY-----\n"
    jwt_access_token_expire_minutes: int = 3
    jwt_refresh_token_expire_days: int = 7

    # Encryption — HIPAA: Key must be set via ENCRYPTION_KEY env var, never hardcoded
    # Generate: python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
    encryption_mode: str = "local"
    local_kms_key_base64: str = ""  # MUST be set via ENCRYPTION_KEY env var in production
    ENCRYPTION_KEY: str = ""        # Primary env var — maps to local_kms_key_base64
    kms_cmk_arn: str | None = None


    # Retell AI
    retell_api_key: str = ""
    RETELL_API_KEY: str = ""
    retell_agent_id: str = ""
    RETELL_AGENT_ID: str = ""
    retell_webhook_secret: str = ""
    RETELL_WEBHOOK_SECRET: str = ""

    # Telnyx
    telnyx_api_key: str = ""
    TELNYX_API_KEY: str = ""
    telnyx_public_key: str = ""
    TELNYX_PUBLIC_KEY: str = ""
    telnyx_app_id: str = ""
    TELNYX_APP_ID: str = ""

    # LLM
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # CALL-E
    calle_api_key: str | None = None
    CALLE_API_KEY: str | None = None          # uppercase alias from env
    calle_base_url: str = "https://api.heycall-e.com"
    CALLE_BASE_URL: str = "https://api.heycall-e.com"
    calle_webhook_secret: str | None = None
    calle_dry_run: bool = False               # real calls by default
    CALLE_DRY_RUN: bool = False
    calle_call_hour_start: int = 8
    calle_call_hour_end: int = 20
    calle_max_retries: int = 2

    @property
    def calle_key(self) -> str | None:
        """Return CALLE API key from either casing."""
        return self.CALLE_API_KEY or self.calle_api_key

    # Monitoring
    SENTRY_DSN: str | None = None

    # App URLs
    API_BASE_URL: str | None = "http://localhost:8000"
    DASHBOARD_URL: str | None = "http://localhost:5173"
    frontend_url: str | None = "http://localhost:5173"

    # Dedicated Single-Clinic Mode
    DEDICATED_CLINIC_MODE: bool = True
    DEFAULT_CLINIC_ID: str | None = None
    CLINIC_TIER: int = 1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "production" or self.NODE_ENV == "production"
        
    @property
    def calle_configured(self) -> bool:
        return bool(self.CALLE_API_KEY or self.calle_api_key)

# Instantiate settings globally.
settings = Settings()
