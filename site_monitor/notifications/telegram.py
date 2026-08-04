from loguru import logger
from telegram import Bot


MAX_MESSAGE_LENGTH = 4000


class TelegramNotifier:

    def __init__(
        self,
        token: str,
        chat_id: str
    ):
        self.token = token
        self.chat_id = chat_id


    async def send_digest(
        self,
        opportunities: list,
        header: str = "",
    ):

        if not opportunities:
            return


        logger.info(
            f"Sending Telegram digest: {len(opportunities)} opportunities"
        )

        if not header:
            header = (
                f"Vacancy digest — {len(opportunities)} opportunities found"
            )


        entries = [
            self._format(opportunity)
            for opportunity in opportunities
        ]

        await self._send_chunks(
            header,
            entries
        )


    async def send(
        self,
        opportunity,
    ):

        await self._send_chunks(
            "New opportunity detected",
            [self._format(opportunity)],
        )


    async def _send_chunks(
        self,
        header: str,
        entries: list[str],
    ):

        chunks = []

        current = header + "\n\n"

        for entry in entries:

            # запись длиннее лимита не влезет ни в какой чанк — режем её
            if len(entry) > MAX_MESSAGE_LENGTH - 2:
                entry = entry[:MAX_MESSAGE_LENGTH - 5] + "..."

            if len(current) + len(entry) + 2 > MAX_MESSAGE_LENGTH:
                chunks.append(current)
                current = ""

            current += entry + "\n\n"


        chunks.append(current)


        async with Bot(self.token) as bot:

            for chunk in chunks:

                text = chunk.strip()

                # Telegram отклоняет пустое сообщение
                if not text:
                    continue

                await bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                )


    def _format(
        self,
        opportunity,
    ) -> str:

        score = (
            f"[{opportunity.ai_score}/10] "
            if opportunity.ai_score is not None
            else ""
        )

        line = (
            f"{score}{opportunity.site}: "
            f"{opportunity.title[:100]}"
        )

        if opportunity.location:
            line += f" — {opportunity.location[:60]}"

        if opportunity.ai_reason:
            line += f"\n{opportunity.ai_reason[:200]}"

        return f"{line}\n{opportunity.url}"
