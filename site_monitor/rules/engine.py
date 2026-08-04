from site_monitor.rules.models import Match
from site_monitor.schemas.vacancy import Vacancy


class RuleEngine:
    """Ключевые слова идут первыми и дёшево; в LLM попадает только то,
    что они не поймали."""

    def __init__(
        self,
        keyword_rule=None,
        semantic_rule=None,
    ):
        self.keyword_rule = keyword_rule
        self.semantic_rule = semantic_rule


    async def evaluate(
        self,
        site: str,
        vacancies: list[Vacancy],
    ) -> list[Match]:

        if not vacancies:
            return []


        matches = []

        matched_ids = set()

        if self.keyword_rule:

            matches = self.keyword_rule.match(vacancies)

            matched_ids = {
                id(match.vacancy)
                for match in matches
            }


        if self.semantic_rule:

            rest = [
                vacancy
                for vacancy in vacancies
                if id(vacancy) not in matched_ids
            ]

            matches.extend(
                await self.semantic_rule.match(
                    site,
                    rest
                )
            )


        # одна и та же вакансия может прийти из двух источников на сайте
        unique = {}

        for match in matches:

            unique.setdefault(
                match.vacancy.fingerprint,
                match
            )

        return list(unique.values())
