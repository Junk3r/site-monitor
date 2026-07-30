from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from site_monitor.storage.models import Base


DATABASE_URL = "sqlite:///data/monitor.db"


engine = create_engine(
    DATABASE_URL,
    echo=False
)


SessionLocal = sessionmaker(
    bind=engine
)


def init_database():

    Base.metadata.create_all(
        engine
    )