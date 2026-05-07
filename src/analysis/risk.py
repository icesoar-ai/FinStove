import numpy as np
import pandas as pd

from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal


class RiskAnalyzer(AbstractAnalyzer):
    """Risk analysis: VaR, max drawdown, volatility, liquidity risk."""

    dimension = Dimension.RISK

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        prices = context.price_data
        if prices is None or prices.empty:
            return AnalysisResult(
                dimension=self.dimension, score=0, confidence=0, signals=[],
                summary="无价格数据", warnings=["缺少价格数据"],
            )

        close = prices["close"].astype(float)
        signals: list[Signal] = []

        signals.extend(self._var_cvar(close))
        signals.extend(self._max_drawdown(close))
        signals.extend(self._volatility(close))
        signals.extend(self._liquidity(prices, close))

        if not signals:
            return AnalysisResult(dimension=self.dimension, score=0, confidence=0.3, signals=[], summary="无法计算风险指标")

        bearish = sum(s.strength for s in signals if s.direction == "bearish")
        neutral = sum(s.strength for s in signals if s.direction == "neutral")
        total = bearish + neutral + sum(s.strength for s in signals if s.direction == "bullish")

        score = -2 * bearish / total if total > 0 else 0
        confidence = min(0.8, len(signals) / 6)

        risk_level = "高风险" if score < -0.6 else ("中等风险" if score < -0.2 else "低风险")
        return AnalysisResult(
            dimension=self.dimension,
            score=round(score, 2),
            confidence=round(confidence, 2),
            signals=signals,
            summary=f"风险评估: {risk_level}，评分 {score:+.1f}",
            details={"signal_count": len(signals)},
        )

    def _var_cvar(self, close: pd.Series) -> list[Signal]:
        signals = []
        if len(close) < 60:
            return signals

        returns = close.pct_change().dropna().tail(252)  # ~1 year
        if len(returns) < 50:
            return signals

        var_95 = np.percentile(returns, 5)
        cvar_95 = returns[returns <= var_95].mean()

        signals.append(Signal(
            f"VaR(95%)={var_95:.2%}", "neutral", 0.4,
            f"单日最差5%情况下跌 {abs(var_95):.2%}，CVaR={cvar_95:.2%}"
        ))

        if var_95 < -0.05:
            signals.append(Signal("尾部风险偏高", "bearish", 0.5, f"5% VaR={var_95:.2%}"))
        elif var_95 < -0.03:
            signals.append(Signal("尾部风险可控", "neutral", 0.3, f"5% VaR={var_95:.2%}"))
        else:
            signals.append(Signal("尾部风险低", "neutral", 0.2, f"5% VaR={var_95:.2%}"))

        return signals

    def _max_drawdown(self, close: pd.Series) -> list[Signal]:
        signals = []
        if len(close) < 60:
            return signals

        cumulative_max = close.expanding().max()
        drawdown = (close - cumulative_max) / cumulative_max
        max_dd = drawdown.min()
        current_dd = drawdown.iloc[-1]

        signals.append(Signal(
            f"历史最大回撤 {max_dd:.1%}", "neutral", 0.4,
            f"当前回撤 {current_dd:.1%}" if current_dd < 0 else "当前处于高点"
        ))

        if max_dd < -0.5:
            signals.append(Signal("历史回撤极大", "bearish", 0.6, f"曾回调 {abs(max_dd):.0%}"))
        elif max_dd < -0.3:
            signals.append(Signal("历史回撤较大", "bearish", 0.4, f"曾回调 {abs(max_dd):.0%}"))

        if current_dd < -0.2:
            signals.append(Signal("当前回撤较深", "bullish", 0.3, f"已从高点回落 {abs(current_dd):.0%}"))

        return signals

    def _volatility(self, close: pd.Series) -> list[Signal]:
        signals = []
        if len(close) < 20:
            return signals

        returns = close.pct_change().dropna().tail(60)
        if len(returns) < 20:
            return signals

        annual_vol = returns.std() * np.sqrt(252)

        if annual_vol > 0.6:
            signals.append(Signal(f"极高波动 {annual_vol:.1%}年化", "bearish", 0.6, "波动率极高"))
        elif annual_vol > 0.4:
            signals.append(Signal(f"高波动 {annual_vol:.1%}年化", "bearish", 0.4, "波动率偏高"))
        elif annual_vol > 0.2:
            signals.append(Signal(f"中等波动 {annual_vol:.1%}年化", "neutral", 0.3, "波动率正常"))
        else:
            signals.append(Signal(f"低波动 {annual_vol:.1%}年化", "neutral", 0.3, "波动率偏低"))

        return signals

    def _liquidity(self, prices: pd.DataFrame, close: pd.Series) -> list[Signal]:
        signals = []
        if "volume" not in prices.columns or len(prices) < 20:
            return signals

        vol = prices["volume"].tail(60)
        avg_vol = vol.mean()
        latest_vol = vol.iloc[-1]
        ratio = latest_vol / avg_vol if avg_vol > 0 else 1

        if ratio < 0.3:
            signals.append(Signal("流动性枯竭", "bearish", 0.5, f"成交量仅均量{ratio:.0%}"))
        elif ratio < 0.5:
            signals.append(Signal("流动性偏低", "bearish", 0.3, f"成交量萎缩至{ratio:.0%}"))

        # Amihud illiquidity (simplified)
        if len(close) >= 20:
            illiq = (abs(close.pct_change()) / (prices["volume"] * close)).tail(60).mean()
            if illiq > 0:
                signals.append(Signal(f"非流动性指标", "neutral", 0.2, f"市场冲击成本参考"))

        return signals
