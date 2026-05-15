"""FRED (Federal Reserve Economic Data) provider for US macroeconomic data.

Requires free API key from https://fred.stlouisfed.org/docs/api/api_key.html
Set via environment variable: FRED_API_KEY=your_key
"""
from typing import Optional
import os

import pandas as pd

from ..cache import DataCache


# FRED 系列 ID 映射
FRED_SERIES = {
    # 利率
    "FED_FUNDS_RATE": "FEDFUNDS",  # 联邦基金目标利率 (月)
    # 通胀
    "CPI YoY": "CPIAUCSL",  # CPI 全部项目 (月)
    "CORE_CPI": "CPILFESL",  # 核心 CPI (不含食品能源)
    # 增长
    "GDP": "GDP",  # 国内生产总值 (季)
    "GDP YoY": "GDPYOY",  # GDP 同比 (季)
    # 就业
    "UNEMPLOYMENT": "UNRATE",  # 失业率 (月)
    "NONFARM_PAYROLLS": "PAYEMS",  # 非农就业人数 (月)
    # 收益率曲线 (日)
    "TREASURY_30Y": "DGS30",  # 30 年期国债收益率
    "TREASURY_10Y": "DGS10",  # 10 年期国债收益率
    "TREASURY_5Y": "DGS5",  # 5 年期国债收益率
    "TREASURY_2Y": "DGS2",  # 2 年期国债收益率
    "TREASURY_1Y": "DGS1",  # 1 年期国债收益率
    "TREASURY_3M": "DGS3MO",  # 3 个月期国债收益率
    # 货币供应
    "M1": "M1SL",  # M1 货币供应 (周)
    "M2": "M2SL",  # M2 货币供应 (周)
    # 消费者信心
    "CONSUMER_SENTIMENT": "UMCSENT",  # 密歇根消费者信心指数 (月)
    # 采购经理指数
    "PMI_MANUFACTURING": "NAPM",  # ISM 制造业 PMI (月)
    "PMI_SERVICES": "NAPMSMI",  # ISM 非制造业 PMI (月)
    # 领先指标
    "LEI": "USLEI",  # 领先经济指数 (月)
}



class FREDProvider:
    """FRED macroeconomic data provider for US data."""

    def __init__(self, api_key: Optional[str] = None, cache: Optional[DataCache] = None):
        self._api_key = api_key or os.environ.get("FRED_API_KEY")
        self._cache = cache
        self._fred = None

    def _init_fred(self):
        if self._fred is None:
            try:
                from fredapi import Fred
                self._fred = Fred(api_key=self._api_key)
            except ImportError:
                raise ImportError("fredapi not installed. Install with: pip install fredapi")

    def _cached(self, series_id: str, fn) -> pd.DataFrame:
        """Cache FRED API responses in diskcache."""
        if self._cache:
            cached = self._cache.get("fred", series_id)
            if cached is not None:
                return cached
        df = fn()
        if df is None or df.empty:
            return pd.DataFrame()
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        if self._cache:
            self._cache.set("fred", series_id, df, ttl=86400 * 7)
        return df

    def get_series(self, series_id: str, start: Optional[str] = None) -> pd.DataFrame:
        """Fetch a single FRED series by ID. No storage I/O — Gateway handles persistence."""
        self._init_fred()

        def fetch():
            try:
                df = self._fred.get_series(series_id)
                df = df.to_frame("value")
                df.index.name = "date"
                df = df.reset_index()
                return df
            except Exception:
                return pd.DataFrame()

        df = self._cached(series_id, fetch)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_federal_funds_rate(self) -> Optional[float]:
        """Get current federal funds rate (most recent value)."""
        try:
            df = self.get_series(FRED_SERIES["FED_FUNDS_RATE"])
            if not df.empty:
                return float(df.iloc[-1]["value"])
        except Exception:
            pass
        return None

    def get_cpi_yoy(self) -> Optional[float]:
        """Get CPI year-over-year change (most recent value)."""
        try:
            df = self.get_series(FRED_SERIES["CPI YoY"])
            if len(df) >= 13:  # 需要至少 13 个月数据计算同比
                current = df.iloc[-1]["value"]
                year_ago = df.iloc[-13]["value"]
                return ((current - year_ago) / year_ago) * 100
        except Exception:
            pass
        return None

    def get_core_cpi_yoy(self) -> Optional[float]:
        """Get core CPI year-over-year change."""
        try:
            df = self.get_series(FRED_SERIES["CORE_CPI"])
            if len(df) >= 13:
                current = df.iloc[-1]["value"]
                year_ago = df.iloc[-13]["value"]
                return ((current - year_ago) / year_ago) * 100
        except Exception:
            pass
        return None

    def get_gdp_growth(self) -> Optional[float]:
        """Get GDP growth rate (quarterly, annualized)."""
        try:
            df = self.get_series(FRED_SERIES["GDP"])
            if len(df) >= 2:
                current = df.iloc[-1]["value"]
                prev = df.iloc[-2]["value"]
                return ((current - prev) / prev) * 100 * 4  # 年化
        except Exception:
            pass
        return None

    def get_gdp_yoy(self) -> Optional[float]:
        """Get GDP year-over-year growth rate."""
        try:
            df = self.get_series(FRED_SERIES["GDP YoY"])
            if not df.empty:
                return float(df.iloc[-1]["value"])
        except Exception:
            pass
        return None

    def get_unemployment_rate(self) -> Optional[float]:
        """Get current unemployment rate."""
        try:
            df = self.get_series(FRED_SERIES["UNEMPLOYMENT"])
            if not df.empty:
                return float(df.iloc[-1]["value"])
        except Exception:
            pass
        return None

    def get_yield_curve(self) -> dict[str, Optional[float]]:
        """Get Treasury yield curve: 3M, 1Y, 2Y, 5Y, 10Y, 30Y.

        Returns dict with tenor -> yield mappings.
        """
        result = {}
        mapping = {
            "30Y": FRED_SERIES["TREASURY_30Y"],
            "10Y": FRED_SERIES["TREASURY_10Y"],
            "5Y": FRED_SERIES["TREASURY_5Y"],
            "2Y": FRED_SERIES["TREASURY_2Y"],
            "1Y": FRED_SERIES["TREASURY_1Y"],
            "3M": FRED_SERIES["TREASURY_3M"],
        }
        for tenor, series_id in mapping.items():
            try:
                df = self.get_series(series_id)
                if not df.empty:
                    result[tenor] = float(df.iloc[-1]["value"])
                else:
                    result[tenor] = None
            except Exception:
                result[tenor] = None
        return result

    def get_pmi_manufacturing(self) -> Optional[float]:
        """Get ISM Manufacturing PMI."""
        try:
            df = self.get_series(FRED_SERIES["PMI_MANUFACTURING"])
            if not df.empty:
                return float(df.iloc[-1]["value"])
        except Exception:
            pass
        return None

    def get_pmi_services(self) -> Optional[float]:
        """Get ISM Non-manufacturing PMI (services)."""
        try:
            df = self.get_series(FRED_SERIES["PMI_SERVICES"])
            if not df.empty:
                return float(df.iloc[-1]["value"])
        except Exception:
            pass
        return None

    def get_consumer_sentiment(self) -> Optional[float]:
        """Get University of Michigan Consumer Sentiment Index."""
        try:
            df = self.get_series(FRED_SERIES["CONSUMER_SENTIMENT"])
            if not df.empty:
                return float(df.iloc[-1]["value"])
        except Exception:
            pass
        return None

    def get_all_macro_data(self) -> dict:
        """Fetch all US macro data in one call.

        Returns dict matching what MacroAnalyzer expects:
            - policy_rate: float (federal funds rate)
            - cpi_yoy: float (inflation)
            - gdp_growth: float (quarterly annualized)
            - unemployment: float
            - yield_curve: dict[tenor -> float]
            - pmi: float (manufacturing)
            - consumer_sentiment: float
        """
        result = {
            "policy_rate": self.get_federal_funds_rate(),
            "cpi_yoy": self.get_cpi_yoy(),
            "core_cpi_yoy": self.get_core_cpi_yoy(),
            "gdp_growth": self.get_gdp_growth(),
            "gdp_yoy": self.get_gdp_yoy(),
            "unemployment": self.get_unemployment_rate(),
            "yield_curve": self.get_yield_curve(),
            "pmi": self.get_pmi_manufacturing(),
            "pmi_services": self.get_pmi_services(),
            "consumer_sentiment": self.get_consumer_sentiment(),
        }
        return result

    def get_yield_curve_history(self) -> pd.DataFrame:
        """Get historical yield curve data for analysis."""
        self._init_fred()
        try:
            # Fetch all tenors
            data = {}
            for tenor, series_id in [
                ("30Y", FRED_SERIES["TREASURY_30Y"]),
                ("10Y", FRED_SERIES["TREASURY_10Y"]),
                ("5Y", FRED_SERIES["TREASURY_5Y"]),
                ("2Y", FRED_SERIES["TREASURY_2Y"]),
                ("1Y", FRED_SERIES["TREASURY_1Y"]),
            ]:
                df = self._fred.get_series(series_id)
                data[tenor] = df
            # Merge on date
            merged = pd.DataFrame(data)
            merged.index.name = "date"
            return merged.reset_index()
        except Exception:
            return pd.DataFrame()
