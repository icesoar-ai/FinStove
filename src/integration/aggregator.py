from __future__ import annotations

from dataclasses import dataclass, field

from src.analysis.base import AnalysisResult


@dataclass
class AggregatedJudgment:
    ticker: str
    composite_score: float
    tier: str
    intrinsic_value_range: tuple[float | None, float | None] = (None, None)
    price_reasonableness: str = "N/A"
    trend_direction: str = "N/A"
    risk_level: str = "N/A"
    benchmark_edge: str = "N/A"
    scenarios: dict = field(default_factory=dict)
    dimension_scores: dict = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)


class Aggregator:
    """Aggregate scored results into structured judgment."""

    def aggregate(self, ticker: str, score_result: dict, results: list[AnalysisResult]) -> AggregatedJudgment:
        j = AggregatedJudgment(
            ticker=ticker,
            composite_score=score_result["composite_score"],
            tier=score_result["tier"],
            dimension_scores=score_result["dimension_scores"],
            conflicts=score_result.get("conflicts", []),
        )

        for r in results:
            j.summary_lines.append(f"[{r.dimension.value}] {r.summary}")

            if r.dimension.value == "fundamental" and r.details:
                fv = r.details.get("fair_value_median") or r.details.get("fair_value")
                if fv:
                    j.intrinsic_value_range = (float(fv) * 0.8, float(fv) * 1.2)

            if r.dimension.value == "technical":
                if r.score > 0.3:
                    j.trend_direction = "上升趋势"
                elif r.score < -0.3:
                    j.trend_direction = "下降趋势"
                else:
                    j.trend_direction = "震荡"

            if r.dimension.value == "risk":
                if r.score < -0.5:
                    j.risk_level = "高"
                elif r.score < -0.2:
                    j.risk_level = "中"
                else:
                    j.risk_level = "低"

            if r.dimension.value == "benchmark":
                if r.score > 0.2:
                    j.benchmark_edge = "优于"
                elif r.score < -0.2:
                    j.benchmark_edge = "弱于"
                else:
                    j.benchmark_edge = "持平"

            if r.dimension.value == "scenario":
                j.scenarios = r.details

        return j
