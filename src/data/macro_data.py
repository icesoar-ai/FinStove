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

        Returns dict matching what MacroAnalyzer expects:
            - policy_rate: dict[country -> float]
            - cpi_yoy: dict[country -> float]
            - gdp_growth: dict[country -> float]
            - pmi: dict[country -> float]
            - yield_curve: dict[country -> dict[tenor -> float]]
            - dxy: float
            - shibor: dict[tenor -> float]
            - unemployment: dict[country -> float] (US only for now)
            - crypto: dict (if CoinGecko available)
        """
        result: dict = {
            "policy_rate": {},
            "cpi_yoy": {},
            "gdp_growth": {},
            "pmi": {},
            "yield_curve": {},
            "shibor": {},
            "unemployment": {},
        }

        # ---- China data (AKShare) ----
        # CPI
        cpi_yoy_cn = self._get_cpi_yoy_cn()
        if cpi_yoy_cn is not None:
            result["cpi_yoy"]["CN"] = cpi_yoy_cn

        # PMI
        pmi_cn = self._get_pmi_cn()
        if pmi_cn is not None:
            result["pmi"]["CN"] = pmi_cn

        # GDP (AKShare doesn't provide directly, estimate from other sources)
        # Skip for now

        # SHIBOR
        shibor = self._get_shibor()
        if shibor:
            result["shibor"] = shibor

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

        return result

    def _get_cpi_yoy_cn(self) -> Optional[float]:
        """Get China CPI YoY from AKShare."""
        try:
            df = self._ak.get_cpi()
            if df is not None and not df.empty and "今值" in df.columns:
                # Find last non-NaN value
                for val in reversed(df["今值"].tolist()):
                    if pd.notna(val) and val != 0:
                        return float(val)
        except Exception:
            pass
        return None

    def _get_pmi_cn(self) -> Optional[float]:
        """Get China PMI from AKShare."""
        try:
            df = self._ak.get_pmi()
            if df is not None and not df.empty and "今值" in df.columns:
                # Find last non-NaN value
                for val in reversed(df["今值"].tolist()):
                    if pd.notna(val):
                        return float(val)
        except Exception:
            pass
        return None

    def _get_shibor(self) -> dict:
        """Get SHIBOR rates by tenor."""
        return self._ak.get_shibor_latest()

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

    # Format for MacroAnalyzer's _yield_curve, _policy_rates, etc.
    return raw
