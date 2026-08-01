from loguru import logger
from playwright.async_api import async_playwright


class PlaywrightFetcher:

    def __init__(self):

        self.playwright = None
        self.browser = None


    async def start(self):

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=True
        )


    async def fetch(
        self,
        url: str
    ):

        page = await self.browser.new_page()

        try:

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=15000
            )

            try:

                await page.wait_for_load_state(
                    "networkidle",
                    timeout=10000
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

            await page.close()


    async def close(self):

        if self.browser:

            await self.browser.close()


        if self.playwright:

            await self.playwright.stop()