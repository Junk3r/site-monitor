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

from site_monitor.rules.engine import (
    RuleEngine
)

from site_monitor.rules.keyword import (
    KeywordRule
)

from site_monitor.notifications.telegram import (
    TelegramNotifier
)


class Monitor:

    def __init__(self, config):

        self.fetcher = PlaywrightFetcher()
        self.parser = GenericParser()

        self.session = SessionLocal()

        self.repository = PageRepository(
            self.session
        )

        keywords = config["keywords"]

        self.engine = RuleEngine([
            KeywordRule(
                include=keywords["include"],
                exclude=keywords["exclude"],
            )
        ])

        telegram = config["telegram"]

        self.notifier = None

        if telegram["enabled"]:

            if telegram["token"] and telegram["chat_id"]:

                self.notifier = TelegramNotifier(
                    token=telegram["token"],
                    chat_id=telegram["chat_id"],
                )

            else:

                logger.warning(
                    "Telegram enabled but token/chat_id missing in .env"
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
        site
    ):

        logger.info(
            f"Checking {site.url}"
        )

        html = await self.fetcher.fetch(
            site.url
        )

        title = self.parser.parse_title(
            html
        )

        content = self.parser.parse_text(
            html
        )

        page = self.repository.get_by_url(
            site.url
        )


        if page is None:

            logger.info(
                f"Snapshot saved for {site.name}"
            )

            self.repository.save(
                site.url,
                title,
                content
            )

            return


        events = self.engine.evaluate(
            site=site.name,
            url=site.url,
            old_content=page.content or "",
            new_content=content,
        )


        if events:

            logger.warning(
                f"Opportunities detected on {site.name}: {len(events)}"
            )

            for event in events:

                if self.notifier:

                    await self.notifier.send(
                        event
                    )

                else:

                    logger.info(
                        f"Matched: {event.matched_keywords} "
                        f"in {event.matched_lines}"
                    )

        else:

            logger.info(
                "No relevant changes"
            )


        self.repository.update(
            page,
            title,
            content
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
                    site
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
