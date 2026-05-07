import numpy as np

from .base import ValuationMethod, ValuationResult


class FCFQualityCheck(ValuationMethod):
    """FCF quality metrics: FCF Yield, FCF Margin, FCF Conversion, EV/FCF."""

    name = "FCF Quality"

    def evaluate(self, financials: dict, market_data=None) -> ValuationResult:
        cf = financials.get("cashflow", None)
        inc = financials.get("income", None)
        bs = financials.get("balance_sheet", None)

        if cf is None or cf.empty:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无现金流数据"])

        try:
            ocf = self._extract_ocf(cf)
            capex = self._extract_capex(cf)
            ni = self._extract_net_income(inc)
            revenue = self._extract_revenue(inc)
            shares = self._get_shares(bs, inc)
            fcf = ocf + capex if (ocf is not None and capex is not None) else None

            price = None
            if market_data is not None and not market_data.empty:
                price = float(market_data["close"].iloc[-1])

            signals = []
            market_cap = price * shares if (price and shares) else None

            if fcf and fcf > 0 and market_cap:
                fcf_yield = (fcf / market_cap) * 100
                if fcf_yield > 8:
                    signals.append((f"FCF收益率{fcf_yield:.1f}%，极高", "bullish", 0.7))
                elif fcf_yield > 5:
                    signals.append((f"FCF收益率{fcf_yield:.1f}%，良好", "bullish", 0.5))
                elif fcf_yield > 2:
                    signals.append((f"FCF收益率{fcf_yield:.1f}%，一般", "neutral", 0.3))
                else:
                    signals.append((f"FCF收益率{fcf_yield:.1f}%，偏低", "bearish", 0.4))

            if fcf and revenue and revenue > 0:
                fcf_margin = (fcf / revenue) * 100
                if fcf_margin > 20:
                    signals.append((f"FCF率{fcf_margin:.1f}%，优秀", "bullish", 0.6))
                elif fcf_margin > 10:
                    signals.append((f"FCF率{fcf_margin:.1f}%，良好", "bullish", 0.4))
                elif fcf_margin > 0:
                    signals.append((f"FCF率{fcf_margin:.1f}%，一般", "neutral", 0.3))
                else:
                    signals.append((f"FCF率{fcf_margin:.1f}%，为负", "bearish", 0.5))

            if fcf and ni and ni > 0:
                conversion = fcf / ni
                if conversion > 1.5:
                    signals.append((f"FCF转化率{conversion:.1f}，利润含金量极高", "bullish", 0.6))
                elif conversion > 1.0:
                    signals.append((f"FCF转化率{conversion:.1f}，利润含金量好", "bullish", 0.4))
                elif conversion > 0.5:
                    signals.append((f"FCF转化率{conversion:.1f}，一般", "neutral", 0.3))
                else:
                    signals.append((f"FCF转化率{conversion:.1f}，利润含金量差", "bearish", 0.5))

            if not signals:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.1, warnings=["无法计算FCF质量指标"])

            bullish = sum(s[2] for s in signals if s[1] == "bullish")
            bearish = sum(s[2] for s in signals if s[1] == "bearish")
            total = bullish + bearish
            score = (bullish - bearish) / total if total > 0 else 0

            return ValuationResult(
                method=self.name,
                fair_value=0, value_low=0, value_high=0,
                confidence=min(0.7, len(signals) / 5),
                assumptions={"fcf_yield": f"{((fcf/market_cap)*100):.1f}%" if fcf and market_cap else "N/A"},
            )
        except Exception as e:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=[f"FCF质量分析异常: {e}"])

    def _extract_ocf(self, cf) -> float | None:
        for col in cf.columns:
            col_l = str(col).lower()
            if "经营" in col_l or "operating" in col_l:
                return float(cf[col].iloc[-1] or 0)
        return None

    def _extract_capex(self, cf) -> float | None:
        for col in cf.columns:
            col_l = str(col).lower()
            if "投资" in col_l or "investing" in col_l or "capital" in col_l:
                return float(cf[col].iloc[-1] or 0)
        return None

    def _extract_net_income(self, inc) -> float | None:
        if inc is None or inc.empty:
            return None
        for col in inc.columns:
            col_l = str(col).lower()
            if "净利" in col_l or "net_income" in col_l:
                return float(inc[col].iloc[-1] or 0)
        return None

    def _extract_revenue(self, inc) -> float | None:
        if inc is None or inc.empty:
            return None
        for col in inc.columns:
            col_l = str(col).lower()
            if "营收" in col_l or "revenue" in col_l or "收入" in col_l:
                return float(inc[col].iloc[-1] or 0)
        return None

    def _get_shares(self, bs, inc):
        if bs is not None and not bs.empty:
            for col in bs.columns:
                if "股本" in str(col) or "share" in str(col).lower():
                    val = bs[col].iloc[-1] if len(bs) > 0 else 0
                    if val > 0:
                        return float(val)
        return None
