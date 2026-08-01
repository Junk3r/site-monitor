from datetime import datetime, timezone

from site_monitor.rules.diff import new_lines
from site_monitor.rules.models import OpportunityEvent


class KeywordRule:

    def __init__(
        self,
        include: list[str],
        exclude: list[str]
    ):
        self.include = [
            keyword.lower()
            for keyword in include
        ]

        self.exclude = [
            keyword.lower()
            for keyword in exclude
        ]


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

        for line in lines:

            lowered = line.lower()

            if any(
                keyword in lowered
                for keyword in self.exclude
            ):
                continue

            hits = [
                keyword
                for keyword in self.include
                if keyword in lowered
            ]

            if hits:
                matched_lines.append(line)
                matched_keywords.update(hits)


        if not matched_lines:
            return None


        return OpportunityEvent(
            site=site,
            url=url,
            title=matched_lines[0],
            matched_keywords=sorted(matched_keywords),
            matched_lines=matched_lines,
            confidence=1.0,
            detected_at=datetime.now(timezone.utc),
        )
