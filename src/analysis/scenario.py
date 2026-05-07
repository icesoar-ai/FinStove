import numpy as np
import pandas as pd

from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal


class ScenarioAnalyzer(AbstractAnalyzer):
    """Scenario analysis: bull/base/bear cases, stress tests, sensitivity."""

    dimension = Dimension.SCENARIO

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        prices = context.price_data
        financials = context.financials or {}
        signals: list[Signal] = []
        details: dict = {}

        if prices is not None and not prices.empty:
            signals.extend(self._historical_scenarios(prices))
            details.update(self._price_sensitivity(prices))

        if not signals:
            return AnalysisResult(
                dimension=self.dimension, score=0, confidence=0.2,
                signals=[], summary="情景分析数据不足", warnings=["缺少足够数据进行情景推演"],
            )

        bullish = sum(s.strength for s in signals if s.direction == "bullish")
        bearish = sum(s.strength for s in signals if s.direction == "bearish")
        total = bullish + bearish
        score = 2 * (bullish - bearish) / total if total > 0 else 0
        confidence = min(0.5, len(signals) / 5)

        return AnalysisResult(
            dimension=self.dimension,
            score=round(score, 2),
            confidence=round(confidence, 2),
            signals=signals,
            summary=f"情景分析评分 {score:+.1f}",
            details=details,
        )

    def _historical_scenarios(self, prices: pd.DataFrame) -> list[Signal]:
        signals = []
        close = prices["close"].astype(float)
        if len(close) < 252:
            return signals

        current = close.iloc[-1]
        high_52w = close.tail(252).max()
        low_52w = close.tail(252).min()

        # Bull case: return to 52w high
        bull_upside = (high_52w / current - 1) * 100
        # Bear case: return to 52w low
        bear_downside = (current / low_52w - 1) * 100 if low_52w > 0 else 0

        if bull_upside > 20:
            signals.append(Signal(f"乐观空间 {bull_upside:.0f}%", "bullish", 0.4, f"回到52周高 {high_52w:.0f} 有 {bull_upside:.0f}% 空间"))
        if bear_downside > 20:
            signals.append(Signal(f"下行风险 {bear_downside:.0f}%", "bearish", 0.4, f"跌回52周低 {low_52w:.0f} 需跌 {bear_downside:.0f}%"))

        # Reversal scenario
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
        if ma200 and current < ma200:
            signals.append(Signal("反转情景: 均值回归向上", "bullish", 0.3, f"当前低于200日均线"))

        return signals

    def _price_sensitivity(self, prices: pd.DataFrame) -> dict:
        """Simple sensitivity analysis based on volatility."""
        close = prices["close"].astype(float)
        returns = close.pct_change().dropna().tail(252)
        sigma = returns.std() if len(returns) > 0 else 0.02

        current = close.iloc[-1]
        return {
            "current_price": round(float(current), 2),
            "daily_sigma": round(float(sigma), 4),
            "bull_1sigma_1m": round(float(current * (1 + sigma * np.sqrt(21))), 2),
            "bear_1sigma_1m": round(float(current * (1 - sigma * np.sqrt(21))), 2),
            "bull_2sigma_3m": round(float(current * (1 + 2 * sigma * np.sqrt(63))), 2),
            "bear_2sigma_3m": round(float(current * (1 - 2 * sigma * np.sqrt(63))), 2),
        }
