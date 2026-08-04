import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from site_monitor.rules.models import Match
from site_monitor.schemas.vacancy import Vacancy
from site_monitor.storage.database import resolve_url
from site_monitor.storage.models import Base
from site_monitor.storage.repository import (
    OpportunityRepository,
    SiteHealthRepository,
)


class Site:

    def __init__(self, name, url):
        self.name = name
        self.url = url


@pytest.fixture
def session():

    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    with sessionmaker(bind=engine)() as opened:
        yield opened


def match(url, title="Account Manager"):

    return Match(
        vacancy=Vacancy(
            site="Acme",
            title=title,
            url=url,
            location="Malta",
            direct=True,
        ),
        keywords=["account manager"],
        confidence=1.0,
    )


def test_upsert_returns_only_unseen(session):

    repository = OpportunityRepository(session)

    first = repository.upsert_many([match("https://acme.com/1")])

    assert len(first) == 1

    again = repository.upsert_many([match("https://acme.com/1")])

    assert again == []


def test_upsert_deduplicates_within_one_batch(session):

    repository = OpportunityRepository(session)

    created = repository.upsert_many(
        [
            match("https://acme.com/1"),
            match("https://acme.com/1?utm_source=mail"),
            match("https://acme.com/2"),
        ]
    )

    assert len(created) == 2


def test_second_sighting_updates_last_seen(session):

    repository = OpportunityRepository(session)

    created = repository.upsert_many([match("https://acme.com/1")])[0]

    before = created.last_seen

    repository.upsert_many([match("https://acme.com/1")])

    assert created.last_seen >= before


def test_notification_happens_once(session):

    repository = OpportunityRepository(session)

    repository.upsert_many(
        [match("https://acme.com/1"), match("https://acme.com/2")]
    )

    pending = repository.pending_notification()

    assert len(pending) == 2

    repository.mark_notified(pending)

    assert repository.pending_notification() == []


def test_upsert_of_empty_list_is_a_noop(session):

    assert OpportunityRepository(session).upsert_many([]) == []


def test_failure_counter_starts_from_zero_on_a_fresh_row(session):
    """Значения по умолчанию проставляются только при вставке, поэтому
    первый record_failure на новой записи ронял += 1 на None."""

    repository = SiteHealthRepository(session)

    site = Site("Shift4", "https://shift4.com/careers")

    repository.record_failure(site, "page returned only 0 characters")

    assert repository.problems()[0].consecutive_failures == 1


def test_failures_accumulate_and_success_resets(session):

    repository = SiteHealthRepository(session)

    site = Site("Shift4", "https://shift4.com/careers")

    repository.record_failure(site, "boom")
    repository.record_failure(site, "boom")

    assert repository.problems()[0].consecutive_failures == 2

    repository.record_success(site, "browser", 12)

    assert repository.problems() == []


def test_problems_respect_the_threshold(session):

    repository = SiteHealthRepository(session)

    flaky = Site("Flaky", "https://flaky.com")
    broken = Site("Broken", "https://broken.com")

    repository.record_failure(flaky, "once")

    for _ in range(3):
        repository.record_failure(broken, "always")

    assert len(repository.problems()) == 2

    persistent = repository.problems(min_failures=3)

    assert [record.name for record in persistent] == ["Broken"]


def test_relative_sqlite_path_resolves_against_the_project():
    """Относительный путь раньше зависел от текущей директории и
    создавал вторую базу при запуске из другой папки."""

    resolved = resolve_url("sqlite:///data/monitor.db")

    assert resolved.startswith("sqlite:///")

    assert "site-monitor/data/monitor.db" in resolved.replace("\\", "/")


def test_memory_and_absolute_urls_pass_through():

    assert resolve_url("sqlite:///:memory:") == "sqlite:///:memory:"

    assert resolve_url(
        "postgresql://localhost/db"
    ) == "postgresql://localhost/db"
