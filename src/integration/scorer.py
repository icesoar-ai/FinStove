from __future__ import annotations

from src.analysis.base import AnalysisResult
from src.data.base import Dimension


DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "long_term": {
        Dimension.FUNDAMENTAL.value: 0.40,
        Dimension.MACRO.value: 0.20,
        Dimension.POLICY.value: 0.15,
        Dimension.TECHNICAL.value: 0.10,
        Dimension.CORRELATION.value: 0.05,
        Dimension.CAPITAL_FLOW.value: 0.05,
        Dimension.SENTIMENT.value: 0.05,
    },
    "short_term": {
        Dimension.TECHNICAL.value: 0.35,
        Dimension.CAPITAL_FLOW.value: 0.25,
        Dimension.SENTIMENT.value: 0.20,
        Dimension.MACRO.value: 0.10,
        Dimension.CORRELATION.value: 0.05,
        Dimension.FUNDAMENTAL.value: 0.03,
        Dimension.POLICY.value: 0.02,
    },
}

THRESHOLDS = {"strong_buy": 1.0, "buy": 0.3, "hold": -0.3, "sell": -1.0}


class WeightedScorer:
    def __init__(self, context: str = "long_term", weights: dict[str, float] | None = None):
        self.context = context
        self.weights = weights or DEFAULT_WEIGHTS.get(context, DEFAULT_WEIGHTS["long_term"])

    def score(self, results: list[AnalysisResult]) -> dict:
        """Compute weighted composite score from analysis results."""
        composite = 0.0
        total_weight = 0.0
        dimension_scores: dict[str, float] = {}
        conflicts: list[str] = []

        for r in results:
            w = self.weights.get(r.dimension.value, 0.05)
            if w > 0 and r.confidence > 0:
                composite += r.score * w * r.confidence
                total_weight += w * r.confidence
                dimension_scores[r.dimension.value] = r.score

        if total_weight > 0:
            composite /= total_weight

        # Detect conflicts: opposite signals with decent confidence
        bull_dims = [r.dimension.value for r in results if r.score > 0.5 and r.confidence > 0.3]
        bear_dims = [r.dimension.value for r in results if r.score < -0.5 and r.confidence > 0.3]
        if bull_dims and bear_dims:
            conflicts.append(f"多空分歧: 看涨维度 {bull_dims} vs 看跌维度 {bear_dims}")

        # Tier
        tier = self._tier(composite)

        return {
            "composite_score": round(composite, 2),
            "tier": tier,
            "dimension_scores": dimension_scores,
            "active_dimensions": len([r for r in results if r.confidence > 0]),
            "conflicts": conflicts,
            "context": self.context,
        }

    def _tier(self, score: float) -> str:
        if score >= THRESHOLDS["strong_buy"]:
            return "STRONG_BUY"
        elif score >= THRESHOLDS["buy"]:
            return "BUY"
        elif score >= THRESHOLDS["hold"]:
            return "HOLD"
        elif score >= THRESHOLDS["sell"]:
            return "SELL"
        else:
            return "STRONG_SELL"
