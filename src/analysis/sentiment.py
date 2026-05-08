import math
from datetime import datetime

from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal

# ---- Financial Sentiment Lexicon ----

# Strong negative (-2), general negative (-1)
NEG_WORDS = {
    "亏损": -2, "暴跌": -2, "崩盘": -2, "退市": -2, "ST": -2, "跌停": -2,
    "造假": -2, "爆雷": -2, "暴雷": -2, "破产": -2, "清盘": -2,
    "下滑": -1, "下降": -1, "减持": -1, "诉讼": -1, "处罚": -1,
    "监管": -1, "风险": -1, "不确定性": -1, "下跌": -1, "回落": -1,
    "低迷": -1, "疲软": -1, "恶化": -1, "紧缩": -1, "警告": -1,
    "违约": -1, "债务": -1, "危机": -1, "恐慌": -1, "抛售": -1,
    "降级": -1, "罚款": -1, "调查": -1, "冻结": -1, "暂停": -1,
    "异常": -1, "波动": -1, "减少": -1, "缩减": -1, "收窄": -1,
}

# Strong positive (+2), general positive (+1)
POS_WORDS = {
    "涨停": 2, "大涨": 2, "翻倍": 2, "创新高": 2, "突破": 1,
    "增长": 1, "上升": 1, "增持": 1, "回购": 1, "分红": 1,
    "盈利": 1, "利好": 1, "回升": 1, "反弹": 1, "扩张": 1,
    "研发": 1, "订单": 1, "签约": 1, "中标": 1, "获批": 1,
    "看好": 1, "买入": 1, "推荐": 1, "超预期": 1, "优于": 1,
    "领先": 1, "优化": 1, "改善": 1, "提升": 1, "加大": 1,
    "投入": 1, "合作": 1, "战略": 1, "布局": 1, "升级": 1,
    "龙头": 1, "稳健": 1, "复苏": 1, "回暖": 1, "放量": 1,
}

# Negation flips polarity of next sentiment word
NEGATION_WORDS = {"不", "没", "无", "未", "非", "勿", "别", "莫", "否", "没有"}

# Degree adverbs amplify or dampen
AMPLIFIERS = {"大幅": 1.5, "急剧": 1.5, "显著": 1.5, "持续": 1.3,
              "进一步": 1.3, "严重": 1.5, "明显": 1.3, "加快": 1.3}
DAMPENERS = {"略微": 0.5, "小幅": 0.5, "略有": 0.5, "微幅": 0.5,
             "稍微": 0.5, "轻度": 0.5}


def _compute_sentiment(text: str) -> float:
    """Compute sentiment score for Chinese financial text using jieba + lexicon.

    Returns float in [-1.0, 1.0].
    """
    if not text or not text.strip():
        return 0.0

    import jieba

    words = list(jieba.cut(text))
    score = 0.0
    negated = False
    degree = 1.0
    hit_count = 0

    for w in words:
        w = w.strip()
        if not w:
            continue

        if w in NEGATION_WORDS:
            negated = True
            continue

        if w in AMPLIFIERS:
            degree = AMPLIFIERS[w]
            continue
        if w in DAMPENERS:
            degree = DAMPENERS[w]
            continue

        if w in NEG_WORDS:
            val = NEG_WORDS[w] * degree
            if negated:
                val = -val  # flip: "未亏损" → positive
            score += val
            hit_count += 1
            negated = False
            degree = 1.0
        elif w in POS_WORDS:
            val = POS_WORDS[w] * degree
            if negated:
                val = -val  # flip: "不增长" → negative
            score += val
            hit_count += 1
            negated = False
            degree = 1.0

    if hit_count == 0:
        return 0.0

    # Normalize: max abs score per word is 2, so divide by (2 * hit_count)
    max_score = 2.0 * hit_count
    normalized = max(-1.0, min(1.0, score / max_score * 2.0))
    return round(normalized, 4)


class SentimentAnalyzer(AbstractAnalyzer):
    """Market sentiment analysis from news, VIX, breadth indicators."""

    dimension = Dimension.SENTIMENT

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        news = context.news_data or []
        md = context.macro_data or {}
        prices = context.price_data
        signals: list[Signal] = []

        signals.extend(self._news_sentiment(news))
        signals.extend(self._fear_greed(md, prices))

        if not signals:
            return AnalysisResult(
                dimension=self.dimension, score=0, confidence=0.2,
                signals=[], summary="情绪数据不足", warnings=["未获取到新闻情绪数据"],
            )

        bullish = sum(s.strength for s in signals if s.direction == "bullish")
        bearish = sum(s.strength for s in signals if s.direction == "bearish")
        total = bullish + bearish
        score = 2 * (bullish - bearish) / total if total > 0 else 0
        confidence = min(0.7, len(signals) / 6)

        mood = "乐观" if score > 0.3 else ("恐慌" if score < -0.3 else "中性")
        return AnalysisResult(
            dimension=self.dimension,
            score=round(score, 2),
            confidence=round(confidence, 2),
            signals=signals,
            summary=f"市场情绪{mood}，综合评分 {score:+.1f}",
            details={"signal_count": len(signals)},
        )

    def _news_sentiment(self, news: list) -> list[Signal]:
        signals = []
        if not news:
            return signals

        now = datetime.now()

        # Compute sentiment for news items that don't have it
        for n in news:
            if n.sentiment_score is None:
                text = f"{n.title} {n.summary}"
                n.sentiment_score = _compute_sentiment(text)

        # Time-weighted aggregation: newer news has higher weight
        scores_and_weights = []
        for n in news:
            if n.sentiment_score is not None:
                age_days = (now - n.date.replace(tzinfo=None)).total_seconds() / 86400 if n.date else 7
                weight = math.exp(-age_days / 3)  # half-life ~2 days
                scores_and_weights.append((n.sentiment_score, weight))

        if not scores_and_weights:
            return signals

        total_weight = sum(w for _, w in scores_and_weights)
        if total_weight == 0:
            return signals

        avg_score = sum(s * w for s, w in scores_and_weights) / total_weight

        # Standard deviation for confidence
        if len(scores_and_weights) > 1:
            variance = sum(w * (s - avg_score) ** 2 for s, w in scores_and_weights) / total_weight
            std = math.sqrt(variance)
        else:
            std = 0

        if avg_score > 0.3:
            signals.append(Signal("新闻情绪正面", "bullish", 0.4, f"加权平均得分 {avg_score:.2f}"))
        elif avg_score > 0:
            signals.append(Signal("新闻情绪偏正面", "bullish", 0.2, f"加权平均得分 {avg_score:.2f}"))
        elif avg_score > -0.3:
            signals.append(Signal("新闻情绪偏负面", "bearish", 0.2, f"加权平均得分 {avg_score:.2f}"))
        else:
            signals.append(Signal("新闻情绪负面", "bearish", 0.4, f"加权平均得分 {avg_score:.2f}"))

        # High dispersion → low consensus
        if std > 0.3:
            signals.append(Signal("新闻观点分歧大", "neutral", 0.1, f"标准差 {std:.2f}"))

        return signals

    def _fear_greed(self, md: dict, prices) -> list[Signal]:
        signals = []
        vix = md.get("vix")
        if vix is not None:
            vix_val = float(vix) if isinstance(vix, (int, float, str)) else 30
            if vix_val > 35:
                signals.append(Signal("极度恐惧", "bearish", 0.6, f"VIX={vix_val:.0f}"))
            elif vix_val < 12:
                signals.append(Signal("极度贪婪", "bullish", 0.4, f"VIX={vix_val:.0f}"))

        # Breadth: % above MA
        if prices is not None and not prices.empty and "close" in prices.columns:
            close = prices["close"].tail(250)
            if len(close) >= 20:
                ma20 = close.rolling(20).mean()
                pct_above = (close.iloc[-1] > ma20.iloc[-1])
                ma50 = close.rolling(50).mean()
                pct_above_50 = (close.iloc[-1] > ma50.iloc[-1]) if len(close) >= 50 else None

                if pct_above and (pct_above_50 or True):
                    signals.append(Signal("价格在均线上方", "bullish", 0.3, "短期趋势偏多"))
                else:
                    signals.append(Signal("价格在均线下方", "bearish", 0.3, "短期趋势偏空"))

        return signals
