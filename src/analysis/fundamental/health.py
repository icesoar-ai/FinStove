import numpy as np

from .base import ValuationMethod, ValuationResult


class FinancialHealthCheck(ValuationMethod):
    """Financial health: Altman Z-Score, liquidity, leverage trends, ROE DuPont."""

    name = "Financial Health"

    def evaluate(self, financials: dict, market_data=None) -> ValuationResult:
        bs = financials.get("balance_sheet", None)
        inc = financials.get("income", None)

        if bs is None or bs.empty:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无资产负债表数据"])

        try:
            signals = []

            # Altman Z-Score (simplified for non-US firms)
            z = self._altman_z(bs, inc)
            if z is not None:
                if z > 3.0:
                    signals.append((f"Z={z:.1f}，财务安全", "bullish", 0.6))
                elif z > 1.8:
                    signals.append((f"Z={z:.1f}，灰色区域", "neutral", 0.4))
                else:
                    signals.append((f"Z={z:.1f}，财务困境风险", "bearish", 0.7))

            # Current ratio
            cr = self._current_ratio(bs)
            if cr is not None:
                if cr > 2.0:
                    signals.append((f"流动比率{cr:.1f}，流动性充裕", "bullish", 0.4))
                elif cr > 1.0:
                    signals.append((f"流动比率{cr:.1f}，可接受", "neutral", 0.3))
                else:
                    signals.append((f"流动比率{cr:.1f}，流动性紧张", "bearish", 0.5))

            # Quick ratio
            qr = self._quick_ratio(bs)
            if qr is not None:
                if qr > 1.0:
                    signals.append((f"速动比率{qr:.1f}，良好", "bullish", 0.3))
                elif qr < 0.5:
                    signals.append((f"速动比率{qr:.1f}，偏低", "bearish", 0.4))

            # D/E trend
            de = self._debt_equity(bs)
            if de is not None:
                if de < 0.5:
                    signals.append((f"D/E={de:.2f}，低杠杆", "bullish", 0.4))
                elif de < 1.5:
                    signals.append((f"D/E={de:.2f}，中等杠杆", "neutral", 0.3))
                else:
                    signals.append((f"D/E={de:.2f}，高杠杆", "bearish", 0.5))

            # ROE DuPont
            roe = self._roe(bs, inc)
            if roe is not None:
                if roe > 0.20:
                    signals.append((f"ROE={roe:.1%}，优秀", "bullish", 0.5))
                elif roe > 0.10:
                    signals.append((f"ROE={roe:.1%}，良好", "bullish", 0.3))
                elif roe > 0.05:
                    signals.append((f"ROE={roe:.1%}，一般", "neutral", 0.3))
                elif roe > 0:
                    signals.append((f"ROE={roe:.1%}，偏低", "bearish", 0.3))
                else:
                    signals.append((f"ROE={roe:.1%}，亏损", "bearish", 0.6))

            if not signals:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.1, warnings=["无法计算财务健康指标"])

            bullish = sum(s[2] for s in signals if s[1] == "bullish")
            bearish = sum(s[2] for s in signals if s[1] == "bearish")
            total = bullish + bearish
            score = (bullish - bearish) / total if total > 0 else 0

            return ValuationResult(
                method=self.name,
                fair_value=0, value_low=0, value_high=0,
                confidence=min(0.7, len(signals) / 6),
                assumptions={},
            )
        except Exception as e:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=[f"财务健康分析异常: {e}"])

    def _altman_z(self, bs, inc) -> float | None:
        """Simplified Z-Score for non-manufacturing firms."""
        try:
            wc = self._get_bs_value(bs, ["流动资产", "current_asset"])
            ta = self._get_bs_value(bs, ["总资产", "total_asset"])
            re = self._get_bs_value(bs, ["未分配利润", "留存收益", "retained_earning"])
            ebit = self._get_is_value(inc, ["营业利润", "ebit", "operating_profit"])
            equity = self._get_bs_value(bs, ["所有者权益", "equity", "净资产"])
            tl = self._get_bs_value(bs, ["总负债", "负债合计", "total_liab"])
            revenue = self._get_is_value(inc, ["营业总收入", "营业收入", "revenue"])

            if not all([wc, ta, re is not None, ebit, equity, tl, revenue]) or ta == 0 or tl == 0:
                return None

            a = 1.2 * wc / ta
            b = 1.4 * re / ta if re else 0
            c = 3.3 * ebit / ta
            d = 0.6 * equity / tl if equity else 0
            e_val = 1.0 * revenue / ta
            return a + b + c + d + e_val
        except Exception:
            return None

    def _current_ratio(self, bs) -> float | None:
        ca = self._get_bs_value(bs, ["流动资产", "current_asset"])
        cl = self._get_bs_value(bs, ["流动负债", "current_liab"])
        return ca / cl if ca and cl and cl > 0 else None

    def _quick_ratio(self, bs) -> float | None:
        ca = self._get_bs_value(bs, ["流动资产", "current_asset"])
        inv = self._get_bs_value(bs, ["存货", "inventory"])
        cl = self._get_bs_value(bs, ["流动负债", "current_liab"])
        if ca and cl and cl > 0:
            inv = inv or 0
            return (ca - inv) / cl
        return None

    def _debt_equity(self, bs) -> float | None:
        tl = self._get_bs_value(bs, ["总负债", "负债合计", "total_liab"])
        eq = self._get_bs_value(bs, ["所有者权益", "equity", "净资产"])
        return tl / eq if tl is not None and eq and eq > 0 else None

    def _roe(self, bs, inc) -> float | None:
        ni = self._get_is_value(inc, ["净利润", "net_income"])
        eq = self._get_bs_value(bs, ["所有者权益", "equity", "净资产"])
        return ni / eq if ni is not None and eq and eq > 0 else None

    def _get_bs_value(self, bs, keys: list[str]) -> float | None:
        if bs is None or bs.empty:
            return None
        for col in bs.columns:
            col_l = str(col).lower()
            if any(k.lower() in col_l for k in keys):
                vals = bs[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        return None

    def _get_is_value(self, inc, keys: list[str]) -> float | None:
        if inc is None or inc.empty:
            return None
        for col in inc.columns:
            col_l = str(col).lower()
            if any(k.lower() in col_l for k in keys):
                vals = inc[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        return None
