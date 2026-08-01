from sqlalchemy.orm import Session

from site_monitor.storage.models import (
    MonitoredPage
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