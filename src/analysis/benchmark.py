import numpy as np
import pandas as pd

from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal


class BenchmarkAnalyzer(AbstractAnalyzer):
    """Benchmark comparison: index relative performance, risk-adjusted returns."""

    dimension = Dimension.BENCHMARK

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        prices = context.price_data
        md = context.macro_data or {}
        signals: list[Signal] = []

        signals.extend(self._index_comparison(prices, md))
        signals.extend(self._risk_free_comparison(md))

        if not signals:
            return AnalysisResult(
                dimension=self.dimension, score=0, confidence=0.2,
                signals=[], summary="基准对比数据不足",
            )

        bullish = sum(s.strength for s in signals if s.direction == "bullish")
        bearish = sum(s.strength for s in signals if s.direction == "bearish")
        total = bullish + bearish
        score = 2 * (bullish - bearish) / total if total > 0 else 0
        confidence = min(0.6, len(signals) / 4)

        edge = "优于基准" if score > 0.2 else ("弱于基准" if score < -0.2 else "与基准持平")
        return AnalysisResult(
            dimension=self.dimension,
            score=round(score, 2),
            confidence=round(confidence, 2),
            signals=signals,
            summary=f"基准对比: {edge}，评分 {score:+.1f}",
            details={},
        )

    def _index_comparison(self, prices, md: dict) -> list[Signal]:
        signals = []
        if prices is None or prices.empty:
            return signals

        benchmark_returns = md.get("benchmark_returns")
        if benchmark_returns is None:
            return signals

        stock_ret = prices["close"].pct_change().dropna().tail(252).sum() if len(prices) >= 252 else 0
        bench_ret = float(benchmark_returns) if isinstance(benchmark_returns, (int, float)) else 0

        excess = stock_ret - bench_ret
        if excess > 0.1:
            signals.append(Signal("显著跑赢指数", "bullish", 0.5, f"年超额收益 {excess:.1%}"))
        elif excess > 0:
            signals.append(Signal("小幅跑赢指数", "bullish", 0.3, f"年超额收益 {excess:.1%}"))
        elif excess > -0.1:
            signals.append(Signal("小幅跑输指数", "bearish", 0.3, f"年超额收益 {excess:.1%}"))
        else:
            signals.append(Signal("显著跑输指数", "bearish", 0.5, f"年超额收益 {excess:.1%}"))

        return signals

    def _risk_free_comparison(self, md: dict) -> list[Signal]:
        signals = []
        rf_rate = md.get("risk_free_rate", md.get("bond_10y"))
        if rf_rate is None:
            # Assume 2.5% for China, 4% for US
            rf_rate = 0.03

        rf_val = float(rf_rate) if isinstance(rf_rate, (int, float, str)) else 0.03
        earnings_yield = md.get("earnings_yield", md.get("fcf_yield"))

        if earnings_yield:
            ey = float(earnings_yield) if isinstance(earnings_yield, (int, float, str)) else 0
            spread = ey - rf_val
            if spread > 0.05:
                signals.append(Signal("股债性价比极佳", "bullish", 0.6, f"盈利收益率 {ey:.1%} vs 国债 {rf_val:.1%}"))
            elif spread > 0.02:
                signals.append(Signal("股债性价比好", "bullish", 0.4, f"盈利收益率 {ey:.1%} vs 国债 {rf_val:.1%}"))
            elif spread > 0:
                signals.append(Signal("股债性价比一般", "neutral", 0.3, f"盈利收益率 {ey:.1%} vs 国债 {rf_val:.1%}"))
            else:
                signals.append(Signal("股债倒挂", "bearish", 0.5, f"盈利收益率 {ey:.1%} vs 国债 {rf_val:.1%}"))

        return signals
