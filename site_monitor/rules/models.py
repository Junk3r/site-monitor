from dataclasses import dataclass, field

from site_monitor.schemas.vacancy import Vacancy


@dataclass
class Match:
    """Вакансия, которую правило сочло подходящей."""

    vacancy: Vacancy
    keywords: list[str] = field(default_factory=list)
    confidence: float = 0.0
    via: str = "keyword"
