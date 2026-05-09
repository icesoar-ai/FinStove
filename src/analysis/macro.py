from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal


class MacroAnalyzer(AbstractAnalyzer):
    """Analyze macro environment: rates, yield curve, CPI, PPI, PMI, GDP, DXY, M2, LPR, trade.

    Works with macro_data dict from context, populated by FRED + AKShare.
    Expects keys like:
        - `cpi_yoy`: dict[country -> float]
        - `ppi_yoy`: dict[country -> float]
        - `pmi`: dict[country -> float]
        - `pmi_caixin`: float
        - `pmi_non_man`: float
        - `gdp_growth`: dict[country -> float]
        - `yield_curve`: dict[country -> dict[tenor -> float]]
        - `dxy`: float (DXY index level)
        - `policy_rate`: dict[country -> float]
        - `shibor`: dict[tenor -> float]
        - `lpr`: dict[str -> float]  (1Y, 5Y)
        - `m2_growth`: float
        - `m1_growth`: float
        - `social_financing`: float  (亿元)
        - `fx_reserves`: float  (USD billions)
        - `exports_yoy`: float
        - `imports_yoy`: float
        - `industrial_production`: float
        - `retail_sales_growth`: float
        - `unemployment`: dict[country -> float]
    """

    dimension = Dimension.MACRO

    # 客观阈值 (不随观点改变)
    CPI_TARGET = 2.0
    PMI_THRESHOLD = 50.0
    YIELD_CURVE_INVERSION_THRESH = -0.5
    DXY_HIGH = 105.0
    DXY_LOW = 95.0
    GDP_HEALTHY = 2.0
    PPI_DEFLATION = -0.5
    M2_HEALTHY_MIN = 8.0
    M2_HEALTHY_MAX = 12.0
    UNEMPLOYMENT_WARNING = 5.5
    TRADE_SURPLUS_HEALTHY = 300.0  # USD billion equivalent, but values are in 亿 so ~3000
    FX_DECLINE_WARNING = -5.0   # pct decline

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        md = context.macro_data or {}
        signals: list[Signal] = []

        signals.extend(self._yield_curve(md))
        signals.extend(self._policy_rates(md))
        signals.extend(self._inflation(md))
        signals.extend(self._ppi(md))
        signals.extend(self._pmi(md))
        signals.extend(self._gdp(md))
        signals.extend(self._dxy(md))
        signals.extend(self._shibor_liquidity(md))
        signals.extend(self._money_supply(md))
        signals.extend(self._social_financing(md))
        signals.extend(self._lpr(md))
        signals.extend(self._unemployment(md))
        signals.extend(self._trade(md))
        signals.extend(self._industrial(md))

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
            # Try standard keys first (10Y/2Y for US), then Chinese key format
            tenor_long = curve.get("10Y") or curve.get("10年")
            tenor_short = curve.get("2Y") or curve.get("1年")
            if tenor_long is None or tenor_short is None:
                continue
            spread = float(tenor_long) - float(tenor_short)
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

    def _ppi(self, md: dict) -> list[Signal]:
        """PPI analysis — industrial-side price pressure."""
        signals = []
        ppi = md.get("ppi_yoy", {})
        for country in ("US", "CN"):
            val = ppi.get(country)
            if val is None:
                continue
            label = f"{'美国' if country == 'US' else '中国'}工业通胀 (PPI)"
            if val > 5:
                signals.append(Signal(label, "bearish", 0.5, f"{val:.1f}%，成本压力大"))
            elif val > 2:
                signals.append(Signal(label, "neutral", 0.3, f"{val:.1f}%，温和上行"))
            elif val > self.PPI_DEFLATION:
                signals.append(Signal(label, "bullish", 0.3, f"{val:.1f}%，价格稳定"))
            elif val > -3:
                signals.append(Signal(label, "bearish", 0.4, f"{val:.1f}%，工业通缩"))
            else:
                signals.append(Signal(label, "bearish", 0.6, f"{val:.1f}%，深度通缩"))
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

        # Caixin PMI (private/export-oriented manufacturing)
        cx = md.get("pmi_caixin")
        if cx is not None:
            if cx > 52:
                signals.append(Signal("中国财新制造业PMI", "bullish", 0.4, f"{cx:.1f}，私营制造业扩张"))
            elif cx > 50:
                signals.append(Signal("中国财新制造业PMI", "bullish", 0.2, f"{cx:.1f}，温和扩张"))
            elif cx > 48:
                signals.append(Signal("中国财新制造业PMI", "neutral", 0.2, f"{cx:.1f}，收缩边缘"))
            else:
                signals.append(Signal("中国财新制造业PMI", "bearish", 0.4, f"{cx:.1f}，收缩"))

        # Non-manufacturing PMI
        nm = md.get("pmi_non_man")
        if nm is not None:
            if nm > 52:
                signals.append(Signal("中国非制造业PMI", "bullish", 0.3, f"{nm:.1f}，服务业扩张"))
            elif nm > 50:
                signals.append(Signal("中国非制造业PMI", "neutral", 0.2, f"{nm:.1f}，温和"))
            else:
                signals.append(Signal("中国非制造业PMI", "bearish", 0.4, f"{nm:.1f}，收缩"))
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

    def _money_supply(self, md: dict) -> list[Signal]:
        """M1/M2 growth — monetary expansion signals."""
        signals = []
        m2 = md.get("m2_growth")
        m1 = md.get("m1_growth")

        if m2 is not None:
            if m2 > 13:
                signals.append(Signal("M2货币供应", "bullish", 0.5, f"M2={m2:.1f}%，货币宽松"))
            elif m2 > self.M2_HEALTHY_MIN:
                signals.append(Signal("M2货币供应", "bullish", 0.3, f"M2={m2:.1f}%，适度增长"))
            elif m2 > 6:
                signals.append(Signal("M2货币供应", "neutral", 0.3, f"M2={m2:.1f}%，增长偏慢"))
            else:
                signals.append(Signal("M2货币供应", "bearish", 0.5, f"M2={m2:.1f}%，货币紧缩"))

        if m1 is not None and m2 is not None:
            spread = m1 - m2
            if spread > 2:
                signals.append(Signal("M1-M2剪刀差", "bullish", 0.4, f"{spread:+.1f}%，企业活期存款活跃"))
            elif spread < -5:
                signals.append(Signal("M1-M2剪刀差", "bearish", 0.4, f"{spread:+.1f}%，资金沉淀定期"))
        return signals

    def _social_financing(self, md: dict) -> list[Signal]:
        """Social financing — credit impulse."""
        sf = md.get("social_financing")
        if sf is None:
            return []
        if sf > 30000:
            return [Signal("社会融资", "bullish", 0.4, f"{sf:.0f}亿，信贷扩张")]
        elif sf > 15000:
            return [Signal("社会融资", "bullish", 0.2, f"{sf:.0f}亿，信贷正常")]
        elif sf > 5000:
            return [Signal("社会融资", "neutral", 0.2, f"{sf:.0f}亿，信贷放缓")]
        else:
            return [Signal("社会融资", "bearish", 0.4, f"{sf:.0f}亿，信贷紧缩")]

    def _lpr(self, md: dict) -> list[Signal]:
        """LPR — China benchmark lending rate."""
        lpr = md.get("lpr", {})
        if not lpr:
            return []
        signals = []
        lpr1y = lpr.get("1Y")
        lpr5y = lpr.get("5Y")
        if lpr1y is not None:
            if lpr1y > 4.0:
                signals.append(Signal("LPR", "bearish", 0.3, f"1Y={lpr1y:.2f}%, 5Y={lpr5y:.2f}%，利率偏高"))
            elif lpr1y > 3.0:
                signals.append(Signal("LPR", "neutral", 0.2, f"1Y={lpr1y:.2f}%, 5Y={lpr5y:.2f}%，中等水平"))
            else:
                signals.append(Signal("LPR", "bullish", 0.3, f"1Y={lpr1y:.2f}%, 5Y={lpr5y:.2f}%，利率偏低"))
        return signals

    def _unemployment(self, md: dict) -> list[Signal]:
        signals = []
        unemp = md.get("unemployment", {})
        for country in ("US", "CN"):
            val = unemp.get(country)
            if val is None:
                continue
            label = f"{'美国' if country == 'US' else '中国'}失业率"
            if val > 7:
                signals.append(Signal(label, "bearish", 0.6, f"{val:.1f}%，高失业率"))
            elif val > self.UNEMPLOYMENT_WARNING:
                signals.append(Signal(label, "bearish", 0.3, f"{val:.1f}%，偏高"))
            elif val > 4:
                signals.append(Signal(label, "neutral", 0.2, f"{val:.1f}%"))
            else:
                signals.append(Signal(label, "bullish", 0.3, f"{val:.1f}%，充分就业"))
        return signals

    def _trade(self, md: dict) -> list[Signal]:
        """Trade balance analysis."""
        signals = []
        exports = md.get("exports_yoy")
        imports = md.get("imports_yoy")

        if exports is not None:
            if exports > 10:
                signals.append(Signal("中国出口", "bullish", 0.5, f"同比+{exports:.1f}%，出口强劲"))
            elif exports > 0:
                signals.append(Signal("中国出口", "bullish", 0.3, f"同比+{exports:.1f}%，正增长"))
            elif exports > -5:
                signals.append(Signal("中国出口", "neutral", 0.3, f"同比{exports:.1f}%，小幅下滑"))
            else:
                signals.append(Signal("中国出口", "bearish", 0.5, f"同比{exports:.1f}%，大幅下滑"))

        if imports is not None:
            if imports > 10:
                signals.append(Signal("中国进口", "bullish", 0.3, f"同比+{imports:.1f}%，内需旺盛"))
            elif imports > 0:
                signals.append(Signal("中国进口", "neutral", 0.2, f"同比+{imports:.1f}%"))
            elif imports > -5:
                signals.append(Signal("中国进口", "neutral", 0.3, f"同比{imports:.1f}%，内需偏弱"))
            else:
                signals.append(Signal("中国进口", "bearish", 0.4, f"同比{imports:.1f}%，内需疲软"))
        return signals

    def _industrial(self, md: dict) -> list[Signal]:
        """Industrial production and retail sales."""
        signals = []
        ip_val = md.get("industrial_production")
        if ip_val is not None:
            if ip_val > 8:
                signals.append(Signal("中国工业增加值", "bullish", 0.5, f"同比+{ip_val:.1f}%，生产旺盛"))
            elif ip_val > 5:
                signals.append(Signal("中国工业增加值", "bullish", 0.3, f"同比+{ip_val:.1f}%，稳定增长"))
            elif ip_val > 3:
                signals.append(Signal("中国工业增加值", "neutral", 0.3, f"同比+{ip_val:.1f}%，增速放缓"))
            else:
                signals.append(Signal("中国工业增加值", "bearish", 0.5, f"同比+{ip_val:.1f}%，增长停滞"))

        rs_val = md.get("retail_sales_growth")
        if rs_val is not None:
            if rs_val > 10:
                signals.append(Signal("中国社消零售", "bullish", 0.4, f"同比+{rs_val:.1f}%，消费旺盛"))
            elif rs_val > 5:
                signals.append(Signal("中国社消零售", "bullish", 0.2, f"同比+{rs_val:.1f}%，消费稳健"))
            elif rs_val > 0:
                signals.append(Signal("中国社消零售", "neutral", 0.3, f"同比+{rs_val:.1f}%，消费低迷"))
            else:
                signals.append(Signal("中国社消零售", "bearish", 0.5, f"同比{rs_val:.1f}%，消费萎缩"))
        return signals
