"""SQLAlchemy engine and session management."""
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import config

_engine = None
_SessionLocal = None


def _build_engine(url):
    engine = create_engine(url, future=True, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def configure(url=None):
    """(Re)configure the engine. Used by tests to point at a temp database."""
    global _engine, _SessionLocal
    _engine = _build_engine(url or config.DATABASE_URL)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_engine():
    if _engine is None:
        configure()
    return _engine


@contextmanager
def get_session():
    """Transactional scope: commit on success, rollback on any error."""
    if _SessionLocal is None:
        configure()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
