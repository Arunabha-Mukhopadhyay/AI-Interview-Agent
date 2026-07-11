"""
db/init_db.py
Run this once to create all tables in PostgreSQL.

Usage:
    python -m db.init_db
"""
from db.session import engine, Base
from db import models  # noqa: F401 — import models so Base knows about them
from core.logging import get_logger

logger = get_logger(__name__)


def init_db():
    logger.info("Creating all tables in PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    logger.info("Done. Tables created (or already existed).")


if __name__ == "__main__":
    init_db()
