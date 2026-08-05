import asyncio

from loguru import logger

from site_monitor.ai.client import OllamaClient

from site_monitor.fetchers.ats import ATSFetcher

from site_monitor.fetchers.playwright_fetcher import (
    PlaywrightFetcher
)

from site_monitor.parsers.generic import (
    GenericParser,
    looks_blocked,
)

from site_monitor.rules.engine import RuleEngine
from site_monitor.rules.keyword import KeywordRule
from site_monitor.rules.relevance import RelevanceScorer
from site_monitor.rules.semantic import SemanticRule

from site_monitor.schemas.vacancy import Vacancy

from site_monitor.storage.database import SessionLocal

from site_monitor.storage.repository import (
    OpportunityRepository,
    PageRepository,
    SiteHealthRepository,
)

from site_monitor.notifications.telegram import TelegramNotifier


DEFAULT_FETCH_CONCURRENCY = 3

DIGEST_BATCH_SIZE = 30

# ниже этого объёма текста страница считается не загрузившейся:
# Shift4 отдаёт 0 символов, IGT и Games Global по 13
DEFAULT_MIN_CONTENT_LENGTH = 200

DEFAULT_HEALTH_ALERT_AFTER = 3


class Monitor:

    def __init__(self, config):

        monitor = config.get("monitor", {})

        self.fetcher = PlaywrightFetcher(
            attempts=monitor.get("fetch_attempts", 2),
        )

        self.ats = ATSFetcher()
        self.parser = GenericParser()

        self.session = SessionLocal()

        self.repository = PageRepository(self.session)

        self.opportunities = OpportunityRepository(self.session)

        self.health = SiteHealthRepository(self.session)

        self.fetch_concurrency = monitor.get(
            "concurrency",
            DEFAULT_FETCH_CONCURRENCY,
        )

        self.min_content_length = monitor.get(
            "min_content_length",
            DEFAULT_MIN_CONTENT_LENGTH,
        )

        self.health_alert_after = monitor.get(
            "health_alert_after",
            DEFAULT_HEALTH_ALERT_AFTER,
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

            profile = config.get("profile", {})

            self.scorer = RelevanceScorer(
                client=self.ai_client,
                model=ai["model"],
                profile=profile.get("candidate", ""),
                scale=profile.get("scale", ""),
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

        self.dry_run = telegram.get("dry_run", False)

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

        if not from_db:
            await self._report_health()

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

                self.health.record_failure(
                    site,
                    f"{type(result).__name__}: {result}",
                )

            elif result:
                matches.extend(result)

        return matches


    async def _collect(self, site) -> list[Vacancy]:

        vacancies = await self.ats.fetch(site)

        if vacancies is not None:

            self.health.record_success(
                site,
                vacancies[0].source,
                len(vacancies),
            )

            return vacancies


        html = await self.fetcher.fetch(site.url)

        title = self.parser.parse_title(html)

        content = self.parser.parse_text(html)

        self._save_snapshot(site, title, content)

        # антибот-заслон отдаёт 200 и осмысленный текст, поэтому порога
        # длины мало — Playson так проходил с 317 символами
        if looks_blocked(content):

            logger.warning(
                f"{site.name} served a bot-protection page "
                f"instead of content"
            )

            self.health.record_failure(
                site,
                "blocked by bot protection",
                source="browser",
            )

            return []


        # пустая страница неотличима от «вакансий нет», если про неё
        # не сказать отдельно
        if len(content) < self.min_content_length:

            logger.warning(
                f"{site.name} returned only {len(content)} characters "
                f"of text, page likely did not render"
            )

            self.health.record_failure(
                site,
                f"page returned only {len(content)} characters of text",
                source="browser",
            )

            return []


        vacancies = self.parser.parse_vacancies(
            html,
            site.url,
            site.name,
        )

        self.health.record_success(
            site,
            "browser",
            len(vacancies),
        )

        return vacancies


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


    async def _report_health(self):

        problems = self.health.problems()

        if not problems:

            logger.info("All sites healthy")

            return


        logger.warning(
            f"{len(problems)} sites are not returning vacancies:"
        )

        for record in problems:

            logger.warning(
                f"  {record.name}: {record.last_error} "
                f"({record.consecutive_failures} in a row)"
            )


        persistent = [
            record
            for record in problems
            if record.consecutive_failures >= self.health_alert_after
        ]

        if not persistent or not self.notifier:
            return


        lines = "\n".join(
            f"{record.name} ({record.consecutive_failures}x): "
            f"{record.last_error}"
            for record in persistent
        )

        await self.notifier.send_text(
            f"{len(persistent)} sites broken for "
            f"{self.health_alert_after}+ runs:\n\n{lines}"
        )


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

            if not self.dry_run:
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
