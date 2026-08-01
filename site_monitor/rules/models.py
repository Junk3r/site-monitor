from dataclasses import dataclass
from datetime import datetime


@dataclass
class OpportunityEvent:
    site: str
    url: str
    title: str
    matched_keywords: list[str]
    matched_lines: list[str]
    confidence: float
    detected_at: datetime