"""Baostock provider — free A-share data, no registration required.

http://baostock.com

可作为 AKShare 第三降级（仅获取日线 OHLCV，财报/分红格式不同暂不覆盖）。
"""
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from ..cache import DataCache
from ..normalizer import standardize
from ..storage import ParquetStorage


class BaostockProvider:
    """Baostock data provider for A-shares."""

    def __init__(self, cache: Optional[DataCache] = None, storage: Optional[ParquetStorage] = None):
        self._cache = cache
        self._storage = storage or ParquetStorage()
        import baostock as bs
        self._bs = bs

    def _ensure_login(self):
        lg = self._bs.login()
        return lg.error_code == "0"

    def get_daily(self, symbol: str, start: str = "20100101",
                  end: Optional[str] = None, store_symbol: Optional[str] = None) -> pd.DataFrame:
        """Fetch daily OHLCV from Baostock.

        Args:
            symbol: 6-digit A-share code, e.g. '600519'.
            start/end: dates in YYYY-MM-DD format.
            store_symbol: Parquet directory override (e.g. '600519_贵州茅台').
        """
        if end is None:
            end = date.today().strftime("%Y-%m-%d")
        start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:8]}" if len(start) == 8 and start.isdigit() else start
        end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:8]}" if len(end) == 8 and end.isdigit() else end

        store_sym = store_symbol or symbol

        # Check existing
        existing = self._storage.load("stock", "cn", store_sym, "daily")
        if not existing.empty:
            _, last = self._storage.get_date_range("stock", "cn", store_sym, "daily")
            if last and last >= date.today() - timedelta(days=1):
                return existing

        if not self._ensure_login():
            return existing if not existing.empty else pd.DataFrame()

        try:
            prefix = "sz" if symbol.startswith(("0", "3")) else "sh"
            code = f"{prefix}.{symbol}"
            rs = self._bs.query_history_k_data_plus(
                code, "date,open,high,low,close,volume,amount",
                start_date=start_fmt, end_date=end_fmt,
                frequency="d", adjustflag="2"  # forward-adjusted
            )
            if rs.error_code != "0":
                return existing if not existing.empty else pd.DataFrame()

            df = rs.get_data()
            if df is None or df.empty:
                return existing if not existing.empty else pd.DataFrame()

            # Standardize
            df.columns = ["date", "open", "high", "low", "close", "volume", "amount"]
            for col in ["open", "high", "low", "close", "volume", "amount"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df = df[df["open"].notna()]
        finally:
            self._bs.logout()

        return self._storage.merge_and_save(df, "stock", "cn", store_sym, "daily")
