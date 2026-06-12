"""Alembic environment configuration — auto-detects SQLite or PostgreSQL."""

import os
import sys
from logging.config import fileConfig

from alembic import context

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import metadata for autogenerate support
from src.database import db  # noqa: E402

# Use DATABASE_URL for migration target if provided
database_url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine
    connectable = create_engine(database_url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
