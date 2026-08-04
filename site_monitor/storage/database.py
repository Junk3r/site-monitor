from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from site_monitor.storage.models import Base


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_DATABASE_URL = "sqlite:///data/monitor.db"

SQLITE_PREFIX = "sqlite:///"


engine = None

# создаётся без bind — привязка приходит из configure(), поэтому
# `from ... import SessionLocal` остаётся валидным до настройки
SessionLocal = sessionmaker()


def resolve_url(database_url: str) -> str:
    """Относительный путь к SQLite считается от корня проекта, а не от
    текущей директории — иначе запуск из другой папки создаёт вторую БД."""

    if not database_url.startswith(SQLITE_PREFIX):
        return database_url


    raw = database_url[len(SQLITE_PREFIX):]

    if (
        not raw
        or raw.startswith("/")
        or raw.startswith(":")
        or raw.startswith("file:")
    ):
        return database_url


    path = Path(raw)

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    path.parent.mkdir(parents=True, exist_ok=True)

    return SQLITE_PREFIX + path.as_posix()


def configure(database_url: str = DEFAULT_DATABASE_URL):

    global engine

    engine = create_engine(
        resolve_url(database_url),
        echo=False,
    )

    SessionLocal.configure(bind=engine)

    return engine


def init_database(database_url: str | None = None):

    if engine is None or database_url is not None:
        configure(database_url or DEFAULT_DATABASE_URL)

    Base.metadata.create_all(engine)
