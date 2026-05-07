import numpy as np
import pandas as pd
import ta

from ..data.base import Dimension
from .base import AbstractAnalyzer, AnalysisContext, AnalysisResult, Signal


class TechnicalAnalyzer(AbstractAnalyzer):
    dimension = Dimension.TECHNICAL

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        df = context.price_data
        if df is None or df.empty:
            return AnalysisResult(
                dimension=self.dimension,
                score=0,
                confidence=0,
                signals=[],
                summary="无价格数据",
                warnings=["缺少价格数据"],
            )

        close = df["close"].astype(float)
        volume = df["volume"].astype(float)
        signals: list[Signal] = []

        signals.extend(self._trend(close))
        signals.extend(self._momentum(close))
        signals.extend(self._volume_signal(close, volume))
        signals.extend(self._support_resistance(close))

        if not signals:
            return AnalysisResult(
                dimension=self.dimension,
                score=0,
                confidence=0.3,
                signals=[],
                summary="无法生成有效技术信号",
            )

        bullish = sum(s.strength for s in signals if s.direction == "bullish")
        bearish = sum(s.strength for s in signals if s.direction == "bearish")
        total = bullish + bearish
        score = 2 * (bullish - bearish) / total if total > 0 else 0
        confidence = min(0.9, len(signals) / 10)

        direction = "看涨" if score > 0.3 else ("看跌" if score < -0.3 else "中性")
        return AnalysisResult(
            dimension=self.dimension,
            score=round(score, 2),
            confidence=round(confidence, 2),
            signals=signals,
            summary=f"技术面{direction}，综合评分 {score:+.1f}，共 {len(signals)} 个信号",
            details={"signal_count": len(signals), "bullish_count": sum(1 for s in signals if s.direction == "bullish"), "bearish_count": sum(1 for s in signals if s.direction == "bearish")},
        )

    def _trend(self, close: pd.Series) -> list[Signal]:
        signals = []
        if len(close) < 250:
            return signals

        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1]
        ma120 = close.rolling(120).mean().iloc[-1]
        current = close.iloc[-1]

        # MA alignment
        if current > ma20 > ma60 > ma120:
            signals.append(Signal("MA多头排列", "bullish", 0.8, "短中长期均线多头排列"))
        elif current < ma20 < ma60 < ma120:
            signals.append(Signal("MA空头排列", "bearish", 0.8, "短中长期均线空头排列"))
        else:
            if current > ma20:
                signals.append(Signal("短期均线上方", "bullish", 0.3, "价格站上20日均线"))
            else:
                signals.append(Signal("短期均线下方", "bearish", 0.3, "价格跌破20日均线"))
            if ma20 > ma60:
                signals.append(Signal("中期趋势向上", "bullish", 0.3, "20日均线在60日均线上方"))
            elif ma20 < ma60:
                signals.append(Signal("中期趋势向下", "bearish", 0.3, "20日均线在60日均线下方"))

        # ADX
        adx = ta.trend.ADXIndicator(close, close, close, window=14)
        adx_val = adx.adx().iloc[-1]
        if not np.isnan(adx_val):
            if adx_val > 40:
                signals.append(Signal("强趋势", "neutral", 0.5, f"ADX={adx_val:.0f}，趋势明确"))
            elif adx_val > 25:
                signals.append(Signal("中等趋势", "neutral", 0.3, f"ADX={adx_val:.0f}"))
            else:
                signals.append(Signal("震荡市", "neutral", 0.3, f"ADX={adx_val:.0f}，无明显趋势"))

        return signals

    def _momentum(self, close: pd.Series) -> list[Signal]:
        signals = []
        if len(close) < 14:
            return signals

        # RSI
        rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
        if not np.isnan(rsi):
            if rsi < 30:
                signals.append(Signal("RSI超卖", "bullish", 0.7, f"RSI={rsi:.0f}，超卖区域"))
            elif rsi > 70:
                signals.append(Signal("RSI超买", "bearish", 0.7, f"RSI={rsi:.0f}，超买区域"))
            elif rsi < 35:
                signals.append(Signal("RSI偏弱", "bullish", 0.3, f"RSI={rsi:.0f}，接近超卖"))
            elif rsi > 65:
                signals.append(Signal("RSI偏强", "bearish", 0.3, f"RSI={rsi:.0f}，接近超买"))
            else:
                signals.append(Signal("RSI中性", "neutral", 0.2, f"RSI={rsi:.0f}"))

        # MACD
        macd = ta.trend.MACD(close).macd().iloc[-1]
        macd_signal = ta.trend.MACD(close).macd_signal().iloc[-1]
        macd_diff = ta.trend.MACD(close).macd_diff().iloc[-1]
        if not any(np.isnan(x) for x in [macd, macd_signal, macd_diff]):
            if macd_diff > 0:
                if macd > 0:
                    signals.append(Signal("MACD强势多头", "bullish", 0.6, "MACD在零轴上方且金叉"))
                else:
                    signals.append(Signal("MACD弱势反弹", "bullish", 0.3, "MACD在零轴下方金叉"))
            else:
                if macd < 0:
                    signals.append(Signal("MACD强势空头", "bearish", 0.6, "MACD在零轴下方且死叉"))
                else:
                    signals.append(Signal("MACD回调", "bearish", 0.3, "MACD在零轴上方死叉"))

        # Price vs MA20
        ma20 = close.rolling(20).mean().iloc[-1]
        pct_from_ma20 = (close.iloc[-1] / ma20 - 1) * 100
        if abs(pct_from_ma20) > 10:
            direction = "bullish" if pct_from_ma20 < -10 else "bearish"
            signals.append(Signal("均值回归压力", direction, 0.5, f"偏离MA20 {pct_from_ma20:+.1f}%"))

        return signals

    def _volume_signal(self, close: pd.Series, volume: pd.Series) -> list[Signal]:
        signals = []
        if len(close) < 20 or len(volume) < 20:
            return signals

        avg_vol = volume.rolling(20).mean().iloc[-1]
        latest_vol = volume.iloc[-1]
        vol_ratio = latest_vol / avg_vol if avg_vol > 0 else 1

        if vol_ratio > 2.5:
            direction = "bullish" if close.iloc[-1] > close.iloc[-2] else "bearish"
            signals.append(Signal("天量", direction, 0.7, f"成交量放大 {vol_ratio:.1f} 倍"))
        elif vol_ratio > 1.5:
            direction = "bullish" if close.iloc[-1] > close.iloc[-2] else "bearish"
            signals.append(Signal("放量", direction, 0.4, f"成交量放大 {vol_ratio:.1f} 倍"))
        elif vol_ratio < 0.5:
            signals.append(Signal("缩量", "neutral", 0.3, f"成交量萎缩至 {vol_ratio:.1f} 倍"))

        # OBV trend
        obv = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
        obv_ma = obv.rolling(20).mean()
        if len(obv) > 20 and len(obv_ma) > 0:
            if obv.iloc[-1] > obv_ma.iloc[-1]:
                signals.append(Signal("OBV强势", "bullish", 0.3, "能量潮在均线上方"))
            else:
                signals.append(Signal("OBV弱势", "bearish", 0.3, "能量潮在均线下方"))

        return signals

    def _support_resistance(self, close: pd.Series) -> list[Signal]:
        signals = []
        if len(close) < 60:
            return signals

        current = close.iloc[-1]
        recent = close.iloc[-60:]
        recent_high = recent.max()
        recent_low = recent.min()
        range_pct = (recent_high / recent_low - 1) * 100

        near_high = current / recent_high if recent_high > 0 else 1
        near_low = current / recent_low if recent_low > 0 else 1

        if near_high > 0.97:
            signals.append(Signal("接近阻力位", "bearish", 0.5, f"距60日高 {recent_high:.2f} 仅 {(near_high-1)*100:+.1f}%"))
        if near_low < 1.03:
            signals.append(Signal("接近支撑位", "bullish", 0.5, f"距60日低 {recent_low:.2f} 仅 {(near_low-1)*100:+.1f}%"))

        if range_pct < 10:
            signals.append(Signal("窄幅整理", "neutral", 0.4, f"60日振幅仅 {range_pct:.1f}%，即将突破"))

        return signals
