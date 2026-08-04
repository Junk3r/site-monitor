"""Единая точка обращения к Ollama.

Раньше классификация и скоринг создавали по своему httpx-клиенту и
конкурировали за модель: семафор стоял только на классификации, а скоринг
шёл мимо него. Здесь один семафор на весь процесс и одно соединение.
"""

import asyncio
import json

import httpx

from loguru import logger


# Ollama роняет раннер на больших батчах эмбеддингов
# (120 строк проходят, 240 дают 400) — режем с запасом
EMBED_BATCH_SIZE = 64

EMBED_MAX_CHARS = 2000


class OllamaClient:

    def __init__(
        self,
        base_url: str,
        concurrency: int = 1,
        chat_timeout: int = 180,
        embed_timeout: int = 120,
        think: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.chat_timeout = chat_timeout
        self.embed_timeout = embed_timeout

        # Рассуждающие модели (qwen3.x) уводят до 8000 символов в thinking
        # и на длинном промпте возвращают пустой content — отключаем.
        # Если модель не умеет thinking, Ollama отвергает поле: тогда
        # повторяем запрос без него.
        self.think = think

        self._think_supported = True

        # Ollama обрабатывает запросы по одному: параллельные вызовы
        # выстраиваются в очередь и упираются в таймаут
        self.semaphore = asyncio.Semaphore(concurrency)

        self.client = None


    async def start(self):

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.chat_timeout,
        )


    async def close(self):

        if self.client:

            await self.client.aclose()

            self.client = None


    async def chat_json(
        self,
        model: str,
        system: str,
        user: str,
        label: str = "",
    ) -> dict | None:
        """Один запрос к /api/chat с format=json. Возвращает разобранный
        объект или None, если модель не ответила или ответ не разбирается."""

        payload = {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        if self._think_supported:
            payload["think"] = self.think


        content = await self._post_chat(payload, label)

        if content is None:
            return None


        try:

            return json.loads(content)

        except (json.JSONDecodeError, TypeError):

            logger.error(
                f"LLM returned unparseable JSON"
                f"{f' ({label})' if label else ''}: {str(content)[:200]}"
            )

            return None


    async def _post_chat(
        self,
        payload: dict,
        label: str,
    ) -> str | None:

        try:

            async with self.semaphore:

                response = await self.client.post(
                    "/api/chat",
                    json=payload,
                )

            if (
                response.status_code == 400
                and "think" in payload
            ):

                logger.info(
                    "Model does not accept the think flag, "
                    "retrying without it"
                )

                self._think_supported = False

                payload.pop("think")

                async with self.semaphore:

                    response = await self.client.post(
                        "/api/chat",
                        json=payload,
                    )

            response.raise_for_status()

            return response.json()["message"]["content"]

        except Exception as e:

            logger.error(
                f"LLM call failed{f' ({label})' if label else ''}: {e}"
            )

            return None


    async def embed(
        self,
        model: str,
        texts: list[str],
    ) -> list[list[float]]:
        """Эмбеддинги, выровненные 1:1 со входом. Режет на батчи, потому
        что Ollama не выдерживает больших."""

        prepared = [
            text[:EMBED_MAX_CHARS]
            for text in texts
        ]

        vectors: list[list[float]] = []

        for start in range(0, len(prepared), EMBED_BATCH_SIZE):

            batch = prepared[start:start + EMBED_BATCH_SIZE]

            async with self.semaphore:

                response = await self.client.post(
                    "/api/embed",
                    json={"model": model, "input": batch},
                    timeout=self.embed_timeout,
                )

            response.raise_for_status()

            vectors.extend(
                response.json()["embeddings"]
            )


        return vectors
