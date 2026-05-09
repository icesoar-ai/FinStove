"""Macro data aggregator: combines AKShare (CN) + FRED (US) + YFinance (DXY).

Usage:
    from src.data.macro_data import get_all_macro_data
    data = get_all_macro_data()
"""
from typing import Optional
import os

import pandas as pd

from src.data.providers.akshare import AKShareProvider
from src.data.providers.yfinance import YFinanceProvider
from src.data.cache import DataCache
from src.data.storage import ParquetStorage

# Optional imports
try:
    from src.data.providers.fred import FREDProvider
    HAS_FRED = True
except ImportError:
    HAS_FRED = False

try:
    from src.data.providers.coingecko import CoinGeckoProvider
    HAS_COINGECKO = True
except ImportError:
    HAS_COINGECKO = False


class MacroDataAggregator:
    """Aggregate macro data from multiple sources."""

    def __init__(self, cache: Optional[DataCache] = None, storage: Optional[ParquetStorage] = None):
        self._ak = AKShareProvider(cache=cache, storage=storage)
        self._yf = YFinanceProvider(cache=cache, storage=storage)

        if HAS_FRED:
            self._fred = FREDProvider(cache=cache, storage=storage)
        else:
            self._fred = None

        if HAS_COINGECKO:
            self._cg = CoinGeckoProvider(cache=cache, storage=storage)
        else:
            self._cg = None

    def get_all_macro_data(self) -> dict:
        """Fetch all macro data from CN + US sources.

        Returns dict with keys:
            - policy_rate: dict[country -> float]
            - cpi_yoy: dict[country -> float]
            - ppi_yoy: dict[country -> float]
            - gdp_growth: dict[country -> float]
            - pmi: dict[country -> float]
            - yield_curve: dict[country -> dict[tenor -> float]]
            - dxy: float
            - shibor: dict[tenor -> float]
            - lpr: dict[str -> float]  (1Y, 5Y)
            - m2_growth: float
            - m1_growth: float
            - social_financing: float  (亿元)
            - fx_reserves: float  (USD billions)
            - exports_yoy: float
            - imports_yoy: float
            - industrial_production: float
            - retail_sales_growth: float
            - pmi_caixin: float
            - pmi_non_man: float
            - unemployment: dict[country -> float]
            - crypto: dict
            - gold: float
            - oil_wti: float
            - oil_brent: float
            - forex: dict
            - global_indices: dict
        """
        result: dict = {
            "policy_rate": {},
            "cpi_yoy": {},
            "ppi_yoy": {},
            "gdp_growth": {},
            "pmi": {},
            "yield_curve": {},
            "shibor": {},
            "lpr": {},
            "unemployment": {},
        }

        # ---- China data (AKShare) ----
        # CPI
        cpi_yoy_cn = self._get_cpi_yoy_cn()
        if cpi_yoy_cn is not None:
            result["cpi_yoy"]["CN"] = cpi_yoy_cn

        # PPI
        ppi_cn = self._get_ppi_yoy_cn()
        if ppi_cn is not None:
            result["ppi_yoy"]["CN"] = ppi_cn

        # PMI (official)
        pmi_cn = self._get_pmi_cn()
        if pmi_cn is not None:
            result["pmi"]["CN"] = pmi_cn

        # PMI (Caixin manufacturing)
        pmi_cx = self._get_caixin_pmi()
        if pmi_cx is not None:
            result["pmi_caixin"] = pmi_cx

        # PMI (non-manufacturing)
        pmi_nm = self._get_non_man_pmi()
        if pmi_nm is not None:
            result["pmi_non_man"] = pmi_nm

        # GDP
        gdp_cn = self._get_gdp_cn()
        if gdp_cn is not None:
            result["gdp_growth"]["CN"] = gdp_cn

        # SHIBOR
        shibor = self._get_shibor()
        if shibor:
            result["shibor"] = shibor

        # LPR
        lpr = self._get_lpr()
        if lpr:
            result["lpr"] = lpr

        # Money supply
        m2_growth, m1_growth = self._get_money_supply_growth()
        if m2_growth is not None:
            result["m2_growth"] = m2_growth
        if m1_growth is not None:
            result["m1_growth"] = m1_growth

        # Social financing
        sf = self._get_social_financing_latest()
        if sf is not None:
            result["social_financing"] = sf

        # FX reserves
        fx = self._get_fx_reserves_latest()
        if fx is not None:
            result["fx_reserves"] = fx

        # Trade
        exports = self._get_exports_yoy_latest()
        if exports is not None:
            result["exports_yoy"] = exports

        imports = self._get_imports_yoy_latest()
        if imports is not None:
            result["imports_yoy"] = imports

        # Industrial production
        ip_val = self._get_industrial_production_latest()
        if ip_val is not None:
            result["industrial_production"] = ip_val

        # Retail sales
        rs_growth = self._get_retail_sales_growth_latest()
        if rs_growth is not None:
            result["retail_sales_growth"] = rs_growth

        # Unemployment
        unemp_cn = self._get_unemployment_cn_latest()
        if unemp_cn is not None:
            result["unemployment"]["CN"] = unemp_cn

        # China bond yield curve
        cn_yield = self._get_cn_yield_curve()
        if cn_yield:
            result["yield_curve"]["CN"] = cn_yield

        # ---- US data (FRED) ----
        if self._fred:
            us_data = self._fred.get_all_macro_data()

            if us_data.get("policy_rate"):
                result["policy_rate"]["US"] = us_data["policy_rate"]

            if us_data.get("cpi_yoy"):
                result["cpi_yoy"]["US"] = us_data["cpi_yoy"]

            if us_data.get("gdp_growth"):
                result["gdp_growth"]["US"] = us_data["gdp_growth"]

            if us_data.get("pmi"):
                result["pmi"]["US"] = us_data["pmi"]

            if us_data.get("yield_curve"):
                result["yield_curve"]["US"] = us_data["yield_curve"]

            if us_data.get("unemployment"):
                result["unemployment"]["US"] = us_data["unemployment"]

        # ---- DXY (YFinance) ----
        dxy = self._yf.get_dxy_current()
        if dxy is not None:
            result["dxy"] = dxy

        # ---- Crypto (CoinGecko) ----
        if self._cg and HAS_COINGECKO:
            result["crypto"] = self._get_crypto_summary()

        # ---- Gold & Oil (from Parquet) ----
        gold = self._get_latest_close("commodity", "global", "GC", "daily")
        if gold is not None:
            result["gold"] = gold

        oil_wti = self._get_latest_close("commodity", "global", "CL", "daily")
        if oil_wti is not None:
            result["oil_wti"] = oil_wti

        oil_brent = self._get_latest_close("commodity", "global", "BZ", "daily")
        if oil_brent is not None:
            result["oil_brent"] = oil_brent

        # ---- VIX (from Parquet) ----
        vix_val = self._get_latest_close("index", "us", "VIX", "daily")
        if vix_val is not None:
            result["vix"] = vix_val

        # ---- Forex snapshot (from Parquet) ----
        result["forex"] = {}
        for pair in ["USDCNY", "EURCNY", "JPYCNY"]:
            rate = self._get_latest_close("forex", "global", pair, "daily")
            if rate is not None:
                result["forex"][pair] = rate

        # ---- Global index snapshot (from Parquet) ----
        result["global_indices"] = {}
        index_targets = [
            ("us", "SPX"), ("us", "NDX"), ("hk", "HSI"),
            ("jp", "N225"), ("de", "DAX"), ("uk", "FTSE"), ("fr", "CAC"),
        ]
        for mkt, sym in index_targets:
            val = self._get_latest_close("index", mkt, sym, "daily")
            if val is not None:
                result["global_indices"][f"{mkt}_{sym}"] = val

        return result

    # ---- Helpers ----

    def _get_latest_close(self, asset_type: str, market: str, symbol: str, data_type: str) -> Optional[float]:
        """Read latest close price from Parquet storage."""
        try:
            storage = ParquetStorage()
            df = storage.load(asset_type, market, symbol, data_type)
            if df is not None and not df.empty and "close" in df.columns:
                return float(df.iloc[-1]["close"])
        except Exception:
            pass
        return None

    @staticmethod
    def _latest_value(df: pd.DataFrame, col: str = "今值") -> Optional[float]:
        """Extract last non-NaN value from a ''商品/日期/今值/预测值/前值'' format dataframe."""
        if df is None or df.empty or col not in df.columns:
            return None
        for val in reversed(df[col].tolist()):
            if pd.notna(val) and val != 0:
                return float(val)
        return None

    def _get_cpi_yoy_cn(self) -> Optional[float]:
        try:
            return self._latest_value(self._ak.get_cpi())
        except Exception:
            return None

    def _get_ppi_yoy_cn(self) -> Optional[float]:
        try:
            return self._latest_value(self._ak.get_ppi())
        except Exception:
            return None

    def _get_pmi_cn(self) -> Optional[float]:
        try:
            return self._latest_value(self._ak.get_pmi())
        except Exception:
            return None

    def _get_caixin_pmi(self) -> Optional[float]:
        try:
            return self._latest_value(self._ak.get_caixin_pmi())
        except Exception:
            return None

    def _get_non_man_pmi(self) -> Optional[float]:
        try:
            return self._latest_value(self._ak.get_non_man_pmi())
        except Exception:
            return None

    def _get_gdp_cn(self) -> Optional[float]:
        try:
            return self._latest_value(self._ak.get_gdp_cn())
        except Exception:
            return None

    def _get_shibor(self) -> dict:
        return self._ak.get_shibor_latest()

    def _get_lpr(self) -> dict:
        try:
            df = self._ak.get_lpr()
            if df is None or df.empty:
                return {}
            result = {}
            for col, key in [("LPR1Y", "1Y"), ("LPR5Y", "5Y")]:
                if col in df.columns:
                    for val in reversed(df[col].tolist()):
                        if pd.notna(val):
                            result[key] = float(val)
                            break
            return result
        except Exception:
            return {}

    def _get_money_supply_growth(self) -> tuple:
        """Return (M2_growth, M1_growth) in percentage points."""
        try:
            df = self._ak.get_money_supply()
            if df is None or df.empty:
                return None, None
            m2_col = "货币和准货币(M2)-同比增长"
            m1_col = "货币(M1)-同比增长"
            m2, m1 = None, None
            for col, vals in [(m2_col, []), (m1_col, [])]:
                if col in df.columns:
                    for v in reversed(df[col].tolist()):
                        if pd.notna(v):
                            if col == m2_col:
                                m2 = float(v)
                            else:
                                m1 = float(v)
                            break
            return m2, m1
        except Exception:
            return None, None

    def _get_social_financing_latest(self) -> Optional[float]:
        """Latest aggregate social financing increment (亿元)."""
        try:
            df = self._ak.get_social_financing()
            if df is None or df.empty:
                return None
            col = "社会融资规模增量"
            if col in df.columns:
                for val in reversed(df[col].tolist()):
                    if pd.notna(val):
                        return float(val)
            return None
        except Exception:
            return None

    def _get_fx_reserves_latest(self) -> Optional[float]:
        """Latest FX reserves in USD billions."""
        try:
            return self._latest_value(self._ak.get_fx_reserves())
        except Exception:
            return None

    def _get_exports_yoy_latest(self) -> Optional[float]:
        try:
            return self._latest_value(self._ak.get_exports_yoy())
        except Exception:
            return None

    def _get_imports_yoy_latest(self) -> Optional[float]:
        try:
            return self._latest_value(self._ak.get_imports_yoy())
        except Exception:
            return None

    def _get_industrial_production_latest(self) -> Optional[float]:
        try:
            return self._latest_value(self._ak.get_industrial_production())
        except Exception:
            return None

    def _get_retail_sales_growth_latest(self) -> Optional[float]:
        """Latest retail sales YoY growth rate."""
        try:
            df = self._ak.get_retail_sales()
            if df is None or df.empty:
                return None
            col = "同比增长"
            if col in df.columns:
                for val in reversed(df[col].tolist()):
                    if pd.notna(val):
                        return float(val)
            return None
        except Exception:
            return None

    def _get_unemployment_cn_latest(self) -> Optional[float]:
        """Get latest urban unemployment rate from AKShare.

        macro_china_urban_unemployment returns breakdown by household registration
        (户籍). We take the national urban survey rate if available, otherwise
        average the latest month's values as a proxy.
        """
        try:
            df = self._ak.get_unemployment_cn()
            if df is None or df.empty:
                return None
            # Prefer "全国城镇调查失业率" if present
            if "item" in df.columns:
                overall = df[df["item"] == "全国城镇调查失业率"]
                if not overall.empty and "value" in overall.columns:
                    for val in reversed(overall["value"].tolist()):
                        if pd.notna(val):
                            return float(val)
                # Fallback: any row with "失业率" (take latest date, average if multiple)
                unemp_rows = df[df["item"].str.contains("失业率", na=False)]
                if not unemp_rows.empty and "value" in unemp_rows.columns:
                    latest_date = unemp_rows["date"].max()
                    latest = unemp_rows[unemp_rows["date"] == latest_date]
                    vals = [float(v) for v in latest["value"].tolist() if pd.notna(v)]
                    if vals:
                        return sum(vals) / len(vals)
            return None
        except Exception:
            return None

    def _get_cn_yield_curve(self) -> dict:
        """Get China treasury bond yield curve (国债收益率)."""
        try:
            df = self._ak.get_bond_yield_cn()
            if df is None or df.empty:
                return {}
            # The latest row has the most recent data
            row = df.iloc[-1]
            curve = {}
            for tenor in ["3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"]:
                if tenor in row.index and pd.notna(row[tenor]):
                    curve[tenor] = float(row[tenor])
            return curve
        except Exception:
            return {}

    def _get_crypto_summary(self) -> dict:
        """Get summary crypto data for major coins."""
        if not self._cg:
            return {}

        result = {}
        for symbol in ["BTC", "ETH"]:
            data = self._cg.get_market_data(symbol)
            if data:
                result[symbol.lower()] = {
                    "price": data.get("price"),
                    "market_cap": data.get("market_cap"),
                    "change_24h": data.get("change_24h"),
                    "change_7d": data.get("change_7d"),
                }
        return result


def get_all_macro_data() -> dict:
    """Convenience function to get all macro data."""
    aggregator = MacroDataAggregator()
    return aggregator.get_all_macro_data()


def get_macro_data_for_analyzer() -> dict:
    """Get macro data formatted for MacroAnalyzer.

    This is the main entry point called by the CLI.
    """
    aggregator = MacroDataAggregator()
    raw = aggregator.get_all_macro_data()
    return raw
