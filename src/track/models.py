from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TrackRecord:
    id: str
    ticker: str
    timestamp: datetime
    composite_score: float
    tier: str
    dimension_scores: dict = field(default_factory=dict)
    current_price: Optional[float] = None
    notes: str = ""


@dataclass
class ReviewResult:
    record: TrackRecord
    elapsed_days: int
    current_price: float
    price_return: float
    was_correct: Optional[bool] = None
