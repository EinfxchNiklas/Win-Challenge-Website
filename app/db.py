import os

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./winchallenge.db"


def _normalize_url(url: str) -> str:
    # Neon liefert postgres(ql)://; SQLAlchemy braucht den expliziten psycopg-Treiber im Schema
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql+psycopg://") and "sslmode=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"
    return url


_engine_url = _normalize_url(DATABASE_URL)
_connect_args = {"check_same_thread": False} if _engine_url.startswith("sqlite") else {}
# pre_ping fängt von Neon serverseitig geschlossene Idle-Connections ab, statt mit ihnen zu crashen
engine = create_engine(_engine_url, connect_args=_connect_args, pool_pre_ping=True, pool_recycle=300)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_position_column()
    _ensure_mode_column()


def _ensure_position_column() -> None:
    # Nachträglich eingeführtes Feld: bei älteren Datenbanken per ALTER TABLE ergänzen
    inspector = inspect(engine)
    if "game" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("game")}
    if "position" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE game ADD COLUMN position INTEGER DEFAULT 0"))
        rows = conn.execute(text("SELECT id FROM game ORDER BY created_at")).fetchall()
        for index, row in enumerate(rows):
            conn.execute(
                text("UPDATE game SET position = :position WHERE id = :id"),
                {"position": index, "id": row[0]},
            )


def _ensure_mode_column() -> None:
    # Nachträglich eingeführtes Feld: bei älteren Datenbanken per ALTER TABLE ergänzen
    inspector = inspect(engine)
    if "game" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("game")}
    if "mode" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE game ADD COLUMN mode TEXT DEFAULT 'total'"))


def get_session() -> Session:
    return Session(engine)
