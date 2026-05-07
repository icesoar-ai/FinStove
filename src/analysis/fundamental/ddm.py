from .base import ValuationMethod, ValuationResult


class DDMValuation(ValuationMethod):
    """Dividend Discount Model — Gordon Growth + Multi-stage DDM."""

    name = "DDM"

    def evaluate(self, financials: dict, market_data=None) -> ValuationResult:
        inc = financials.get("income", None)
        bs = financials.get("balance_sheet", None)
        cf = financials.get("cashflow", None)

        if inc is None or inc.empty:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无利润表数据"])

        try:
            dps = self._extract_dps(inc, cf)
            if dps is None:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.1, reason="数据缺失", warnings=["缺少股利数据，无法使用 DDM"])
            if dps <= 0:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.1, reason="模型不适用", warnings=["公司不分红，DDM 不适用"])

            growth = self._estimate_dividend_growth(inc, cf)
            growth = max(0.01, min(0.10, growth))
            required_return = 0.08
            terminal_g = 0.025

            if growth >= required_return:
                growth = required_return - 0.01

            gordon_value = dps * (1 + growth) / (required_return - growth)

            return ValuationResult(
                method=self.name,
                fair_value=round(gordon_value, 2),
                value_low=round(gordon_value * 0.75, 2),
                value_high=round(gordon_value * 1.25, 2),
                confidence=0.5 if dps > 0 else 0.1,
                assumptions={"dps": round(dps, 2), "growth": round(growth, 3), "required_return": required_return},
            )
        except Exception as e:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=[f"DDM计算异常: {e}"])

    def _extract_dps(self, inc, cf) -> float | None:
        # Try DPS from income statement or cash flow
        for df_source in [inc, cf]:
            if df_source is None or df_source.empty:
                continue
            for col in df_source.columns:
                col_l = str(col).lower()
                if "dps" in col_l or "每股股利" in col_l or "每股分红" in col_l:
                    vals = df_source[col].dropna()
                    if len(vals) > 0:
                        return float(vals.iloc[-1])
        # Estimate from payout ratio
        payout = self._extract_payout(inc, cf)
        if payout is None:
            return None  # Data missing, not zero dividend
        eps = self._extract_eps(inc)
        if eps and payout:
            return eps * payout
        return None

    def _extract_eps(self, inc) -> float | None:
        for col in inc.columns:
            col_l = str(col).lower()
            if "eps" in col_l or "每股收益" in col_l:
                vals = inc[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        return None

    def _extract_payout(self, inc, cf) -> float | None:
        import math
        ni = 0.0
        ni_found = False
        div_found = False
        for col in inc.columns:
            col_l = str(col).lower()
            if "净利" in col_l or "net_income" in col_l:
                val = inc[col].iloc[-1]
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    ni = float(val)
                    ni_found = True
        # Search for dividend payments in cash flow
        for df in ([cf] if cf is not None else []):
            for col in df.columns:
                col_l = str(col).lower()
                if "分配股利" in col_l or "dividend" in col_l or "分红" in col_l or "股利" in col_l:
                    val = df[col].iloc[-1]
                    if val is not None and not (isinstance(val, float) and math.isnan(val)):
                        div = abs(float(val))
                        div_found = True
        if not ni_found:
            return None  # Can't determine without net income
        if ni > 0 and div_found:
            return div / ni
        if ni > 0 and not div_found:
            return None  # Dividend data missing, can't estimate
        return 0.3

    def _estimate_dividend_growth(self, inc, cf) -> float:
        """Estimate sustainable dividend growth from earnings growth."""
        for col in inc.columns:
            col_l = str(col).lower()
            if "净利" in col_l or "net_income" in col_l:
                vals = inc[col].dropna().values
                if len(vals) >= 2 and vals[-1] > 0 and vals[0] > 0:
                    return min(0.10, max(0.01, (vals[-1] / vals[0]) ** (1 / len(vals)) - 1))
        return 0.03
