from dataclasses import dataclass, field
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
    matched_locations: list[str] = field(default_factory=list)