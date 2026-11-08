"""Gestión de conexión a la base de datos (motor, sesiones e inicialización)."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import database_url
from src.database.models import Base

_ENGINES: dict[str, Engine] = {}


def _enable_sqlite_pragmas(dbapi_connection, _record) -> None:
    """SQLite no aplica llaves foráneas por defecto: se activan en cada conexión."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine(url: str | None = None) -> Engine:
    """Devuelve (y reutiliza) un motor SQLAlchemy para la URL indicada."""
    url = url or database_url()
    if url in _ENGINES:
        return _ENGINES[url]
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, future=True, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_pragmas)
    _ENGINES[url] = engine
    return engine


def dispose_engine(url: str | None = None) -> None:
    url = url or database_url()
    engine = _ENGINES.pop(url, None)
    if engine is not None:
        engine.dispose()


def init_db(engine: Engine | None = None, drop: bool = False) -> Engine:
    """Crea las tablas (idempotente). ``drop=True`` reconstruye el esquema."""
    engine = engine or get_engine()
    if drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Sesión transaccional: confirma al finalizar o revierte ante cualquier excepción."""
    factory = sessionmaker(bind=engine or get_engine(), expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_connection(engine: Engine | None = None) -> bool:
    engine = engine or get_engine()
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar() == 1


def table_names(engine: Engine | None = None) -> list[str]:
    return sorted(inspect(engine or get_engine()).get_table_names())


def is_populated(engine: Engine | None = None) -> bool:
    engine = engine or get_engine()
    if "ventas" not in table_names(engine):
        return False
    with engine.connect() as conn:
        return (conn.execute(text("SELECT COUNT(*) FROM ventas")).scalar() or 0) > 0
