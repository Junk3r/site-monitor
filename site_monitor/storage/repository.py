from sqlalchemy.orm import Session

from site_monitor.storage.models import (
    MonitoredPage,
    Opportunity,
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