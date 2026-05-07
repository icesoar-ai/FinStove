from .base import ValuationMethod, ValuationResult


class ResidualIncomeValuation(ValuationMethod):
    """Residual Income Model (Ohlson): BV + ∑(RI/(1+r)^t)."""

    name = "Residual Income"

    def evaluate(self, financials: dict, market_data=None) -> ValuationResult:
        bs = financials.get("balance_sheet", None)
        inc = financials.get("income", None)

        if bs is None or bs.empty or inc is None or inc.empty:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["缺少资产负债表或利润表"])

        try:
            bv = self._extract_book_value(bs)
            eps = self._extract_eps(inc)
            shares = self._get_shares(bs, inc)

            if bv is None or eps is None or shares is None or shares <= 0:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无法提取关键财务数据"])

            bvps = bv / shares
            roe = eps / bvps if bvps > 0 else 0
            if roe < 0 or bvps <= 0:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.1, warnings=["ROE或BVPS为负"])

            required_return = 0.09
            years = 10
            terminal_roe = 0.12  # reversion to mean

            pv_ri = 0
            current_bvps = bvps
            for t in range(1, years + 1):
                decay = (years - t) / years
                ri_t = current_bvps * (roe * decay + terminal_roe * (1 - decay) - required_return)
                pv_ri += ri_t / (1 + required_return) ** t
                current_bvps *= (1 + roe * decay + terminal_roe * (1 - decay))

            terminal_ri = current_bvps * (terminal_roe - required_return) / required_return
            pv_terminal = terminal_ri / (1 + required_return) ** years

            fair_value = bvps + pv_ri + pv_terminal

            return ValuationResult(
                method=self.name,
                fair_value=round(max(0, fair_value), 2),
                value_low=round(max(0, fair_value * 0.7), 2),
                value_high=round(max(0, fair_value * 1.3), 2),
                confidence=0.55,
                assumptions={"bvps": round(bvps, 2), "roe": f"{roe:.1%}", "required_return": required_return},
            )
        except Exception as e:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=[f"RI计算异常: {e}"])

    def _extract_book_value(self, bs) -> float | None:
        for col in bs.columns:
            col_l = str(col).lower()
            if "权益" in col_l or "equity" in col_l or "净资产" in col_l or "所有者权益" in col_l:
                return float(bs[col].iloc[-1] or 0)
        return None

    def _extract_eps(self, inc) -> float | None:
        for col in inc.columns:
            col_l = str(col).lower()
            if "eps" in col_l or "每股收益" in col_l:
                vals = inc[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        # Net income from income statement
        for col in inc.columns:
            col_l = str(col).lower()
            if "净利" in col_l or "net_income" in col_l:
                vals = inc[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        return None

    def _get_shares(self, bs, inc):
        if bs is not None and not bs.empty:
            for col in bs.columns:
                col_l = str(col).lower()
                if "股本" in col_l or "share" in col_l:
                    val = bs[col].iloc[-1] if len(bs) > 0 else 0
                    if val > 0:
                        return float(val)
        return None
