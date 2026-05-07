from datetime import date, timedelta
from typing import Optional

import pandas as pd

from ..cache import DataCache
from ..normalizer import standardize
from ..storage import ParquetStorage


class AKShareProvider:
    def __init__(self, cache: Optional[DataCache] = None, storage: Optional[ParquetStorage] = None):
        self._cache = cache
        self._storage = storage or ParquetStorage()
        import akshare as ak
        self._ak = ak

    def _cached(self, method: str, ttl: int, fn, *args, **kwargs) -> pd.DataFrame:
        """Fetch with diskcache as API-call cache (avoid repeated API hits)."""
        if self._cache:
            cached = self._cache.get("akshare", method, *args, **kwargs)
            if cached is not None:
                return cached
        df = fn(*args, **kwargs)
        if df is None or df.empty:
            return pd.DataFrame()
        df = standardize(df)
        if self._cache:
            self._cache.set("akshare", method, df, *args, ttl=ttl, **kwargs)
        return df

    # ---- Stock OHLCV (with Parquet incremental) ----

    def get_daily(self, symbol: str, start: str = "20100101", end: Optional[str] = None,
                  market: str = "cn") -> pd.DataFrame:
        if end is None:
            end = date.today().strftime("%Y%m%d")

        # Check Parquet for existing data
        existing = self._storage.load("stock", market, symbol, "daily")
        if not existing.empty:
            # Find last date in existing data
            _, last_date = self._storage.get_date_range("stock", market, symbol, "daily")
            if last_date:
                # Only fetch from day after last date
                start = (last_date + timedelta(days=1)).strftime("%Y%m%d")
                if start >= end:
                    return existing  # Already up to date

        # Fetch new data
        new_df = self._cached("get_daily", 86400, self._ak.stock_zh_a_hist, symbol, "daily", start, end, "qfq")

        if new_df is None or new_df.empty:
            return existing if not existing.empty else pd.DataFrame()

        # Merge and save
        return self._storage.merge_and_save(new_df, "stock", market, symbol, "daily")

    # ---- Stock Info ----
    def get_info(self, symbol: str) -> dict:
        try:
            df = self._ak.stock_individual_info_em(symbol=symbol)
            return dict(zip(df["item"], df["value"])) if not df.empty else {}
        except Exception:
            return {}

    # ---- Financial Statements ----
    def get_financials(self, symbol: str) -> dict[str, pd.DataFrame]:
        result = {}
        for name, fn in [("balance_sheet", self._ak.stock_balance_sheet_by_report_em),
                          ("income", self._ak.stock_profit_sheet_by_report_em),
                          ("cashflow", self._ak.stock_cash_flow_sheet_by_report_em)]:
            try:
                df = self._cached(name, 86400, fn, symbol)
                if df is not None and not df.empty:
                    self._storage.save(df, "stock", "cn", symbol, name)
                    result[name] = df
            except Exception:
                pass
        if not result:
            try:
                df = self._cached("income_abstract", 86400, self._ak.stock_financial_abstract_ths, symbol)
                if df is not None and not df.empty:
                    result["income"] = df
            except Exception:
                pass
        return result

    # ---- Major Indices ----
    def get_index_daily(self, symbol: str, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
        if end is None:
            end = date.today().strftime("%Y%m%d")
        index_map = {
            "000001": "sh000001", "399001": "sz399001", "000300": "sh000300",
            "000016": "sh000016", "399006": "sz399006", "000688": "sh000688", "000905": "sh000905",
        }
        sym = index_map.get(symbol, f"sh{symbol}" if symbol.startswith(("0", "6")) else f"sz{symbol}")
        return self._cached("get_index", 86400, self._ak.stock_zh_index_daily_em, sym, start, end)

    # ---- Northbound / Southbound Flow ----
    def get_northbound(self, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
        if end is None:
            end = date.today().strftime("%Y%m%d")
        return self._cached("northbound", 86400, self._ak.stock_hsgt_north_net_flow_in_em, start, end)

    def get_southbound(self, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
        if end is None:
            end = date.today().strftime("%Y%m%d")
        return self._cached("southbound", 86400, self._ak.stock_hsgt_south_net_flow_in_em, start, end)

    # ---- Macro (with Parquet) ----
    def get_shibor(self) -> pd.DataFrame:
        key = ("macro", "cn", "shibor", "daily")
        existing = self._storage.load(*key)
        if not existing.empty:
            _, last = self._storage.get_date_range(*key)
            if last and last >= date.today() - timedelta(days=1):
                return existing

        df = pd.DataFrame()
        try:
            df = self._cached("shibor", 86400, self._ak.rate_interbank, market="上海银行同业拆借市场", symbol="Shibor人民币")
        except Exception:
            pass

        if df is not None and not df.empty:
            return self._storage.merge_and_save(df, *key)
        return existing if not existing.empty else pd.DataFrame()

    def get_cpi(self) -> pd.DataFrame:
        key = ("macro", "cn", "cpi", "monthly")
        existing = self._storage.load(*key)
        if not existing.empty:
            return existing  # CPI updates monthly, cache is fine
        df = self._cached("cpi", 86400, self._ak.macro_china_cpi_yearly)
        if df is not None and not df.empty:
            return self._storage.merge_and_save(df, *key)
        return existing if not existing.empty else pd.DataFrame()

    def get_pmi(self) -> pd.DataFrame:
        key = ("macro", "cn", "pmi", "monthly")
        existing = self._storage.load(*key)
        if not existing.empty:
            return existing
        df = self._cached("pmi", 86400, self._ak.macro_china_pmi_yearly)
        if df is not None and not df.empty:
            return self._storage.merge_and_save(df, *key)
        return existing if not existing.empty else pd.DataFrame()
