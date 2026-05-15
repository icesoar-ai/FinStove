"""Baostock provider — free A-share data, no registration required.

http://baostock.com

可作为 AKShare 第三降级（仅获取日线 OHLCV，财报/分红格式不同暂不覆盖）。
"""
from datetime import date
from typing import Optional

import pandas as pd

from ..cache import DataCache


class BaostockProvider:
    """Baostock data provider for A-shares."""

    def __init__(self, cache: Optional[DataCache] = None):
        self._cache = cache
        import baostock as bs
        self._bs = bs

    def _ensure_login(self):
        lg = self._bs.login()
        return lg.error_code == "0"

    def get_daily(self, symbol: str, start: str = "20100101",
                  end: Optional[str] = None) -> pd.DataFrame:
        """Fetch daily OHLCV from Baostock. No storage I/O — Gateway handles persistence.

        Args:
            symbol: 6-digit A-share code, e.g. '600519'.
            start/end: dates in YYYYMMDD format.
        """
        if end is None:
            end = date.today().strftime("%Y-%m-%d")
        start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:8]}" if len(start) == 8 and start.isdigit() else start
        end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:8]}" if len(end) == 8 and end.isdigit() else end

        if not self._ensure_login():
            return pd.DataFrame()

        try:
            prefix = "sz" if symbol.startswith(("0", "3")) else "sh"
            code = f"{prefix}.{symbol}"
            rs = self._bs.query_history_k_data_plus(
                code, "date,open,high,low,close,volume,amount",
                start_date=start_fmt, end_date=end_fmt,
                frequency="d", adjustflag="2"
            )
            if rs.error_code != "0":
                return pd.DataFrame()
            df = rs.get_data()
            if df is None or df.empty:
                return pd.DataFrame()
            df.columns = ["date", "open", "high", "low", "close", "volume", "amount"]
            for col in ["open", "high", "low", "close", "volume", "amount"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df = df[df["open"].notna()]
        finally:
            self._bs.logout()

        return df if df is not None and not df.empty else pd.DataFrame()
