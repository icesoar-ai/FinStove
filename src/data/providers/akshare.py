from datetime import date, timedelta
from typing import Optional

import pandas as pd

from ..cache import DataCache
from ..normalizer import standardize, normalize_financials
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
                  market: str = "cn", dir_name: Optional[str] = None) -> pd.DataFrame:
        """Fetch daily OHLCV. dir_name overrides the storage symbol (e.g. '600388_龙净环保')."""
        if end is None:
            end = date.today().strftime("%Y%m%d")

        store_symbol = dir_name or symbol

        existing = self._storage.load("stock", market, store_symbol, "daily")
        if not existing.empty:
            _, last_date = self._storage.get_date_range("stock", market, store_symbol, "daily")
            if last_date:
                start = (last_date + timedelta(days=1)).strftime("%Y%m%d")
                if start >= end:
                    return existing

        new_df = self._cached("get_daily", 86400, self._ak.stock_zh_a_hist, symbol, "daily", start, end, "qfq")

        if new_df is None or new_df.empty:
            return existing if not existing.empty else pd.DataFrame()

        return self._storage.merge_and_save(new_df, "stock", market, store_symbol, "daily")

    # ---- Stock Info ----
    def get_info(self, symbol: str) -> dict:
        try:
            df = self._ak.stock_individual_info_em(symbol=symbol)
            return dict(zip(df["item"], df["value"])) if not df.empty else {}
        except Exception:
            return {}

    # ---- Dividends ----
    def get_dividends(self, symbol: str, dir_name: Optional[str] = None) -> pd.DataFrame:
        """Fetch historical dividend records via AKShare.

        Returns DataFrame with columns: 公告日期，派息，送股，转增，进度，
        除权除息日，股权登记日，红股上市日.
        Only includes "实施" (executed) records.
        """
        store_symbol = dir_name or symbol
        try:
            df = self._ak.stock_history_dividend_detail(symbol=symbol, indicator="分红")
            if df is not None and not df.empty:
                df = df[df["进度"] == "实施"].copy()
                df["公告日期"] = pd.to_datetime(df["公告日期"])
                df = df.sort_values("公告日期").reset_index(drop=True)
                self._storage.save(df, "stock", "cn", store_symbol, "dividends")
                return df
        except Exception:
            pass
        return pd.DataFrame()

    # ---- Financial Statements ----
    def get_financials(self, symbol: str, dir_name: Optional[str] = None) -> dict[str, pd.DataFrame]:
        """Fetch detailed financial statements via AKShare.

        Uses stock_financial_*_ths (同花顺 backend) as primary source,
        since stock_*_by_report_em (东方财富 backend) frequently breaks.
        """
        store_symbol = dir_name or symbol
        result = {}

        sources = [
            ("balance_sheet", self._ak.stock_financial_debt_ths),
            ("income", self._ak.stock_financial_benefit_ths),
            ("cashflow", self._ak.stock_financial_cash_ths),
        ]

        for name, fn in sources:
            try:
                df = fn(symbol)
                if df is not None and not df.empty:
                    # THS returns newest-first; sort ascending for correct iloc[-1]
                    if "报告期" in df.columns:
                        df = df.sort_values("报告期").reset_index(drop=True)
                    # Normalize formatted strings ("88.54 亿", "60.42%") to floats
                    df = normalize_financials(df)
                    self._storage.save(df, "stock", "cn", store_symbol, name)
                    result[name] = df
            except Exception:
                pass

        if not result:
            # Ultimate fallback: financial summary
            try:
                df = self._ak.stock_financial_abstract_ths(symbol)
                if df is not None and not df.empty:
                    self._storage.save(df, "stock", "cn", store_symbol, "income")
                    result["income"] = df
            except Exception:
                pass

        return result

    # ---- Major Indices ----
    def get_index_daily(self, symbol: str, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
        """Fetch daily index OHLCV with Parquet persistence.

        Storage path: data/index/cn/{symbol}/daily.parquet
        """
        if end is None:
            end = date.today().strftime("%Y%m%d")

        index_map = {
            "000001": "sh000001", "399001": "sz399001", "000300": "sh000300",
            "000016": "sh000016", "399006": "sz399006", "000688": "sh000688", "000905": "sh000905",
        }
        sym = index_map.get(symbol, f"sh{symbol}" if symbol.startswith(("0", "6")) else f"sz{symbol}")

        key = ("index", "cn", symbol, "daily")
        existing = self._storage.load(*key)
        if not existing.empty:
            _, last = self._storage.get_date_range(*key)
            if last and last >= date.today() - timedelta(days=1):
                return existing
            start = (last + timedelta(days=1)).strftime("%Y%m%d")
            if start >= end:
                return existing

        df = self._cached("get_index", 86400, self._ak.stock_zh_index_daily_em, sym, start, end)
        if df is not None and not df.empty:
            return self._storage.merge_and_save(df, *key)
        return existing if not existing.empty else pd.DataFrame()

    # ---- Northbound / Southbound Flow ----
    def get_northbound(self, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
        """Fetch northbound net flow (沪深港通北向资金), with Parquet persistence."""
        if end is None:
            end = date.today().strftime("%Y%m%d")

        key = ("flow", "cn", "northbound", "daily")
        existing = self._storage.load(*key)
        if not existing.empty:
            _, last = self._storage.get_date_range(*key)
            if last and last >= date.today() - timedelta(days=1):
                return existing
            start = (last + timedelta(days=1)).strftime("%Y%m%d")
            if start >= end:
                return existing

        df = self._cached("northbound", 86400,
                          self._ak.stock_hsgt_hist_em, "北向资金")
        if df is not None and not df.empty:
            return self._storage.merge_and_save(df, *key)
        return existing if not existing.empty else pd.DataFrame()

    def get_southbound(self, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
        """Fetch southbound net flow (沪深港通南向资金), with Parquet persistence."""
        if end is None:
            end = date.today().strftime("%Y%m%d")

        key = ("flow", "cn", "southbound", "daily")
        existing = self._storage.load(*key)
        if not existing.empty:
            _, last = self._storage.get_date_range(*key)
            if last and last >= date.today() - timedelta(days=1):
                return existing
            start = (last + timedelta(days=1)).strftime("%Y%m%d")
            if start >= end:
                return existing

        df = self._cached("southbound", 86400,
                          self._ak.stock_hsgt_hist_em, "南向资金")
        if df is not None and not df.empty:
            return self._storage.merge_and_save(df, *key)
        return existing if not existing.empty else pd.DataFrame()

    def get_northbound_latest(self) -> Optional[float]:
        """Get most recent northbound net flow value in 亿元."""
        df = self.get_northbound()
        if df.empty:
            return None
        col = "当日成交净买额"
        if col in df.columns:
            val = df.iloc[-1][col]
            if pd.notna(val):
                return float(val)
        return None

    def get_southbound_latest(self) -> Optional[float]:
        """Get most recent southbound net flow value in 亿元."""
        df = self.get_southbound()
        if df.empty:
            return None
        col = "当日成交净买额"
        if col in df.columns:
            val = df.iloc[-1][col]
            if pd.notna(val):
                return float(val)
        return None

    # ---- Macro (with Parquet) ----

    def get_shibor(self) -> pd.DataFrame:
        """Fetch SHIBOR rates for all tenors.

        Uses macro_china_shibor_all which returns all tenors in one call.

        Returns DataFrame with columns: 报告日，ON, 1W, 2W, 1M, 3M, 6M, 9M, 1Y
        """
        key = ("macro", "cn", "shibor", "daily")
        existing = self._storage.load(*key)
        if not existing.empty:
            _, last = self._storage.get_date_range(*key)
            if last and last >= date.today() - timedelta(days=1):
                return existing

        try:
            df = self._cached("shibor_all", 86400, self._ak.macro_china_shibor_all)
            if df is not None and not df.empty:
                # Rename columns to standard format: O/N-定价 -> ON, 1W-定价 -> 1W, etc.
                rename_map = {}
                for col in df.columns:
                    if col.endswith('-定价'):
                        tenor = col.replace('-定价', '').replace('O/N', 'ON')
                        rename_map[col] = tenor

                df = df.rename(columns=rename_map)
                # Keep only date and tenor columns (standardize converts '日期' to 'date')
                tenors = ['ON', '1W', '2W', '1M', '3M', '6M', '9M', '1Y']
                keep_cols = ['date'] + [t for t in tenors if t in df.columns]
                df = df[keep_cols].copy()
                df = df.rename(columns={'date': '报告日'})
                df = df.sort_values('报告日').reset_index(drop=True)
                return self._storage.merge_and_save(df, *key)
        except Exception:
            pass

        return existing if not existing.empty else pd.DataFrame()

    def get_shibor_latest(self) -> dict:
        """Get latest SHIBOR rates as dict {tenor: rate}.

        Convenience method for getting current rates without loading full history.
        """
        df = self.get_shibor()
        if df.empty:
            return {}

        result = {}
        tenors = ["ON", "1W", "2W", "1M", "3M", "6M", "9M", "1Y"]
        for tenor in tenors:
            if tenor in df.columns:
                val = df.iloc[-1][tenor]
                if pd.notna(val):
                    result[tenor] = float(val)
        return result

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

    # ---- Spot / Real-Time Quotes (cached, no Parquet persistence) ----

    def get_a_share_spot(self) -> pd.DataFrame:
        """Real-time A-share quotes (沪深京). TTL=30s."""
        return self._cached("a_share_spot", 30, self._ak.stock_zh_a_spot_em)

    def get_index_spot(self) -> pd.DataFrame:
        """Global index spot prices. TTL=30s."""
        return self._cached("index_spot", 30, self._ak.index_global_spot_em)

    def get_forex_spot(self) -> pd.DataFrame:
        """Forex spot rates (all pairs). TTL=30s."""
        return self._cached("forex_spot", 30, self._ak.forex_spot_em)

    def get_futures_spot(self) -> pd.DataFrame:
        """Global futures spot prices. TTL=30s."""
        return self._cached("futures_spot", 30, self._ak.futures_global_spot_em)

    def get_hk_stock_spot(self) -> pd.DataFrame:
        """HK stock real-time quotes. TTL=30s."""
        return self._cached("hk_spot", 30, self._ak.stock_hk_spot_em)

    def get_us_stock_spot(self) -> pd.DataFrame:
        """US stock real-time quotes (delayed 15min). TTL=30s."""
        return self._cached("us_spot", 30, self._ak.stock_us_spot_em)

    def get_crypto_spot(self) -> pd.DataFrame:
        """Crypto spot quotes from major exchanges. TTL=30s."""
        return self._cached("crypto_spot", 30, self._ak.crypto_js_spot)
