from .base import ValuationMethod, ValuationResult


class FCFEValuation(ValuationMethod):
    """Free Cash Flow to Equity valuation using Cost of Equity discount rate."""

    name = "FCFE"

    def evaluate(self, financials: dict, market_data=None) -> ValuationResult:
        cf = financials.get("cashflow", None)
        bs = financials.get("balance_sheet", None)
        inc = financials.get("income", None)

        if cf is None or cf.empty:
            return ValuationResult(
                method=self.name, fair_value=0, value_low=0, value_high=0,
                confidence=0, warnings=["无现金流量表数据"],
            )

        try:
            # FCFE = FCFF - interest*(1-tax) + net borrowing
            # Simplified: use dividends or estimate from earnings
            net_income = self._extract_net_income(inc)
            if net_income is None:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无法提取净利润"])

            shares = self._get_shares(bs, inc)
            if shares is None:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无法确定总股本"])

            eps = net_income / shares if shares > 0 else 0
            if eps <= 0:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.1, warnings=["EPS为负"])

            # Conservative: payout ratio estimate
            payout_ratio = 0.5
            growth = min(0.15, max(0.02, self._estimate_growth(inc)))
            coe = 0.09
            terminal_g = 0.025
            years = 5

            proj = [eps * payout_ratio * (1 + growth) ** i for i in range(1, years + 1)]
            terminal = proj[-1] * (1 + terminal_g) / (coe - terminal_g)
            pv = sum(cf / (1 + coe) ** (i + 1) for i, cf in enumerate(proj))
            pv += terminal / (1 + coe) ** years
            fair_value = pv

            return ValuationResult(
                method=self.name,
                fair_value=round(fair_value, 2),
                value_low=round(fair_value * 0.7, 2),
                value_high=round(fair_value * 1.3, 2),
                confidence=0.55,
                assumptions={"cost_of_equity": coe, "growth": round(growth, 3), "eps": round(eps, 2), "payout": payout_ratio},
            )
        except Exception as e:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=[f"FCFE计算异常: {e}"])

    def _extract_net_income(self, inc):
        if inc is None or inc.empty:
            return None
        for col in inc.columns:
            col_l = str(col).lower()
            if "净利" in col_l or "net_income" in col_l or "净利润" in col_l:
                vals = inc[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        # Try first numeric column
        for col in inc.columns:
            if inc[col].dtype in ("float64", "int64"):
                vals = inc[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        return None

    def _estimate_growth(self, inc) -> float:
        if inc is None or inc.empty:
            return 0.05
        ni = self._extract_net_income(inc)
        if ni is None:
            return 0.05
        # Look for historical net income in the income statement
        for col in inc.columns:
            col_l = str(col).lower()
            if "净利" in col_l or "net_income" in col_l or "净利润" in col_l:
                vals = inc[col].dropna().values
                if len(vals) >= 2:
                    cagr = (vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1 if vals[0] > 0 else 0.05
                    return max(0.02, min(0.15, cagr))
        return 0.05

    def _get_shares(self, bs, inc):
        if bs is not None and not bs.empty:
            for col in bs.columns:
                col_l = str(col).lower()
                if "股本" in col_l or "share" in col_l:
                    val = bs[col].iloc[-1] if len(bs) > 0 else 0
                    if val > 0:
                        return float(val)
        return None
