from .base import ValuationMethod, ValuationResult


class EPVValuation(ValuationMethod):
    """Earnings Power Value (Greenwald) — sustainable earnings + surplus assets."""

    name = "EPV"

    def evaluate(self, financials: dict, market_data=None) -> ValuationResult:
        inc = financials.get("income", None)
        bs = financials.get("balance_sheet", None)

        if inc is None or inc.empty:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无利润表数据"])

        try:
            sustainable_earnings = self._estimate_sustainable_earnings(inc)
            if sustainable_earnings is None or sustainable_earnings <= 0:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.1, warnings=["无法确定可持续盈利"])

            wacc = 0.08
            epv_operations = sustainable_earnings / wacc

            # Surplus assets (simple: cash minus non-operating debt)
            surplus = self._estimate_surplus_assets(bs)
            total_value = epv_operations + surplus

            shares = self._get_shares(bs, inc)
            if shares is None or shares <= 0:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无法确定总股本"])

            fair_value = total_value / shares

            return ValuationResult(
                method=self.name,
                fair_value=round(fair_value, 2),
                value_low=round(fair_value * 0.7, 2),
                value_high=round(fair_value * 1.5, 2),
                confidence=0.55,
                assumptions={"sustainable_earnings": round(sustainable_earnings, 2), "wacc": wacc, "surplus": round(surplus, 2)},
            )
        except Exception as e:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=[f"EPV计算异常: {e}"])

    def _estimate_sustainable_earnings(self, inc) -> float | None:
        for col in inc.columns:
            col_l = str(col).lower()
            yield_cols = ["营业利润", "operating_income", "operating_profit", "ebit", "息税前利润"]
            if any(k in col_l for k in yield_cols):
                vals = inc[col].dropna()
                if len(vals) >= 3:
                    return float(vals.tail(3).mean())
                return float(vals.iloc[-1])

        # Fallback: net income with margin of safety
        for col in inc.columns:
            col_l = str(col).lower()
            if "净利" in col_l or "net_income" in col_l or "净利润" in col_l:
                vals = inc[col].dropna()
                if len(vals) >= 3:
                    return float(vals.tail(3).mean()) * 0.8
                return float(vals.iloc[-1]) * 0.8
        return None

    def _estimate_surplus_assets(self, bs) -> float:
        if bs is None or bs.empty:
            return 0
        cash = 0
        total_liab = 0
        for col in bs.columns:
            col_l = str(col).lower()
            if "货币" in col_l or "现金" in col_l or "cash" in col_l:
                cash = float(bs[col].iloc[-1] or 0)
            if "总负债" in col_l or "total_liab" in col_l or "负债合计" in col_l:
                total_liab = float(bs[col].iloc[-1] or 0)
        return max(0, cash - total_liab * 0.3)

    def _get_shares(self, bs, inc):
        if bs is not None and not bs.empty:
            for col in bs.columns:
                col_l = str(col).lower()
                if "股本" in col_l or "share" in col_l:
                    val = bs[col].iloc[-1] if len(bs) > 0 else 0
                    if val > 0:
                        return float(val)
        return None
