from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    Integer,
    Text,
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

    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
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