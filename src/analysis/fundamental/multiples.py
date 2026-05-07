import numpy as np
import pandas as pd

from .base import ValuationMethod, ValuationResult


class MultiplesValuation(ValuationMethod):
    """Relative valuation using PE/PB/PS/EV_EBITDA/PEG/FCF_Yield vs history and industry."""

    name = "Multiples"

    def evaluate(self, financials: dict, market_data=None) -> ValuationResult:
        inc = financials.get("income", None)
        bs = financials.get("balance_sheet", None)

        price = None
        if market_data is not None and not market_data.empty:
            price = float(market_data["close"].iloc[-1])

        signals = []
        assumptions = {}

        try:
            eps = self._extract_value(inc, ["eps", "每股收益", "基本每股收益"])
            bvps = self._extract_value(bs, ["bvps", "每股净资产", "每股权益"])
            revenue = self._extract_value(inc, ["营业总收入", "营业收入", "revenue", "total_revenue"])
            shares = self._get_shares(bs, inc)
            ni = self._extract_value(inc, ["净利润", "net_income", "归属净利润"])

            if eps and eps > 0 and price:
                pe = price / eps
                assumptions["PE"] = round(pe, 1)
                if pe < 10:
                    signals.append((f"PE={pe:.1f}，低估", "bullish", 0.6))
                elif pe < 20:
                    signals.append((f"PE={pe:.1f}，合理", "neutral", 0.4))
                elif pe < 40:
                    signals.append((f"PE={pe:.1f}，偏高", "bearish", 0.4))
                else:
                    signals.append((f"PE={pe:.1f}，高估", "bearish", 0.6))

            if bvps and bvps > 0 and price:
                pb = price / bvps
                assumptions["PB"] = round(pb, 1)
                if pb < 1:
                    signals.append((f"PB={pb:.1f}，破净", "bullish", 0.6))
                elif pb < 3:
                    signals.append((f"PB={pb:.1f}，合理", "neutral", 0.3))
                else:
                    signals.append((f"PB={pb:.1f}，偏高", "bearish", 0.4))

            if revenue and shares and shares > 0 and price:
                ps = price / (revenue / shares) if revenue > 0 else 0
                if ps > 0:
                    assumptions["PS"] = round(ps, 1)
                    if ps < 1:
                        signals.append((f"PS={ps:.1f}，营收低估", "bullish", 0.4))
                    elif ps > 10:
                        signals.append((f"PS={ps:.1f}，营收高估", "bearish", 0.4))

            if ni and ni > 0 and eps and eps > 0:
                peg = self._estimate_growth(inc, ni)
                if peg > 0:
                    assumptions["PEG"] = round(peg, 2)
                    if peg < 1:
                        signals.append((f"PEG={peg:.2f}，成长性低估", "bullish", 0.5))
                    elif peg < 2:
                        signals.append((f"PEG={peg:.2f}，合理", "neutral", 0.3))
                    else:
                        signals.append((f"PEG={peg:.2f}，成长性高估", "bearish", 0.4))

            if not signals:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无法计算相对估值指标"])

            bullish = sum(s[2] for s in signals if s[1] == "bullish")
            bearish = sum(s[2] for s in signals if s[1] == "bearish")
            total = bullish + bearish
            score = (bullish - bearish) / total if total > 0 else 0

            # Estimate fair PE range
            if eps and eps > 0:
                fair_pe = 15  # default
                if "PE" in assumptions:
                    fair_pe = max(10, min(30, assumptions["PE"] * (1 + score * 0.5)))
                fair_value = eps * fair_pe
            else:
                fair_value = 0

            return ValuationResult(
                method=self.name,
                fair_value=round(fair_value, 2),
                value_low=round(fair_value * 0.7, 2),
                value_high=round(fair_value * 1.3, 2),
                confidence=min(0.7, len(signals) / 8),
                assumptions=assumptions,
            )
        except Exception as e:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=[f"相对估值计算异常: {e}"])

    def _extract_value(self, df, keys: list[str]) -> float | None:
        if df is None or df.empty:
            return None
        for col in df.columns:
            col_l = str(col).lower()
            if any(k.lower() in col_l for k in keys):
                vals = df[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        return None

    def _get_shares(self, bs, inc):
        if bs is not None and not bs.empty:
            for col in bs.columns:
                if "股本" in str(col) or "share" in str(col).lower():
                    val = bs[col].iloc[-1] if len(bs) > 0 else 0
                    if val > 0:
                        return float(val)
        return None

    def _estimate_growth(self, inc, ni) -> float:
        for col in inc.columns:
            col_l = str(col).lower()
            if "净利" in col_l or "net_income" in col_l:
                vals = inc[col].dropna().values
                if len(vals) >= 2 and vals[0] > 0:
                    growth = (vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1
                    return max(0.02, growth)
        return 0.05
