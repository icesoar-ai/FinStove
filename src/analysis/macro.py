from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal


class MacroAnalyzer(AbstractAnalyzer):
    """Analyze macro environment: rates, yield curve, CPI, PMI, GDP, DXY.

    Works with macro_data dict from context, populated by FRED + AKShare.
    Expects keys like:
        - `cpi_yoy`: dict[country -> float]
        - `pmi`: dict[country -> float]
        - `gdp_growth`: dict[country -> float]
        - `yield_curve`: dict[country -> dict[tenor -> float]]
        - `dxy`: float (DXY index level)
        - `policy_rate`: dict[country -> float]
        - `shibor`: dict[tenor -> float]
    """

    dimension = Dimension.MACRO

    # 客观阈值 (不随观点改变)
    CPI_TARGET = 2.0
    PMI_THRESHOLD = 50.0
    YIELD_CURVE_INVERSION_THRESH = -0.5
    DXY_HIGH = 105.0
    DXY_LOW = 95.0
    GDP_HEALTHY = 2.0

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        md = context.macro_data or {}
        signals: list[Signal] = []

        signals.extend(self._yield_curve(md))
        signals.extend(self._policy_rates(md))
        signals.extend(self._inflation(md))
        signals.extend(self._pmi(md))
        signals.extend(self._gdp(md))
        signals.extend(self._dxy(md))
        signals.extend(self._shibor_liquidity(md))

        if not signals:
            return AnalysisResult(
                dimension=self.dimension,
                score=0,
                confidence=0.2,
                signals=[],
                summary="缺少宏观数据，无法评估",
                warnings=["未获取到宏观数据"],
            )

        bullish = sum(s.strength for s in signals if s.direction == "bullish")
        bearish = sum(s.strength for s in signals if s.direction == "bearish")
        total = bullish + bearish
        score = 2 * (bullish - bearish) / total if total > 0 else 0
        confidence = min(0.85, len(signals) / 12)

        direction = "宽松/增长" if score > 0.3 else ("紧缩/衰退" if score < -0.3 else "中性")
        return AnalysisResult(
            dimension=self.dimension,
            score=round(score, 2),
            confidence=round(confidence, 2),
            signals=signals,
            summary=f"宏观环境{direction}，综合评分 {score:+.1f}",
            details={"signal_count": len(signals)},
        )

    # ---- Sub-analysis Methods ----

    def _yield_curve(self, md: dict) -> list[Signal]:
        signals = []
        for country in ("US", "CN"):
            curve = md.get("yield_curve", {}).get(country, {})
            if not curve:
                continue
            tenor_10y = curve.get("10Y")
            tenor_2y = curve.get("2Y")
            if tenor_10y is None or tenor_2y is None:
                continue
            spread = float(tenor_10y) - float(tenor_2y)
            label = f"{'美国' if country == 'US' else '中国'}收益率曲线"
            if spread < self.YIELD_CURVE_INVERSION_THRESH:
                signals.append(Signal(label, "bearish", 0.6, f"倒挂 {spread:.2f}%，衰退预警"))
            elif spread < 0:
                signals.append(Signal(label, "bearish", 0.4, f"轻微倒挂 {spread:.2f}%"))
            elif spread < 0.5:
                signals.append(Signal(label, "neutral", 0.3, f"扁平 {spread:.2f}%"))
            else:
                signals.append(Signal(label, "bullish", 0.4, f"正常陡峭 {spread:.2f}%"))
        return signals

    def _policy_rates(self, md: dict) -> list[Signal]:
        signals = []
        rates = md.get("policy_rate", {})
        for country in ("US", "CN"):
            rate = rates.get(country)
            if rate is None:
                continue
            label = f"{'美联储' if country == 'US' else '中国央行'}政策利率"
            if rate > 5:
                signals.append(Signal(label, "bearish", 0.5, f"{rate:.2f}%，高利率压制估值"))
            elif rate > 3:
                signals.append(Signal(label, "neutral", 0.3, f"{rate:.2f}%，中等水平"))
            elif rate > 1:
                signals.append(Signal(label, "bullish", 0.4, f"{rate:.2f}%，偏低有利市场"))
            else:
                signals.append(Signal(label, "bullish", 0.5, f"{rate:.2f}%，超低利率"))
        return signals

    def _inflation(self, md: dict) -> list[Signal]:
        signals = []
        cpi = md.get("cpi_yoy", {})
        for country in ("US", "CN"):
            val = cpi.get(country)
            if val is None:
                continue
            label = f"{'美国' if country == 'US' else '中国'}通胀 (CPI)"
            if val > 5:
                signals.append(Signal(label, "bearish", 0.7, f"{val:.1f}%，高通胀"))
            elif val > self.CPI_TARGET + 1:
                signals.append(Signal(label, "bearish", 0.4, f"{val:.1f}%，高于目标"))
            elif val > self.CPI_TARGET:
                signals.append(Signal(label, "neutral", 0.3, f"{val:.1f}%，略高于目标"))
            elif val > 0:
                signals.append(Signal(label, "bullish", 0.4, f"{val:.1f}%，温和通胀"))
            else:
                signals.append(Signal(label, "bearish", 0.5, f"{val:.1f}%，通缩风险"))
        return signals

    def _pmi(self, md: dict) -> list[Signal]:
        signals = []
        pmi = md.get("pmi", {})
        for country in ("US", "CN"):
            val = pmi.get(country)
            if val is None:
                continue
            label = f"{'美国' if country == 'US' else '中国'}PMI"
            if val > 52:
                signals.append(Signal(label, "bullish", 0.5, f"{val:.1f}，扩张"))
            elif val > self.PMI_THRESHOLD:
                signals.append(Signal(label, "bullish", 0.3, f"{val:.1f}，温和扩张"))
            elif val > 48:
                signals.append(Signal(label, "neutral", 0.3, f"{val:.1f}，收缩边缘"))
            else:
                signals.append(Signal(label, "bearish", 0.5, f"{val:.1f}，收缩"))
        return signals

    def _gdp(self, md: dict) -> list[Signal]:
        signals = []
        gdp = md.get("gdp_growth", {})
        for country in ("US", "CN"):
            val = gdp.get(country)
            if val is None:
                continue
            label = f"{'美国' if country == 'US' else '中国'}GDP增速"
            if val > 5:
                signals.append(Signal(label, "bullish", 0.6, f"{val:.1f}%，高速增长"))
            elif val > self.GDP_HEALTHY:
                signals.append(Signal(label, "bullish", 0.4, f"{val:.1f}%，健康增长"))
            elif val > 1:
                signals.append(Signal(label, "neutral", 0.3, f"{val:.1f}%，低速增长"))
            elif val > 0:
                signals.append(Signal(label, "bearish", 0.4, f"{val:.1f}%，接近停滞"))
            else:
                signals.append(Signal(label, "bearish", 0.6, f"{val:.1f}%，衰退"))
        return signals

    def _dxy(self, md: dict) -> list[Signal]:
        dxy = md.get("dxy", md.get("DXY"))
        if dxy is None:
            return []
        signals = []
        if dxy > 108:
            signals.append(Signal("美元指数极强", "bearish", 0.6, f"DXY={dxy:.0f}，新兴市场承压"))
        elif dxy > self.DXY_HIGH:
            signals.append(Signal("美元偏强", "bearish", 0.4, f"DXY={dxy:.0f}"))
        elif dxy < self.DXY_LOW:
            signals.append(Signal("美元偏弱", "bullish", 0.5, f"DXY={dxy:.0f}，利好大宗商品和新兴市场"))
        else:
            signals.append(Signal("美元中性", "neutral", 0.3, f"DXY={dxy:.0f}"))
        return signals

    def _shibor_liquidity(self, md: dict) -> list[Signal]:
        shibor = md.get("shibor", {})
        if not shibor:
            return []
        overnight = shibor.get("ON", shibor.get("隔夜"))
        if overnight is None:
            return []
        if overnight > 3:
            return [Signal("短期流动性紧张", "bearish", 0.4, f"隔夜SHIBOR={overnight:.2f}%")]
        return [Signal("短期流动性充裕", "bullish", 0.2, f"隔夜SHIBOR={overnight:.2f}%")]
