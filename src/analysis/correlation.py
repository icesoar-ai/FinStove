import numpy as np
import pandas as pd

from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal


class CorrelationAnalyzer(AbstractAnalyzer):
    """Cross-market correlation analysis: commodity-FX, bond-stock, safe haven, risk on/off."""

    dimension = Dimension.CORRELATION

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        md = context.macro_data or {}
        prices = context.price_data
        signals: list[Signal] = []

        signals.extend(self._gold_signal(md))
        signals.extend(self._dxy_signal(md))
        signals.extend(self._vix_signal(md, prices))

        if not signals:
            return AnalysisResult(
                dimension=self.dimension, score=0, confidence=0.2,
                signals=[], summary="跨市场数据不足", warnings=["缺少跨市场数据"],
            )

        bullish = sum(s.strength for s in signals if s.direction == "bullish")
        bearish = sum(s.strength for s in signals if s.direction == "bearish")
        total = bullish + bearish
        score = 2 * (bullish - bearish) / total if total > 0 else 0
        confidence = min(0.7, len(signals) / 6)

        regime = "Risk-On" if score > 0.2 else ("Risk-Off" if score < -0.2 else "混合")
        return AnalysisResult(
            dimension=self.dimension,
            score=round(score, 2),
            confidence=round(confidence, 2),
            signals=signals,
            summary=f"跨市场信号指向 {regime}，评分 {score:+.1f}",
            details={"regime": regime, "signal_count": len(signals)},
        )

    def _gold_signal(self, md: dict) -> list[Signal]:
        signals = []
        gold = md.get("gold")
        if gold is None:
            return signals
        gold_val = float(gold) if isinstance(gold, (int, float, str)) else None
        if gold_val:
            if gold_val > 2000:
                signals.append(Signal("金价高位", "bearish", 0.4, f"黄金={gold_val:.0f}，避险情绪较高"))
            elif gold_val > 1800:
                signals.append(Signal("金价偏高", "neutral", 0.3, f"黄金={gold_val:.0f}"))
            else:
                signals.append(Signal("金价适中", "bullish", 0.3, f"黄金={gold_val:.0f}，风险偏好正常"))
        return signals

    def _dxy_signal(self, md: dict) -> list[Signal]:
        signals = []
        dxy = md.get("dxy", md.get("DXY"))
        if dxy is None:
            return signals
        dxy_val = float(dxy) if isinstance(dxy, (int, float, str)) else None
        if dxy_val:
            if dxy_val > 105:
                signals.append(Signal("强美元压制", "bearish", 0.5, f"DXY={dxy_val:.0f}，新兴市场和大宗商品承压"))
            elif dxy_val < 95:
                signals.append(Signal("弱美元利好", "bullish", 0.5, f"DXY={dxy_val:.0f}，利好新兴市场"))
            else:
                signals.append(Signal("美元中性", "neutral", 0.3, f"DXY={dxy_val:.0f}"))
        return signals

    def _vix_signal(self, md: dict, prices) -> list[Signal]:
        signals = []
        vix = md.get("vix")
        if vix is None:
            return signals
        vix_val = float(vix) if isinstance(vix, (int, float, str)) else None
        if vix_val:
            if vix_val > 30:
                signals.append(Signal("极高恐慌", "bearish", 0.7, f"VIX={vix_val:.0f}，市场恐慌"))
            elif vix_val > 25:
                signals.append(Signal("恐慌偏高", "bearish", 0.5, f"VIX={vix_val:.0f}，市场紧张"))
            elif vix_val > 20:
                signals.append(Signal("波动正常偏高", "neutral", 0.3, f"VIX={vix_val:.0f}"))
            elif vix_val > 12:
                signals.append(Signal("波动正常", "bullish", 0.2, f"VIX={vix_val:.0f}"))
            else:
                signals.append(Signal("极低波动", "bullish", 0.3, f"VIX={vix_val:.0f}，但需警惕自满"))
        return signals
