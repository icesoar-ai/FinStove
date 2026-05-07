from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from ..data.base import Dimension
from ..data.models import Ticker, FinancialReport, NewsItem


@dataclass
class Signal:
    name: str
    direction: str        # "bullish", "bearish", "neutral"
    strength: float       # 0.0 to 1.0
    description: str = ""


@dataclass
class AnalysisContext:
    ticker: Ticker
    price_data: Optional[pd.DataFrame] = None
    financials: Optional[dict] = None
    macro_data: Optional[dict] = None
    flow_data: Optional[pd.DataFrame] = None
    news_data: Optional[list[NewsItem]] = None
    lookback_days: int = 250


@dataclass
class AnalysisResult:
    dimension: Dimension
    score: float              # -2.0 to +2.0
    confidence: float         # 0.0 to 1.0
    signals: list[Signal] = field(default_factory=list)
    summary: str = ""
    details: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class AbstractAnalyzer(ABC):
    dimension: Dimension

    @abstractmethod
    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        ...
