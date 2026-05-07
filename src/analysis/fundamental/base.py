from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValuationResult:
    method: str
    fair_value: float         # per-share fair value estimate
    value_low: float          # bear case
    value_high: float         # bull case
    confidence: float         # 0.0 to 1.0
    assumptions: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class ValuationMethod(ABC):
    name: str

    @abstractmethod
    def evaluate(self, financials: dict, market_data: pd.DataFrame | None = None) -> ValuationResult:
        ...


# Re-exported for convenience
__all__ = ["ValuationResult", "ValuationMethod"]
