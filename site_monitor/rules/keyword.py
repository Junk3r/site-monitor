import re

from datetime import datetime, timezone

from site_monitor.rules.diff import new_lines
from site_monitor.rules.models import OpportunityEvent


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


    def check(
        self,
        site: str,
        url: str,
        old_content: str,
        new_content: str,
    ) -> OpportunityEvent | None:

        lines = new_lines(
            old_content,
            new_content
        )

        matched_lines = []
        matched_keywords = set()
        matched_locations = set()

        for line in lines:

            lowered = line.lower()

            if any(
                pattern.search(lowered)
                for _, pattern in self.exclude
            ):
                continue

            hits = [
                keyword
                for keyword, pattern in self.include
                if pattern.search(lowered)
            ]

            if not hits:
                continue

            matched_lines.append(line)
            matched_keywords.update(hits)

            matched_locations.update(
                keyword
                for keyword, pattern in self.locations
                if pattern.search(lowered)
            )


        if not matched_lines:
            return None


        confidence = BASE_CONFIDENCE

        if matched_locations or not self.locations:
            confidence += LOCATION_BONUS


        return OpportunityEvent(
            site=site,
            url=url,
            title=matched_lines[0],
            matched_keywords=sorted(matched_keywords),
            matched_lines=matched_lines,
            matched_locations=sorted(matched_locations),
            confidence=confidence,
            detected_at=datetime.now(timezone.utc),
        )
