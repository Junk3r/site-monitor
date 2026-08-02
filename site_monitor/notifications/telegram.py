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


    async def send_digest(
        self,
        events: list[OpportunityEvent],
        header: str = "",
    ):

        logger.info(
            f"Sending Telegram digest: {len(events)} opportunities"
        )

        entries = []

        for event in events:

            score = (
                f"[{event.ai_score}/10] "
                if event.ai_score is not None
                else ""
            )

            title = event.title[:80]

            entries.append(
                f"{score}{event.site}: {title}\n{event.url}"
            )


        if not header:
            header = (
                f"Vacancy digest — {len(events)} opportunities found"
            )

        header += "\n\n"

        chunks = []
        current = header

        for entry in entries:

            if len(current) + len(entry) + 2 > MAX_MESSAGE_LENGTH:
                chunks.append(current)
                current = ""

            current += entry + "\n\n"

        chunks.append(current)


        async with Bot(self.token) as bot:

            for chunk in chunks:

                await bot.send_message(
                    chat_id=self.chat_id,
                    text=chunk.strip(),
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

        score = ""

        if event.ai_score is not None:

            score = f"Fit score: {event.ai_score}/10"

            if event.ai_reason:
                score += f" — {event.ai_reason}"

            score += "\n"

        text = (
            f"New opportunity detected\n\n"
            f"Site: {event.site}\n\n"
            f"{score}"
            f"Matched keywords: {keywords}\n"
            f"Location: {location}\n\n"
            f"New lines:\n{lines}\n\n"
            f"URL: {event.url}"
        )

        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[:MAX_MESSAGE_LENGTH]

        return text
