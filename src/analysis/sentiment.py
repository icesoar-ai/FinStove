from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal


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

        scores = [n.sentiment_score for n in news if n.sentiment_score is not None]
        if not scores:
            return signals

        avg_score = sum(scores) / len(scores)
        if avg_score > 0.3:
            signals.append(Signal("新闻情绪正面", "bullish", 0.4, f"平均情绪得分 {avg_score:.2f}"))
        elif avg_score > 0:
            signals.append(Signal("新闻情绪偏正面", "bullish", 0.2, f"平均情绪得分 {avg_score:.2f}"))
        elif avg_score > -0.3:
            signals.append(Signal("新闻情绪偏负面", "bearish", 0.2, f"平均情绪得分 {avg_score:.2f}"))
        else:
            signals.append(Signal("新闻情绪负面", "bearish", 0.4, f"平均情绪得分 {avg_score:.2f}"))

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
