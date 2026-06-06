"""Database initialisation — creates all tables on first run."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base

DB_PATH = Path(__file__).parent / "nebius_bench.db"


def get_engine(db_path: Path | None = None) -> Engine:
    path = db_path or DB_PATH
    return create_engine(f"sqlite:///{path}", echo=False, connect_args={"check_same_thread": False})


def init_db(db_path: Path | None = None) -> Engine:
    """Create all tables and return the engine.  Safe to call multiple times."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session_factory(db_path: Path | None = None) -> sessionmaker[Session]:
    engine = init_db(db_path)
    return sessionmaker(bind=engine, expire_on_commit=False)
