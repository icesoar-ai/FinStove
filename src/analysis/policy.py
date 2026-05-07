from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal


class PolicyAnalyzer(AbstractAnalyzer):
    """Policy stance analysis: central bank direction, fiscal, regulatory keywords.

    This is the least quantitative module. It relies on structured keyword frequency
    from news data. Without sufficient news corpus, it returns low-confidence results.
    """

    dimension = Dimension.POLICY

    # Keywords by category
    TIGHTENING_KEYWORDS = ["加息", "缩表", "收紧", "上调利率", "taper", "rate hike", "tightening"]
    EASING_KEYWORDS = ["降息", "降准", "宽松", "刺激", "下调利率", "rate cut", "easing", "QE"]
    REGULATORY_RISK_KEYWORDS = ["监管", "整顿", "反垄断", "限制", "regulation", "crackdown", "fine"]
    GEOPOLITICAL_KEYWORDS = ["制裁", "关税", "战争", "冲突", "脱钩", "sanction", "tariff", "war", "conflict"]
    FISCAL_STIMULUS_KEYWORDS = ["财政", "基建", "减税", "补贴", "fiscal", "infrastructure", "stimulus", "subsidy"]

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        news = context.news_data or []
        md = context.macro_data or {}
        signals: list[Signal] = []

        signals.extend(self._rate_policy(md))
        signals.extend(self._keyword_signals(news))

        if not signals:
            return AnalysisResult(
                dimension=self.dimension, score=0, confidence=0.15,
                signals=[], summary="政策数据不足", warnings=["缺少政策相关数据"],
            )

        bullish = sum(s.strength for s in signals if s.direction == "bullish")
        bearish = sum(s.strength for s in signals if s.direction == "bearish")
        total = bullish + bearish
        score = 2 * (bullish - bearish) / total if total > 0 else 0
        confidence = min(0.6, len(signals) / 8)

        stance = "政策友好" if score > 0.3 else ("政策收紧" if score < -0.3 else "中性")
        return AnalysisResult(
            dimension=self.dimension,
            score=round(score, 2),
            confidence=round(confidence, 2),
            signals=signals,
            summary=f"政策面{stance}，综合评分 {score:+.1f}",
            details={"signal_count": len(signals)},
        )

    def _rate_policy(self, md: dict) -> list[Signal]:
        signals = []
        rates = md.get("policy_rate", {})
        for country, label in [("US", "美联储"), ("CN", "中国央行")]:
            rate = rates.get(country)
            if rate is None:
                continue
            if rate > 5:
                signals.append(Signal(f"{label}紧缩", "bearish", 0.5, f"利率{rate:.1f}%"))
            elif rate < 2:
                signals.append(Signal(f"{label}宽松", "bullish", 0.5, f"利率{rate:.1f}%"))
        return signals

    def _keyword_signals(self, news: list) -> list[Signal]:
        signals = []
        if not news:
            return signals

        all_text = " ".join(n.title for n in news if n.title)
        if not all_text:
            return signals

        tightening_hits = sum(1 for kw in self.TIGHTENING_KEYWORDS if kw.lower() in all_text.lower())
        easing_hits = sum(1 for kw in self.EASING_KEYWORDS if kw.lower() in all_text.lower())
        reg_hits = sum(1 for kw in self.REGULATORY_RISK_KEYWORDS if kw.lower() in all_text.lower())
        geo_hits = sum(1 for kw in self.GEOPOLITICAL_KEYWORDS if kw.lower() in all_text.lower())
        fiscal_hits = sum(1 for kw in self.FISCAL_STIMULUS_KEYWORDS if kw.lower() in all_text.lower())

        if easing_hits > tightening_hits:
            signals.append(Signal("货币政策偏宽松", "bullish", 0.4, f"宽松词频 {easing_hits} > 紧缩词频 {tightening_hits}"))
        elif tightening_hits > easing_hits:
            signals.append(Signal("货币政策偏紧缩", "bearish", 0.4, f"紧缩词频 {tightening_hits} > 宽松词频 {easing_hits}"))

        if reg_hits > 2:
            signals.append(Signal("监管风险", "bearish", 0.4, f"监管关键词出现 {reg_hits} 次"))
        if geo_hits > 2:
            signals.append(Signal("地缘风险", "bearish", 0.5, f"地缘关键词出现 {geo_hits} 次"))
        if fiscal_hits > 2:
            signals.append(Signal("财政刺激", "bullish", 0.3, f"财政关键词出现 {fiscal_hits} 次"))

        return signals
