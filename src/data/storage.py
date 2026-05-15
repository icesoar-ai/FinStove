"""Parquet file storage for raw data.

Directory structure:
    data/{asset_type}/{market}/{symbol}/{data_type}.parquet

Examples:
    data/stock/cn/600519/daily.parquet
    data/index/us/SPX/daily.parquet
    data/macro/cn/cpi.parquet
    data/commodity/global/gold.parquet
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from src.utils.ticker import stock_dir

DEFAULT_DATA_DIR = Path.cwd() / "data"

# Asset types that use stock_dir for directory naming
_STOCK_LIKE = {"stock", "etf"}


class ParquetStorage:
    def __init__(self, base_dir: str | Path = DEFAULT_DATA_DIR):
        self.base = Path(base_dir)

    # ── Public path API ──────────────────────────────

    def dir_path(self, asset_type: str, market: str, code: str) -> Path:
        """Directory for a stock/ETF/etc: data/{asset}/{market}/{dir_name}/"""
        dir_name = stock_dir(code) if asset_type in _STOCK_LIKE else code
        return self.base / asset_type / market / dir_name

    def file_path(self, asset_type: str, market: str, code: str,
                  data_type: str = "", ext: str = ".parquet") -> Path:
        """Full file path: data/{asset}/{market}/{dir_name}/{data_type}{ext}"""
        path = self.dir_path(asset_type, market, code)
        if data_type:
            return path / f"{data_type}{ext}"
        return path

    # ── Internal ─────────────────────────────────────

    def _path(self, asset_type: str, market: str, symbol: str, data_type: str) -> Path:
        """Parquet file path. symbol is already the directory name (pre-resolved by caller)."""
        return self.base / asset_type / market / symbol / f"{data_type}.parquet"

    # ---- Read ----

    def load(self, asset_type: str, market: str, symbol: str, data_type: str) -> pd.DataFrame:
        path = self._path(asset_type, market, symbol, data_type)
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    # ---- Write ----

    def save(self, df: pd.DataFrame, asset_type: str, market: str, symbol: str, data_type: str) -> None:
        if df is None or df.empty:
            return
        path = self._path(asset_type, market, symbol, data_type)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            df.to_parquet(path, index=False)
        except Exception:
            # PyArrow type inference fails on mixed object columns.
            # Fallback: convert numeric-looking columns to float, rest to string.
            df_fixed = df.copy()
            for col in df_fixed.columns:
                if df_fixed[col].dtype == object:
                    try:
                        df_fixed[col] = pd.to_numeric(df_fixed[col], errors='ignore')
                    except Exception:
                        df_fixed[col] = df_fixed[col].astype(str, errors='ignore')
            df_fixed.to_parquet(path, index=False)

    # ---- Incremental merge ----

    def merge_and_save(self, new_df: pd.DataFrame, asset_type: str, market: str, symbol: str, data_type: str) -> pd.DataFrame:
        """Merge new data with existing Parquet, deduplicate by date, save back."""
        existing = self.load(asset_type, market, symbol, data_type)

        if existing.empty:
            if new_df is not None and not new_df.empty:
                self.save(new_df, asset_type, market, symbol, data_type)
            return new_df if new_df is not None else pd.DataFrame()

        # Combine and deduplicate
        combined = pd.concat([existing, new_df], ignore_index=True)

        # Find date column
        date_col = None
        for c in combined.columns:
            if c.lower() in ("date", "trade_date", "日期"):
                date_col = c
                break

        if date_col:
            combined[date_col] = pd.to_datetime(combined[date_col]).dt.date
            combined = combined.drop_duplicates(subset=[date_col], keep="last")
            combined = combined.sort_values(date_col).reset_index(drop=True)

        self.save(combined, asset_type, market, symbol, data_type)
        return combined

    # ---- Intraday merge (datetime-level dedup) ----

    def merge_intraday(self, df: pd.DataFrame, asset_type: str, market: str, symbol: str, interval: str) -> pd.DataFrame:
        """Merge intraday data, dedup by full datetime (not date-only).

        Args:
            df: New intraday DataFrame with a 'datetime' or 'time' column.
            interval: Bar interval (e.g. '1m', '5m', '15m', '30m', '60m', '1h').
        """
        data_type = f"intraday_{interval}"
        existing = self.load(asset_type, market, symbol, data_type)

        if existing.empty:
            if df is not None and not df.empty:
                self.save(df, asset_type, market, symbol, data_type)
            return df if df is not None else pd.DataFrame()

        combined = pd.concat([existing, df], ignore_index=True)

        # Find datetime column
        time_col = None
        for c in combined.columns:
            if c.lower() in ("datetime", "time", "时间"):
                time_col = c
                break

        if time_col:
            combined[time_col] = pd.to_datetime(combined[time_col])
            combined = combined.drop_duplicates(subset=[time_col], keep="last")
            combined = combined.sort_values(time_col).reset_index(drop=True)

        self.save(combined, asset_type, market, symbol, data_type)
        return combined

    # ---- Date range ----

    def get_date_range(self, asset_type: str, market: str, symbol: str, data_type: str) -> tuple[Optional[date], Optional[date]]:
        """Return (min_date, max_date) of existing data, or (None, None)."""
        df = self.load(asset_type, market, symbol, data_type)
        if df.empty:
            return None, None

        for c in df.columns:
            if c.lower() in ("date", "trade_date", "日期"):
                dates = pd.to_datetime(df[c]).dt.date
                return dates.min(), dates.max()

        return None, None

    def needs_update(self, asset_type: str, market: str, symbol: str, data_type: str) -> bool:
        """Check if data needs updating (last data point is before today)."""
        _, last = self.get_date_range(asset_type, market, symbol, data_type)
        if last is None:
            return True
        # For daily data, check if we have yesterday's data at least
        return last < date.today() - timedelta(days=1)
