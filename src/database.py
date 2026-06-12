"""Database backend — auto-selects SQLite (dev) or PostgreSQL (production) via DATABASE_URL.

Environment:
  DATABASE_URL=sqlite:///data/gsm_os.db    → SQLite (default for development)
  DATABASE_URL=postgresql://user:pass@host/db → PostgreSQL (production)
"""

import os
import structlog
from .database_backend import DatabaseBackend
from .config import settings

logger = structlog.get_logger()


def _create_backend() -> DatabaseBackend:
    """Factory: returns the appropriate backend based on DATABASE_URL."""
    dsn = os.environ.get("DATABASE_URL", "sqlite:///data/gsm_os.db")

    if dsn.startswith("postgresql://") or dsn.startswith("postgres://"):
        from .database_postgres import PostgresBackend
        logger.info("Using PostgreSQL backend", dsn=dsn.split("@")[-1] if "@" in dsn else "configured")
        return PostgresBackend(dsn)

    # Default: SQLite
    from .database_sqlite import SQLiteBackend
    db_path = dsn.replace("sqlite:///", "", 1) if dsn.startswith("sqlite:///") else dsn.replace("sqlite://", "", 1)
    if not db_path:
        db_path = "data/gsm_os.db"
    logger.info("Using SQLite backend", path=db_path)
    return SQLiteBackend(db_path)


db: DatabaseBackend = _create_backend()
