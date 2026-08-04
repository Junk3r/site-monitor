from loguru import logger
from telegram import Bot


MAX_MESSAGE_LENGTH = 4000


def build_chunks(
    header: str,
    entries: list[str],
) -> list[str]:
    """Режет дайджест на сообщения в пределах лимита Telegram.
    Пустые сообщения отбрасываются — Telegram их отклоняет."""

    chunks = []

    current = header + "\n\n" if header else ""

    for entry in entries:

        # запись длиннее лимита не влезет ни в какой чанк — режем её
        if len(entry) > MAX_MESSAGE_LENGTH - 2:
            entry = entry[:MAX_MESSAGE_LENGTH - 5] + "..."

        if len(current) + len(entry) + 2 > MAX_MESSAGE_LENGTH:
            chunks.append(current)
            current = ""

        current += entry + "\n\n"


    chunks.append(current)


    return [
        chunk.strip()
        for chunk in chunks
        if chunk.strip()
    ]


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


    async def send_text(
        self,
        text: str,
    ):
        """Служебное сообщение — например, сводка по сломанным сайтам."""

        await self._send_chunks(
            "",
            [text],
        )


    async def _send_chunks(
        self,
        header: str,
        entries: list[str],
    ):

        for text in build_chunks(header, entries):

            async with Bot(self.token) as bot:

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
