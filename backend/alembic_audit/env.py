from logging.config import fileConfig
import sys
import os
from dotenv import load_dotenv

# Add backend directory to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import settings and Base
from src.config.settings import settings
from src.models.base import AuditBase

# Import all models to ensure they are registered with Base.metadata
import src.models.user
import src.models.provider
import src.models.patient
import src.models.appointment
import src.models.call_log
import src.models.sms_log
import src.models.audit_log

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = AuditBase.metadata

def get_url():
    url = settings.audit_database_url
    if url and url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    return url

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
