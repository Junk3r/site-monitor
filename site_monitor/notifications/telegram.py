from loguru import logger
from telegram import Bot

from site_monitor.rules.models import OpportunityEvent


MAX_MESSAGE_LENGTH = 4000


class TelegramNotifier:

    def __init__(
        self,
        token: str,
        chat_id: str
    ):
        self.token = token
        self.chat_id = chat_id


    async def send(
        self,
        event: OpportunityEvent
    ):

        text = self._format(event)

        logger.info(
            f"Sending Telegram notification for {event.site}"
        )

        async with Bot(self.token) as bot:

            await bot.send_message(
                chat_id=self.chat_id,
                text=text,
            )


    def _format(
        self,
        event: OpportunityEvent
    ) -> str:

        lines = "\n".join(
            f"- {line}"
            for line in event.matched_lines
        )

        keywords = ", ".join(
            event.matched_keywords
        )

        location = (
            ", ".join(event.matched_locations)
            if event.matched_locations
            else "not specified in listing"
        )

        text = (
            f"New opportunity detected\n\n"
            f"Site: {event.site}\n\n"
            f"Matched keywords: {keywords}\n"
            f"Location: {location}\n\n"
            f"New lines:\n{lines}\n\n"
            f"URL: {event.url}"
        )

        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[:MAX_MESSAGE_LENGTH]

        return text
