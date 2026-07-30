from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    Integer,
)

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class Base(DeclarativeBase):
    pass


class MonitoredPage(Base):
    __tablename__ = "monitored_pages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    url: Mapped[str] = mapped_column(
        String,
        unique=True
    )

    title: Mapped[str] = mapped_column(
        String
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )