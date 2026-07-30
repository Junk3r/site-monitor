import asyncio

from loguru import logger

from site_monitor.fetchers.playwright_fetcher import (
    PlaywrightFetcher
)

from site_monitor.parsers.generic import (
    GenericParser
)

from site_monitor.storage.database import (
    SessionLocal
)

from site_monitor.storage.repository import (
    PageRepository
)


class Monitor:

    def __init__(self):

        self.fetcher = PlaywrightFetcher()
        self.parser = GenericParser()

        self.session = SessionLocal()

        self.repository = PageRepository(
            self.session
        )


    async def start(self):

        logger.info(
            "Starting browser"
        )

        await self.fetcher.start()


    async def stop(self):

        logger.info(
            "Stopping browser"
        )

        await self.fetcher.close()

        self.session.close()


    async def check(
        self,
        url: str
    ):

        logger.info(
            f"Checking {url}"
        )

        html = await self.fetcher.fetch(
            url
        )

        title = self.parser.parse_title(
            html
        )

        page = self.repository.get_by_url(
            url
        )


        if page is None:

            logger.info(
                "New page detected"
            )

            self.repository.save(
                url,
                title
            )

            return


        if page.title != title:

            logger.warning(
                f"Change detected: {page.title} -> {title}"
            )

            self.repository.update(
                page,
                title
            )

        else:

            logger.info(
                "No changes"
            )


    async def check_all(
        self,
        sites
    ):

        logger.info(
            f"Starting parallel check for {len(sites)} sites"
        )

        semaphore = asyncio.Semaphore(3)


        async def limited_check(site):

            async with semaphore:

                logger.info(
                    f"Checking site: {site.name}"
                )

                await self.check(
                    site.url
                )


        tasks = [
            limited_check(site)
            for site in sites
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )


        for site, result in zip(sites, results):

            if isinstance(result, Exception):

                logger.error(
                    f"Failed checking {site.name}: {result}"
                )