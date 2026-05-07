from __future__ import annotations

import numpy as np
import pandas as pd

from .base import ValuationResult
from .ddm import DDMValuation
from .epv import EPVValuation
from .fcff import FCFFValuation
from .fcfe import FCFEValuation
from .fcf_quality import FCFQualityCheck
from .graham import GrahamValuation
from .health import FinancialHealthCheck
from .multiples import MultiplesValuation
from .ncav import NCAVValuation
from .residual_income import ResidualIncomeValuation


class ValuationAggregator:
    """Run all valuation methods and aggregate results."""

    def __init__(self):
        self._methods = [
            FCFFValuation(),
            FCFEValuation(),
            DDMValuation(),
            GrahamValuation(),
            EPVValuation(),
            NCAVValuation(),
            ResidualIncomeValuation(),
            MultiplesValuation(),
            FCFQualityCheck(),
            FinancialHealthCheck(),
        ]

    def evaluate_all(self, financials: dict, market_data: pd.DataFrame | None = None) -> list[ValuationResult]:
        results = []
        for method in self._methods:
            try:
                result = method.evaluate(financials, market_data)
                results.append(result)
            except Exception as e:
                results.append(ValuationResult(
                    method=method.name, fair_value=0, value_low=0, value_high=0,
                    confidence=0, warnings=[f"方法异常: {e}"],
                ))
        return results

    def aggregate(self, results: list[ValuationResult]) -> dict:
        """Produce aggregate summary from all valuation results."""
        fair_values = [r.fair_value for r in results if r.fair_value > 0 and r.confidence >= 0.3]
        all_warnings = []
        for r in results:
            all_warnings.extend(r.warnings)

        if not fair_values:
            return {
                "fair_value_median": None,
                "fair_value_range": (None, None),
                "method_count": len(results),
                "methods_with_value": 0,
                "agreement": "low",
                "warnings": list(set(all_warnings)),
                "details": results,
            }

        median = np.median(fair_values)
        low = np.percentile(fair_values, 25)
        high = np.percentile(fair_values, 75)

        # Agreement check: if range is narrow relative to median
        spread = (high - low) / median if median > 0 else 1
        if spread < 0.3:
            agreement = "high"
        elif spread < 0.6:
            agreement = "medium"
        else:
            agreement = "low"

        return {
            "fair_value_median": round(median, 2),
            "fair_value_range": (round(low, 2), round(high, 2)),
            "method_count": len(results),
            "methods_with_value": len(fair_values),
            "agreement": agreement,
            "warnings": list(set(all_warnings)),
            "details": results,
        }
