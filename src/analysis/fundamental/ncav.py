from .base import ValuationMethod, ValuationResult


class NCAVValuation(ValuationMethod):
    """Net Current Asset Value — Graham's liquidation value approach.

    NCAV = Current Assets - Total Liabilities
    Net-Net = NCAV / Shares
    """

    name = "NCAV"

    def evaluate(self, financials: dict, market_data=None) -> ValuationResult:
        bs = financials.get("balance_sheet", None)
        inc = financials.get("income", None)

        if bs is None or bs.empty:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无资产负债表数据"])

        try:
            current_assets = self._extract_current_assets(bs)
            total_liab = self._extract_total_liabilities(bs)
            shares = self._get_shares(bs, inc)

            if current_assets is None or total_liab is None:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无法提取资产/负债数据"])

            if shares is None or shares <= 0:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无法确定总股本"])

            ncav = current_assets - total_liab
            net_net = ncav / shares

            if net_net <= 0:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.2, warnings=["NCAV为负，公司净资产不足以覆盖负债"])

            return ValuationResult(
                method=self.name,
                fair_value=round(net_net, 2),
                value_low=round(net_net * 0.67, 2),  # Graham's 2/3 margin of safety
                value_high=round(net_net, 2),
                confidence=0.65,
                assumptions={"current_assets": round(current_assets, 2), "total_liabilities": round(total_liab, 2), "ncav": round(ncav, 2)},
            )
        except Exception as e:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=[f"NCAV计算异常: {e}"])

    def _extract_current_assets(self, bs) -> float | None:
        for col in bs.columns:
            col_l = str(col).lower()
            if "流动资产" in col_l or "current_asset" in col_l:
                return float(bs[col].iloc[-1] or 0)
        return None

    def _extract_total_liabilities(self, bs) -> float | None:
        for col in bs.columns:
            col_l = str(col).lower()
            if "总负债" in col_l or "负债合计" in col_l or "total_liab" in col_l:
                return float(bs[col].iloc[-1] or 0)
        # Sum long-term + current liabilities
        total = 0
        for col in bs.columns:
            col_l = str(col).lower()
            if "负债" in col_l or "liab" in col_l or "debt" in col_l:
                total += float(bs[col].iloc[-1] or 0)
        return total if total > 0 else None

    def _get_shares(self, bs, inc):
        if bs is not None and not bs.empty:
            for col in bs.columns:
                col_l = str(col).lower()
                if "股本" in col_l or "share" in col_l or "capital" in col_l:
                    val = bs[col].iloc[-1] if len(bs) > 0 else 0
                    if val > 0:
                        return float(val)
        return None
