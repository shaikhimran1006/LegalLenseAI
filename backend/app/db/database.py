"""SQLAlchemy setup. Uses SQLite by default (zero-config demo) and PostgreSQL
when DATABASE_URL is provided."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


class Base(DeclarativeBase):
    pass


def _build_engine():
    settings = get_settings()
    url = settings.database_url
    if url:
        return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    db_path = DATA_DIR / "legallens.db"
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    # Import models so they register on Base.metadata.
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()