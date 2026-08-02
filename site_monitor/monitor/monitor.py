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


DIGEST_BATCH_SIZE = 30


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
        sites,
        from_db: bool = False,
    ):

        if from_db:

            all_events = await self._events_from_db(
                sites
            )

        else:

            all_events = await self._events_from_web(
                sites
            )


        logger.info(
            f"Scan found {len(all_events)} events, scoring..."
        )

        scored = []

        for index, event in enumerate(all_events):

            if self.scorer:

                logger.info(
                    f"Scoring {index + 1}/{len(all_events)}: "
                    f"{event.site}"
                )

                event = await self.scorer.score(
                    event
                )

            scored.append(event)

            if (
                self.notifier
                and len(scored) % DIGEST_BATCH_SIZE == 0
            ):

                await self._send_batch(
                    scored[-DIGEST_BATCH_SIZE:],
                    len(scored),
                    len(all_events),
                )


        remainder = len(scored) % DIGEST_BATCH_SIZE

        if self.notifier and remainder:

            await self._send_batch(
                scored[-remainder:],
                len(scored),
                len(all_events),
            )

        return scored


    async def _send_batch(
        self,
        batch,
        done,
        total,
    ):

        batch = sorted(
            batch,
            key=lambda e: e.ai_score or 0,
            reverse=True,
        )

        await self.notifier.send_digest(
            batch,
            header=(
                f"Vacancy digest {done}/{total} scored "
                f"— batch of {len(batch)}"
            ),
        )


    async def _events_from_web(
        self,
        sites
    ):

        semaphore = asyncio.Semaphore(3)

        logger.info(
            f"Scanning existing vacancies on {len(sites)} sites"
        )


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

        return all_events


    async def _events_from_db(
        self,
        sites
    ):

        logger.info(
            f"Scanning stored snapshots for {len(sites)} sites "
            f"(no fetching)"
        )

        all_events = []

        for site in sites:

            page = self.repository.get_by_url(
                site.url
            )

            if page is None or not page.content:

                logger.warning(
                    f"No stored snapshot for {site.name}, skipping"
                )

                continue

            try:

                events = await self.engine.evaluate(
                    site=site.name,
                    url=site.url,
                    old_content="",
                    new_content=page.content,
                )

            except Exception as e:

                logger.error(
                    f"Failed scanning {site.name} from DB: {e}"
                )

                continue

            all_events.extend(events)

        return all_events
