from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Adjust path to import src settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.config import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# Dynamically construct database connection URL
import urllib.parse

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    # Resolve ref_name from SUPABASE_URL (e.g. https://aabbhuzlzjkosqmvhysm.supabase.co -> aabbhuzlzjkosqmvhysm)
    ref_name = settings.SUPABASE_URL.replace("https://", "").replace("http://", "").split(".")[0]
    db_host = "aws-0-ap-northeast-1.pooler.supabase.com"
    db_user = f"postgres.{ref_name}"
    db_password = os.environ.get("SUPABASE_DB_PASSWORD", "Bytelytic@2025")
    encoded_password = urllib.parse.quote_plus(db_password)
    # Enforce transaction pooler (port 6543) and sslmode=require
    database_url = f"postgresql://{db_user}:{encoded_password}@{db_host}:6543/postgres?sslmode=require"

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url
    
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

