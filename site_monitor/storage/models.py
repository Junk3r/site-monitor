from datetime import datetime, timezone

from sqlalchemy import (
    String,
    DateTime,
    Float,
    Integer,
    Text,
)

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


def utcnow() -> datetime:

    return datetime.now(timezone.utc)


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
        default=utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow
    )


class Opportunity(Base):
    """Найденная вакансия. Ключ дедупликации — fingerprint: одна вакансия
    попадает сюда один раз и оповещается один раз, сколько бы раз она
    ни встретилась в последующих сканах."""

    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    fingerprint: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True
    )

    site: Mapped[str] = mapped_column(
        String
    )

    title: Mapped[str] = mapped_column(
        String
    )

    url: Mapped[str] = mapped_column(
        String
    )

    location: Mapped[str] = mapped_column(
        String,
        default=""
    )

    department: Mapped[str] = mapped_column(
        String,
        default=""
    )

    source: Mapped[str] = mapped_column(
        String,
        default="text"
    )

    matched_keywords: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0
    )

    ai_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    ai_reason: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    first_seen: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow
    )

    last_seen: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow
    )

    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True
    )


class SiteHealth(Base):
    """Состояние источника. Нужна, чтобы отличить «вакансий нет» от
    «страница не загрузилась или отдала пустоту»."""

    __tablename__ = "site_health"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    url: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String,
        default=""
    )

    source: Mapped[str] = mapped_column(
        String,
        default=""
    )

    vacancies_found: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
        index=True
    )

    last_error: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )