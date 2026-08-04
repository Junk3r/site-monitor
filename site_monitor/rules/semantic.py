from loguru import logger

from site_monitor.rules.keyword import compile_keywords
from site_monitor.rules.models import Match
from site_monitor.schemas.vacancy import Vacancy


AI_CONFIDENCE = 0.6

CLASSIFY_BATCH_SIZE = 50

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

    if not norm_a or not norm_b:
        return 0.0

    return dot / (norm_a * norm_b)


class SemanticRule:

    def __init__(
        self,
        client,
        model: str,
        skip_keywords: list[str],
        exclude: list[str],
        embedding_model: str = "",
    ):
        self.client = client
        self.model = model
        self.embedding_model = embedding_model
        self.skip = compile_keywords(skip_keywords)
        self.exclude = compile_keywords(exclude)
        self._anchor_vectors: list[list[float]] | None = None


    async def match(
        self,
        site: str,
        vacancies: list[Vacancy],
    ) -> list[Match]:

        candidates = self._candidates(vacancies)

        if not candidates:
            return []


        if self.embedding_model:

            candidates = await self._prefilter(
                site,
                candidates
            )

            if not candidates:
                return []


        matched = await self._classify(
            site,
            candidates
        )

        return [
            Match(
                vacancy=vacancy,
                keywords=["AI: semantic match"],
                confidence=AI_CONFIDENCE,
                via="ai",
            )
            for vacancy in matched
        ]


    def _candidates(
        self,
        vacancies: list[Vacancy],
    ) -> list[Vacancy]:

        result = []

        for vacancy in vacancies:

            line = vacancy.as_line().strip()

            if not (
                MIN_LINE_LENGTH
                <= len(line)
                <= MAX_LINE_LENGTH
            ):
                continue

            lowered = line.lower()

            # уже отдано KeywordRule
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

            result.append(vacancy)

        return result


    async def _prefilter(
        self,
        site: str,
        candidates: list[Vacancy],
    ) -> list[Vacancy]:

        try:

            if self._anchor_vectors is None:

                self._anchor_vectors = await self.client.embed(
                    self.embedding_model,
                    EMBED_ANCHORS,
                )

            vectors = await self.client.embed(
                self.embedding_model,
                [
                    vacancy.as_line()
                    for vacancy in candidates
                ],
            )

        except Exception as e:

            logger.error(
                f"Embedding prefilter for {site} failed: {e}, "
                f"passing all candidates to LLM"
            )

            return candidates


        survivors = []

        for vacancy, vector in zip(candidates, vectors):

            similarity = max(
                cosine(vector, anchor)
                for anchor in self._anchor_vectors
            )

            if similarity >= EMBED_THRESHOLD:
                survivors.append(vacancy)


        if survivors:

            logger.info(
                f"Embedding prefilter for {site}: "
                f"{len(candidates)} -> {len(survivors)} lines"
            )

        return survivors


    async def _classify(
        self,
        site: str,
        candidates: list[Vacancy],
    ) -> list[Vacancy]:
        """Раньше список обрезался до 50 строк и остаток молча терялся.
        Теперь длинные списки идут батчами."""

        matched = []

        for start in range(0, len(candidates), CLASSIFY_BATCH_SIZE):

            batch = candidates[start:start + CLASSIFY_BATCH_SIZE]

            numbered = "\n".join(
                f"{index + 1}. {vacancy.as_line()}"
                for index, vacancy in enumerate(batch)
            )

            data = await self.client.chat_json(
                model=self.model,
                system=SYSTEM_PROMPT,
                user=numbered,
                label=f"classify {site}",
            )

            if not data:
                continue

            numbers = data.get("matches", [])

            if not isinstance(numbers, list):
                continue

            matched.extend(
                batch[number - 1]
                for number in numbers
                if isinstance(number, int)
                and 1 <= number <= len(batch)
            )


        return matched
