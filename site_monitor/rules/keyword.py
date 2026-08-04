import re

from site_monitor.rules.models import Match
from site_monitor.schemas.vacancy import Vacancy


BASE_CONFIDENCE = 0.7

LOCATION_BONUS = 0.3


def compile_keywords(
    keywords: list[str]
) -> list[tuple[str, re.Pattern]]:

    return [
        (
            keyword.lower(),
            re.compile(
                r"\b" + re.escape(keyword.lower()) + r"\b"
            ),
        )
        for keyword in keywords
    ]


class KeywordRule:

    def __init__(
        self,
        include: list[str],
        exclude: list[str],
        locations: list[str] | None = None,
    ):
        self.include = compile_keywords(include)
        self.exclude = compile_keywords(exclude)
        self.locations = compile_keywords(locations or [])


    def match(
        self,
        vacancies: list[Vacancy],
    ) -> list[Match]:

        matches = []

        for vacancy in vacancies:

            match = self.check(vacancy)

            if match:
                matches.append(match)

        return matches


    def check(
        self,
        vacancy: Vacancy,
    ) -> Match | None:

        line = vacancy.as_line().lower()

        if any(
            pattern.search(line)
            for _, pattern in self.exclude
        ):
            return None


        hits = [
            keyword
            for keyword, pattern in self.include
            if pattern.search(line)
        ]

        if not hits:
            return None


        # локация теперь отдельное поле, а не соседняя строка текста —
        # бонус достаётся только тем, у кого география действительно совпала
        haystack = (
            vacancy.location.lower()
            or line
        )

        matched_locations = [
            keyword
            for keyword, pattern in self.locations
            if pattern.search(haystack)
        ]

        confidence = BASE_CONFIDENCE

        if matched_locations or not self.locations:
            confidence += LOCATION_BONUS


        return Match(
            vacancy=vacancy,
            keywords=sorted(hits),
            confidence=confidence,
            via="keyword",
        )
