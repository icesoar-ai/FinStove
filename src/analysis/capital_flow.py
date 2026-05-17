from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal


class CapitalFlowAnalyzer(AbstractAnalyzer):
    """Analyze capital flows: north/south bound, institutional, sector rotation."""

    dimension = Dimension.CAPITAL_FLOW

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        flow_data = context.flow_data
        signals: list[Signal] = []

        signals.extend(self._north_south_flow(flow_data))
        signals.extend(self._volume_trend(context.price_data, context.lookback_days))

        if not signals:
            return AnalysisResult(
                dimension=self.dimension, score=0, confidence=0.2,
                signals=[], summary="资金流向数据不足", warnings=["缺少沪深港通数据"],
            )

        bullish = sum(s.strength for s in signals if s.direction == "bullish")
        bearish = sum(s.strength for s in signals if s.direction == "bearish")
        total = bullish + bearish
        score = 2 * (bullish - bearish) / total if total > 0 else 0
        confidence = min(0.8, len(signals) / 6)

        direction = "资金流入" if score > 0.3 else ("资金流出" if score < -0.3 else "资金平衡")
        return AnalysisResult(
            dimension=self.dimension,
            score=round(score, 2),
            confidence=round(confidence, 2),
            signals=signals,
            summary=f"资金面{direction}，综合评分 {score:+.1f}",
            details={"signal_count": len(signals)},
        )

    def _north_south_flow(self, flow_data) -> list[Signal]:
        signals = []
        if flow_data is None:
            return signals

        for key, label, bull_label, bear_label in [
            ("northbound", "北向资金", "持续净流入A股", "持续净流出A股"),
            ("southbound", "南向资金", "资金回流港股", "资金流入港股"),
        ]:
            df = flow_data.get(key) if isinstance(flow_data, dict) else flow_data
            if df is None or df.empty:
                continue
            col = "当日成交净买额" if "当日成交净买额" in df.columns else None
            if col is None:
                continue
            recent = df[col].tail(20)
            recent = recent.dropna()
            if recent.empty:
                continue
            net_sum = recent.sum()
            if net_sum > 0:
                signals.append(Signal(label, "bullish", 0.5, f"{bull_label}，20日累计 {net_sum:.0f}亿"))
            else:
                signals.append(Signal(label, "bearish", 0.5, f"{bear_label}，20日累计 {net_sum:.0f}亿"))
        return signals

    def _volume_trend(self, price_data, lookback) -> list[Signal]:
        signals = []
        if price_data is None or price_data.empty or "volume" not in price_data.columns:
            return signals

        vol = price_data["volume"].tail(min(60, len(price_data)))
        if len(vol) < 20:
            return signals

        vol_20 = vol.tail(20).mean()
        vol_60 = vol.mean() if len(vol) >= 40 else vol_20

        if vol_20 > vol_60 * 1.3:
            signals.append(Signal("成交量放大", "bullish", 0.4, "近20日均量显著高于60日均量，资金活跃"))
        elif vol_20 < vol_60 * 0.7:
            signals.append(Signal("成交量萎缩", "bearish", 0.3, "近20日均量低于60日均量，资金观望"))

        # Volume-price relationship
        close = price_data["close"].tail(min(60, len(price_data)))
        if len(close) >= 20:
            price_up = close.iloc[-1] > close.iloc[-20]
            vol_up = vol_20 > vol_60
            if price_up and vol_up:
                signals.append(Signal("量价配合上涨", "bullish", 0.5, "放量上涨"))
            elif not price_up and vol_up:
                signals.append(Signal("放量下跌", "bearish", 0.5, "量价背离，放量下跌"))

        return signals
