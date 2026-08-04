import asyncio

from loguru import logger

from site_monitor.ai.client import OllamaClient

from site_monitor.fetchers.ats import ATSFetcher

from site_monitor.fetchers.playwright_fetcher import (
    PlaywrightFetcher
)

from site_monitor.parsers.generic import GenericParser

from site_monitor.rules.engine import RuleEngine
from site_monitor.rules.keyword import KeywordRule
from site_monitor.rules.relevance import RelevanceScorer
from site_monitor.rules.semantic import SemanticRule

from site_monitor.schemas.vacancy import Vacancy

from site_monitor.storage.database import SessionLocal

from site_monitor.storage.repository import (
    OpportunityRepository,
    PageRepository,
)

from site_monitor.notifications.telegram import TelegramNotifier


DEFAULT_FETCH_CONCURRENCY = 3

DIGEST_BATCH_SIZE = 30


class Monitor:

    def __init__(self, config):

        self.fetcher = PlaywrightFetcher()
        self.ats = ATSFetcher()
        self.parser = GenericParser()

        self.session = SessionLocal()

        self.repository = PageRepository(self.session)

        self.opportunities = OpportunityRepository(self.session)

        monitor = config.get("monitor", {})

        self.fetch_concurrency = monitor.get(
            "concurrency",
            DEFAULT_FETCH_CONCURRENCY,
        )

        keywords = config["keywords"]

        keyword_rule = KeywordRule(
            include=keywords["roles"]["include"],
            exclude=keywords["roles"]["exclude"],
            locations=keywords["locations"],
        )

        ai = config["ai"]

        self.ai_client = None
        self.scorer = None

        semantic_rule = None

        if ai["enabled"]:

            self.ai_client = OllamaClient(
                base_url=ai["base_url"],
                concurrency=ai.get("concurrency", 1),
                think=ai.get("think", False),
            )

            semantic_rule = SemanticRule(
                client=self.ai_client,
                model=ai["model"],
                skip_keywords=keywords["roles"]["include"],
                exclude=keywords["roles"]["exclude"],
                embedding_model=ai.get("embedding_model", ""),
            )

            self.scorer = RelevanceScorer(
                client=self.ai_client,
                model=ai["model"],
            )

            logger.info(
                f"AI rule enabled: {ai['model']} at {ai['base_url']}"
            )

        self.engine = RuleEngine(
            keyword_rule=keyword_rule,
            semantic_rule=semantic_rule,
        )

        telegram = config["telegram"]

        self.min_score = telegram.get("min_score", 0)

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


    async def start(self, browser: bool = True):

        await self.ats.start()

        if self.ai_client:
            await self.ai_client.start()

        if browser:

            logger.info("Starting browser")

            await self.fetcher.start()


    async def stop(self, browser: bool = True):

        if browser:

            logger.info("Stopping browser")

            await self.fetcher.close()

        await self.ats.close()

        if self.ai_client:
            await self.ai_client.close()

        self.session.close()


    async def run(
        self,
        sites,
        from_db: bool = False,
    ):
        """Один проход: собрать вакансии, отсеять правилами, сохранить,
        оценить и оповестить только про новые."""

        if from_db:
            matches = await self._matches_from_db(sites)

        else:
            matches = await self._matches_from_sources(sites)


        logger.info(
            f"Rules matched {len(matches)} vacancies"
        )

        created = self.opportunities.upsert_many(matches)

        logger.info(
            f"{len(created)} new, "
            f"{len(matches) - len(created)} already known"
        )

        pending = self.opportunities.pending_notification()

        if not pending:
            return []


        if self.scorer:

            logger.info(
                f"Scoring {len(pending)} new opportunities"
            )

            await self.scorer.score_many(pending)

            self.opportunities.save_scores()


        await self._notify(pending)

        return pending


    async def _matches_from_sources(self, sites):
        """Фетч и LLM работают конвейером: семафор освобождается сразу
        после загрузки, поэтому пока один сайт стоит в очереди к модели,
        остальные продолжают качаться."""

        semaphore = asyncio.Semaphore(self.fetch_concurrency)

        logger.info(
            f"Checking {len(sites)} sites "
            f"(fetch concurrency {self.fetch_concurrency})"
        )


        async def process(site):

            async with semaphore:

                vacancies = await self._collect(site)

            if not vacancies:
                return []

            return await self.engine.evaluate(
                site.name,
                vacancies,
            )


        results = await asyncio.gather(
            *(process(site) for site in sites),
            return_exceptions=True,
        )


        matches = []

        for site, result in zip(sites, results):

            if isinstance(result, Exception):

                logger.error(
                    f"Failed checking {site.name}: {result}"
                )

            elif result:
                matches.extend(result)

        return matches


    async def _collect(self, site) -> list[Vacancy]:

        vacancies = await self.ats.fetch(site)

        if vacancies is not None:
            return vacancies


        html = await self.fetcher.fetch(site.url)

        title = self.parser.parse_title(html)

        content = self.parser.parse_text(html)

        self._save_snapshot(site, title, content)

        return self.parser.parse_vacancies(
            html,
            site.url,
            site.name,
        )


    def _save_snapshot(self, site, title, content):

        page = self.repository.get_by_url(site.url)

        if page is None:
            self.repository.save(site.url, title, content)

        else:
            self.repository.update(page, title, content)


    async def _matches_from_db(self, sites):

        logger.info(
            f"Scanning stored snapshots for {len(sites)} sites "
            f"(no fetching)"
        )

        matches = []

        for site in sites:

            page = self.repository.get_by_url(site.url)

            if page is None or not page.content:

                logger.warning(
                    f"No stored snapshot for {site.name}, skipping"
                )

                continue


            vacancies = [
                Vacancy(
                    site=site.name,
                    title=line,
                    url=site.url,
                    source="text",
                )
                for line in page.content.splitlines()
                if line.strip()
            ]

            try:

                matches.extend(
                    await self.engine.evaluate(
                        site.name,
                        vacancies,
                    )
                )

            except Exception as e:

                logger.error(
                    f"Failed scanning {site.name} from DB: {e}"
                )

        return matches


    async def _notify(self, opportunities):

        shortlist = [
            opportunity
            for opportunity in opportunities
            if (opportunity.ai_score or 0) >= self.min_score
        ]

        skipped = len(opportunities) - len(shortlist)

        if skipped:

            logger.info(
                f"{skipped} opportunities below min_score "
                f"{self.min_score}, not sent"
            )


        if not self.notifier:

            for opportunity in shortlist:

                logger.info(
                    f"[{opportunity.ai_score or '-'}] "
                    f"{opportunity.site}: {opportunity.title} "
                    f"-> {opportunity.url}"
                )

            self.opportunities.mark_notified(opportunities)

            return


        shortlist.sort(
            key=lambda item: item.ai_score or 0,
            reverse=True,
        )

        for start in range(0, len(shortlist), DIGEST_BATCH_SIZE):

            batch = shortlist[start:start + DIGEST_BATCH_SIZE]

            await self.notifier.send_digest(
                batch,
                header=(
                    f"New vacancies "
                    f"{start + len(batch)}/{len(shortlist)}"
                ),
            )


        self.opportunities.mark_notified(opportunities)


    # обратная совместимость с main.py

    async def check_all(self, sites):

        return await self.run(sites)


    async def scan_all(self, sites, from_db: bool = False):

        return await self.run(sites, from_db=from_db)
