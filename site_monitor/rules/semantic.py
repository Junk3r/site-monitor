import asyncio
import json

from datetime import datetime, timezone

import httpx

from loguru import logger

from site_monitor.rules.diff import new_lines
from site_monitor.rules.keyword import compile_keywords
from site_monitor.rules.models import OpportunityEvent


AI_CONFIDENCE = 0.6

MAX_BATCH_LINES = 50

MIN_LINE_LENGTH = 5

MAX_LINE_LENGTH = 120

EMBED_THRESHOLD = 0.68

EMBED_ANCHORS = [
    "Account Manager",
    "Customer Success Manager",
    "Business Development Manager",
    "Partnerships Manager",
    "Sales Manager",
    "Client Relations Manager",
]

# Ollama processes requests one at a time; parallel LLM calls
# from concurrent site checks pile up and time out
LLM_SEMAPHORE = asyncio.Semaphore(1)

SYSTEM_PROMPT = (
    "You classify lines scraped from careers pages. "
    "The candidate seeks roles like: Account Manager, Customer Success, "
    "Business Development, Partnerships, Sales, Client Relations, CRM, "
    "Commercial roles. Remote or Europe-based positions are preferred "
    "but location is optional.\n"
    "Return JSON: {\"matches\": [line numbers that are job vacancy "
    "titles matching this profile]}.\n"
    "Exclude: technical roles (developer, engineer, QA, designer, "
    "data, devops), cookie banners, navigation text, marketing copy, "
    "anything that is not a job vacancy title. Exclude administrative "
    "roles (office manager, accountant, payroll, HR)."
)


def cosine(a: list[float], b: list[float]) -> float:

    dot = sum(x * y for x, y in zip(a, b))

    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    return dot / (norm_a * norm_b)


class SemanticRule:

    def __init__(
        self,
        base_url: str,
        model: str,
        skip_keywords: list[str],
        exclude: list[str],
        embedding_model: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embedding_model = embedding_model
        self.skip = compile_keywords(skip_keywords)
        self.exclude = compile_keywords(exclude)
        self._anchor_vectors: list[list[float]] | None = None


    async def check(
        self,
        site: str,
        url: str,
        old_content: str,
        new_content: str,
    ) -> OpportunityEvent | None:

        candidates = self._candidates(
            old_content,
            new_content
        )

        if not candidates:
            return None


        if self.embedding_model:

            candidates = await self._prefilter(
                site,
                candidates
            )

            if not candidates:
                return None


        if len(candidates) > MAX_BATCH_LINES:

            logger.warning(
                f"AI check for {site}: {len(candidates)} candidate "
                f"lines, truncating to {MAX_BATCH_LINES}"
            )

            candidates = candidates[:MAX_BATCH_LINES]


        matched_lines = await self._classify(
            site,
            candidates
        )

        if not matched_lines:
            return None


        return OpportunityEvent(
            site=site,
            url=url,
            title=matched_lines[0],
            matched_keywords=["AI: semantic match"],
            matched_lines=matched_lines,
            confidence=AI_CONFIDENCE,
            detected_at=datetime.now(timezone.utc),
        )


    def _candidates(
        self,
        old_content: str,
        new_content: str,
    ) -> list[str]:

        lines = new_lines(
            old_content,
            new_content
        )

        result = []

        for line in lines:

            stripped = line.strip()

            if not (
                MIN_LINE_LENGTH
                <= len(stripped)
                <= MAX_LINE_LENGTH
            ):
                continue

            lowered = stripped.lower()

            # already alerted by KeywordRule
            if any(
                pattern.search(lowered)
                for _, pattern in self.skip
            ):
                continue

            if any(
                pattern.search(lowered)
                for _, pattern in self.exclude
            ):
                continue

            result.append(stripped)

        return result


    async def _embed(
        self,
        texts: list[str]
    ) -> list[list[float]]:

        async with httpx.AsyncClient(
            timeout=120
        ) as client:

            response = await client.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": self.embedding_model,
                    "input": texts,
                },
            )

            response.raise_for_status()

            return response.json()["embeddings"]


    async def _prefilter(
        self,
        site: str,
        candidates: list[str],
    ) -> list[str]:

        try:

            if self._anchor_vectors is None:

                self._anchor_vectors = await self._embed(
                    EMBED_ANCHORS
                )

            vectors = await self._embed(
                candidates
            )

        except Exception as e:

            logger.error(
                f"Embedding prefilter for {site} failed: {e}, "
                f"passing all candidates to LLM"
            )

            return candidates


        survivors = []

        for line, vector in zip(candidates, vectors):

            similarity = max(
                cosine(vector, anchor)
                for anchor in self._anchor_vectors
            )

            if similarity >= EMBED_THRESHOLD:
                survivors.append(line)


        if survivors:

            logger.info(
                f"Embedding prefilter for {site}: "
                f"{len(candidates)} -> {len(survivors)} lines"
            )

        return survivors


    async def _classify(
        self,
        site: str,
        candidates: list[str],
    ) -> list[str]:

        numbered = "\n".join(
            f"{i + 1}. {line}"
            for i, line in enumerate(candidates)
        )

        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": numbered},
            ],
        }

        try:

            async with LLM_SEMAPHORE:

                async with httpx.AsyncClient(
                    timeout=180
                ) as client:

                    response = await client.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                    )

                    response.raise_for_status()

                    content = response.json()["message"]["content"]

        except Exception as e:

            logger.error(
                f"AI check for {site} failed: {e}"
            )

            return []


        try:

            numbers = json.loads(content).get("matches", [])

        except (json.JSONDecodeError, AttributeError):

            logger.error(
                f"AI check for {site}: unparseable response: "
                f"{content[:200]}"
            )

            return []


        return [
            candidates[n - 1]
            for n in numbers
            if isinstance(n, int) and 1 <= n <= len(candidates)
        ]
