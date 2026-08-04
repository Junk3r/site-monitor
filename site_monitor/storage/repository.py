from sqlalchemy.orm import Session

from site_monitor.storage.models import (
    MonitoredPage,
    Opportunity,
    SiteHealth,
    utcnow,
)


class PageRepository:

    def __init__(
        self,
        session: Session
    ):
        self.session = session


    def get_by_url(
        self,
        url: str
    ):

        return (
            self.session
            .query(MonitoredPage)
            .filter(
                MonitoredPage.url == url
            )
            .first()
        )


    def save(
        self,
        url: str,
        title: str,
        content: str
    ):

        page = MonitoredPage(
            url=url,
            title=title,
            content=content
        )

        self.session.add(page)
        self.session.commit()


    def update(
        self,
        page: MonitoredPage,
        title: str,
        content: str
    ):

        page.title = title
        page.content = content

        self.session.commit()


class OpportunityRepository:

    def __init__(
        self,
        session: Session
    ):
        self.session = session


    def upsert_many(
        self,
        matches: list,
    ) -> list[Opportunity]:
        """Принимает список Match (vacancy + метаданные правила).
        Уже известные вакансии только обновляют last_seen.
        Возвращает те, что видим впервые."""

        if not matches:
            return []


        fingerprints = {
            match.vacancy.fingerprint: match
            for match in matches
        }

        existing = (
            self.session
            .query(Opportunity)
            .filter(
                Opportunity.fingerprint.in_(
                    list(fingerprints)
                )
            )
            .all()
        )

        known = {
            opportunity.fingerprint
            for opportunity in existing
        }

        now = utcnow()

        for opportunity in existing:
            opportunity.last_seen = now


        created = []

        for fingerprint, match in fingerprints.items():

            if fingerprint in known:
                continue

            vacancy = match.vacancy

            opportunity = Opportunity(
                fingerprint=fingerprint,
                site=vacancy.site,
                title=vacancy.title.strip(),
                url=vacancy.url,
                location=vacancy.location,
                department=vacancy.department,
                source=vacancy.source,
                matched_keywords=", ".join(match.keywords),
                confidence=match.confidence,
                first_seen=now,
                last_seen=now,
            )

            self.session.add(opportunity)

            created.append(opportunity)


        self.session.commit()

        return created


    def pending_notification(self) -> list[Opportunity]:

        return (
            self.session
            .query(Opportunity)
            .filter(
                Opportunity.notified_at.is_(None)
            )
            .order_by(
                Opportunity.id
            )
            .all()
        )


    def mark_notified(
        self,
        opportunities: list[Opportunity],
    ):

        now = utcnow()

        for opportunity in opportunities:
            opportunity.notified_at = now

        self.session.commit()


    def save_scores(self):

        self.session.commit()


class SiteHealthRepository:

    def __init__(
        self,
        session: Session
    ):
        self.session = session


    def _get_or_create(self, site) -> SiteHealth:

        record = (
            self.session
            .query(SiteHealth)
            .filter(
                SiteHealth.url == site.url
            )
            .first()
        )

        if record is None:

            # значения по умолчанию из колонок проставляются только при
            # вставке, поэтому до неё поля надо заполнить самому
            record = SiteHealth(
                url=site.url,
                name=site.name,
                source="",
                vacancies_found=0,
                consecutive_failures=0,
                last_error="",
            )

            self.session.add(record)


        record.name = site.name

        return record


    def record_success(
        self,
        site,
        source: str,
        vacancies: int,
    ):

        now = utcnow()

        record = self._get_or_create(site)

        record.source = source
        record.vacancies_found = vacancies
        record.consecutive_failures = 0
        record.last_error = ""
        record.last_checked_at = now
        record.last_success_at = now

        self.session.commit()


    def record_failure(
        self,
        site,
        error: str,
        source: str = "",
    ):

        record = self._get_or_create(site)

        if source:
            record.source = source

        record.vacancies_found = 0
        record.consecutive_failures += 1
        record.last_error = error[:500]
        record.last_checked_at = utcnow()

        self.session.commit()


    def problems(
        self,
        min_failures: int = 1,
    ) -> list[SiteHealth]:

        return (
            self.session
            .query(SiteHealth)
            .filter(
                SiteHealth.consecutive_failures >= min_failures
            )
            .order_by(
                SiteHealth.consecutive_failures.desc(),
                SiteHealth.name,
            )
            .all()
        )