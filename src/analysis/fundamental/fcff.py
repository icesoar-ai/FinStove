import numpy as np

from .base import ValuationMethod, ValuationResult


class FCFFValuation(ValuationMethod):
    """Enterprise Free Cash Flow to Firm valuation using WACC discount rate."""

    name = "FCFF"

    def evaluate(self, financials: dict, market_data=None) -> ValuationResult:
        cf = financials.get("cashflow", None)
        inc = financials.get("income", None)
        bs = financials.get("balance_sheet", None)

        if cf is None or cf.empty:
            return ValuationResult(
                method=self.name, fair_value=0, value_low=0, value_high=0,
                confidence=0, reason="数据缺失", warnings=["无现金流量表数据"],
            )

        try:
            fcf = self._extract_fcf(cf, inc, bs)
            if fcf is None or len(fcf) < 2:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, reason="数据缺失", warnings=["无法提取自由现金流"])

            latest_fcf = fcf.iloc[-1]
            if latest_fcf <= 0:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.1, reason="模型不适用", warnings=["最新 FCF 为负，FCFF 模型不适用"])

            fcf_growth = (fcf.pct_change().dropna().median() if len(fcf) > 2 else 0.05)
            fcf_growth = min(fcf_growth, 0.25)

            shares = self._get_shares(bs, inc)
            if shares is None:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, reason="数据缺失", warnings=["无法确定总股本"])

            wacc = 0.08
            terminal_g = 0.025
            years = 5
            proj = [latest_fcf * (1 + fcf_growth) ** i for i in range(1, years + 1)]
            terminal = proj[-1] * (1 + terminal_g) / (wacc - terminal_g)

            pv = sum(cf / (1 + wacc) ** (i + 1) for i, cf in enumerate(proj))
            pv += terminal / (1 + wacc) ** years

            net_debt = self._get_net_debt(bs)
            equity_value = pv - net_debt
            fair_value = equity_value / shares

            if fair_value <= 0:
                return ValuationResult(
                    method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.6,
                    reason="结果不合理",
                    assumptions={"wacc": wacc, "terminal_growth": terminal_g, "fcf_growth": round(fcf_growth, 3), "latest_fcf": round(latest_fcf, 2)},
                    warnings=[f"企业价值{pv/1e8:.0f}亿，净债务{net_debt/1e8:.0f}亿，股权价值为负"],
                )

            return ValuationResult(
                method=self.name,
                fair_value=round(fair_value, 2),
                value_low=round(fair_value * 0.7, 2),
                value_high=round(fair_value * 1.3, 2),
                confidence=0.6,
                assumptions={"wacc": wacc, "terminal_growth": terminal_g, "fcf_growth": round(fcf_growth, 3), "latest_fcf": round(latest_fcf, 2)},
            )
        except Exception as e:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, reason="计算异常", warnings=[f"FCFF 计算异常：{e}"])

    def _extract_fcf(self, cf, inc, bs):
        """Extract FCF = Operating CF - CapEx."""
        if isinstance(cf, dict):
            cf = cf.get("cashflow", cf.get("cash_flow"))
        if cf is None:
            return None
        for col in cf.columns:
            col_l = str(col).lower()
            if "经营" in col_l or "operat" in col_l or "net_cash" in col_l:
                ocf = cf[col]
                for cap_col in cf.columns:
                    cap_l = str(cap_col).lower()
                    if "投资" in cap_l or "invest" in cap_l or "cap" in cap_l or "pp" in cap_l:
                        capex = cf[cap_col]
                        return ocf + capex
                return ocf * 0.5
        return None

    def _get_shares(self, bs, inc) -> float | None:
        if bs is not None and not bs.empty:
            for col in bs.columns:
                col_l = str(col).lower()
                if "股本" in col_l or "share" in col_l or "capital" in col_l:
                    val = bs[col].iloc[-1] if len(bs) > 0 else 0
                    if val > 0:
                        return float(val)
        return None

    def _get_net_debt(self, bs) -> float:
        if bs is None or bs.empty:
            return 0
        import math
        debt = 0.0
        cash = 0.0
        for col in bs.columns:
            col_l = str(col).lower()
            val = bs[col].iloc[-1] if len(bs) > 0 else 0
            if "负债" in col_l or "debt" in col_l or "borrow" in col_l or "bond" in col_l:
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    debt += float(val or 0)
            if "现金" in col_l or "cash" in col_l or "货币" in col_l:
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    cash += float(val or 0)
        return debt - cash
