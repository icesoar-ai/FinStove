import numpy as np

from .base import ValuationMethod, ValuationResult


class GrahamValuation(ValuationMethod):
    """Graham Number and Graham Revised Formula."""

    name = "Graham"

    def evaluate(self, financials: dict, market_data=None) -> ValuationResult:
        inc = financials.get("income", None)
        bs = financials.get("balance_sheet", None)

        if inc is None or inc.empty:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=["无利润表数据"])

        try:
            eps = self._extract_eps(inc, bs)
            bvps = self._extract_bvps(bs, inc)

            results = []
            if eps and eps > 0 and bvps and bvps > 0:
                graham_num = np.sqrt(22.5 * eps * bvps)
                results.append(("Graham Number", graham_num, 0.6))

            if eps and eps > 0:
                # Graham Revised: V = EPS * (8.5 + 2g) * 4.4 / Y
                growth = self._estimate_growth(inc, eps)
                aaa_yield = 0.05  # proxy for AAA bond yield
                graham_formula = eps * (8.5 + 2 * growth * 100) * 4.4 / (aaa_yield * 100)
                results.append(("Graham Formula", max(0, graham_formula), 0.5))

            if not results:
                return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0.1, warnings=["无法计算Graham估值"])

            avg_val = sum(r[1] for r in results) / len(results)
            return ValuationResult(
                method=self.name,
                fair_value=round(avg_val, 2),
                value_low=round(min(r[1] for r in results), 2),
                value_high=round(max(r[1] for r in results), 2),
                confidence=round(sum(r[2] for r in results) / len(results), 2),
                assumptions={"eps": round(eps, 2) if eps else None, "bvps": round(bvps, 2) if bvps else None},
            )
        except Exception as e:
            return ValuationResult(method=self.name, fair_value=0, value_low=0, value_high=0, confidence=0, warnings=[f"Graham计算异常: {e}"])

    def _extract_eps(self, inc, bs):
        for col in inc.columns:
            col_l = str(col).lower()
            if "eps" in col_l or "每股收益" in col_l or "基本每股收益" in col_l:
                vals = inc[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        # Estimate EPS from net income / shares
        ni = self._extract_ni(inc)
        shares = self._get_shares(bs, inc)
        if ni and shares and shares > 0:
            return ni / shares
        return None

    def _extract_bvps(self, bs, inc):
        for col in bs.columns:
            col_l = str(col).lower()
            if "bvps" in col_l or "每股净资产" in col_l or "每股权益" in col_l:
                vals = bs[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        # Estimate from equity / shares
        equity = self._extract_equity(bs)
        shares = self._get_shares(bs, inc)
        if equity and shares and shares > 0:
            return equity / shares
        return None

    def _extract_ni(self, inc):
        for col in inc.columns:
            col_l = str(col).lower()
            if "净利" in col_l or "net_income" in col_l or "净利润" in col_l:
                vals = inc[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        return None

    def _extract_equity(self, bs):
        for col in bs.columns:
            col_l = str(col).lower()
            if "权益" in col_l or "equity" in col_l or "净资产" in col_l:
                vals = bs[col].dropna()
                return float(vals.iloc[-1]) if len(vals) > 0 else None
        return None

    def _get_shares(self, bs, inc):
        if bs is not None and not bs.empty:
            for col in bs.columns:
                col_l = str(col).lower()
                if "股本" in col_l or "share" in col_l or "capital" in col_l:
                    val = bs[col].iloc[-1] if len(bs) > 0 else 0
                    if val > 0:
                        return float(val)
        return None

    def _estimate_growth(self, inc, eps) -> float:
        """Estimate growth rate from historical EPS."""
        for col in inc.columns:
            col_l = str(col).lower()
            if "eps" in col_l or "每股收益" in col_l:
                vals = inc[col].dropna().values
                if len(vals) >= 2 and vals[0] > 0:
                    return min(0.15, max(0.02, (vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1))
        return 0.05
