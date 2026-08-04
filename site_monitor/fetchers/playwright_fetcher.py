from loguru import logger
from playwright.async_api import async_playwright

from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_fixed,
)


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

VIEWPORT = {"width": 1440, "height": 900}

GOTO_TIMEOUT = 15000

NETWORKIDLE_TIMEOUT = 10000

RETRY_WAIT_SECONDS = 3


class PlaywrightFetcher:

    def __init__(
        self,
        attempts: int = 2,
    ):
        self.playwright = None
        self.browser = None

        self.attempts = max(1, attempts)


    async def start(self):

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=True
        )


    async def fetch(
        self,
        url: str
    ):
        """Сетевые сбои часто разовые, поэтому неудачная загрузка
        повторяется, а не теряет сайт до следующего цикла."""

        try:

            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.attempts),
                wait=wait_fixed(RETRY_WAIT_SECONDS),
                reraise=True,
            ):

                with attempt:

                    number = attempt.retry_state.attempt_number

                    if number > 1:

                        logger.debug(
                            f"Retry {number}/{self.attempts} for {url}"
                        )

                    return await self._fetch_once(url)

        except RetryError as e:

            raise e.last_attempt.exception()


    async def _fetch_once(
        self,
        url: str
    ):

        # свой контекст на попытку: реальный User-Agent вместо
        # headless-строки и чистые куки
        context = await self.browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            locale="en-US",
        )

        page = await context.new_page()

        try:

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=GOTO_TIMEOUT,
            )

            try:

                await page.wait_for_load_state(
                    "networkidle",
                    timeout=NETWORKIDLE_TIMEOUT,
                )

            except Exception:

                logger.debug(
                    f"networkidle timeout for {url}, using current state"
                )

            return await page.content()


        except Exception as e:

            logger.error(
                f"Failed to fetch {url}: {e}"
            )

            raise


        finally:

            await context.close()


    async def close(self):

        if self.browser:

            await self.browser.close()


        if self.playwright:

            await self.playwright.stop()
