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

from site_monitor.rules.semantic import (
    SemanticRule
)

from site_monitor.rules.relevance import (
    RelevanceScorer
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

        rules = [
            KeywordRule(
                include=keywords["roles"]["include"],
                exclude=keywords["roles"]["exclude"],
                locations=keywords["locations"],
            )
        ]

        ai = config["ai"]

        self.scorer = None

        if ai["enabled"]:

            rules.append(
                SemanticRule(
                    base_url=ai["base_url"],
                    model=ai["model"],
                    skip_keywords=keywords["roles"]["include"],
                    exclude=keywords["roles"]["exclude"],
                    embedding_model=ai.get("embedding_model", ""),
                )
            )

            self.scorer = RelevanceScorer(
                base_url=ai["base_url"],
                model=ai["model"],
            )

            logger.info(
                f"AI rule enabled: {ai['model']} at {ai['base_url']}"
            )

        self.engine = RuleEngine(rules)

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


        events = await self.engine.evaluate(
            site=site.name,
            url=site.url,
            old_content=page.content or "",
            new_content=content,
        )


        if events:

            logger.warning(
                f"Opportunities detected on {site.name}: {len(events)}"
            )

            if self.scorer:

                events = [
                    await self.scorer.score(event)
                    for event in events
                ]

                events.sort(
                    key=lambda e: e.ai_score or 0,
                    reverse=True,
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


    async def scan(
        self,
        site
    ):

        html = await self.fetcher.fetch(
            site.url
        )

        title = self.parser.parse_title(
            html
        )

        content = self.parser.parse_text(
            html
        )

        events = await self.engine.evaluate(
            site=site.name,
            url=site.url,
            old_content="",
            new_content=content,
        )

        page = self.repository.get_by_url(
            site.url
        )

        if page is None:

            self.repository.save(
                site.url,
                title,
                content
            )

        else:

            self.repository.update(
                page,
                title,
                content
            )

        return events


    async def scan_all(
        self,
        sites
    ):

        logger.info(
            f"Scanning existing vacancies on {len(sites)} sites"
        )

        semaphore = asyncio.Semaphore(3)


        async def limited_scan(site):

            async with semaphore:

                logger.info(
                    f"Scanning site: {site.name}"
                )

                return await self.scan(
                    site
                )


        results = await asyncio.gather(
            *(limited_scan(site) for site in sites),
            return_exceptions=True
        )


        all_events = []

        for site, result in zip(sites, results):

            if isinstance(result, Exception):

                logger.error(
                    f"Failed scanning {site.name}: {result}"
                )

            elif result:

                all_events.extend(result)


        logger.info(
            f"Scan found {len(all_events)} events, scoring..."
        )

        if self.scorer:

            for index, event in enumerate(all_events):

                logger.info(
                    f"Scoring {index + 1}/{len(all_events)}: "
                    f"{event.site}"
                )

                all_events[index] = await self.scorer.score(
                    event
                )

            all_events.sort(
                key=lambda e: e.ai_score or 0,
                reverse=True,
            )


        if self.notifier and all_events:

            await self.notifier.send_digest(
                all_events
            )

        return all_events
