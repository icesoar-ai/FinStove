from datetime import date, timedelta
from typing import Optional

import pandas as pd

from ..cache import DataCache
from ..normalizer import standardize
from ..storage import ParquetStorage

SUFFIX_MAP = {
    "cn": {"stock": ".SS", "index": ".SS"},
    "hk": {"stock": ".HK", "index": ".HK"},
    "us": {"stock": "", "index": ""},
    "jp": {"stock": ".T", "index": ".T"},
    "uk": {"stock": ".L", "index": ".L"},
    "de": {"stock": ".DE", "index": ".DE"},
    "fr": {"stock": ".PA", "index": ".PA"},
}

INDEX_TICKERS = {
    "us": {
        "SPX": "^GSPC", "NDX": "^IXIC", "DJI": "^DJI",
        "RUT": "^RUT", "VIX": "^VIX",
    },
    "hk": {"HSI": "^HSI"},
    "jp": {"N225": "^N225"},
    "uk": {"FTSE": "^FTSE"},
    "de": {"DAX": "^GDAXI"},
    "fr": {"CAC": "^FCHI"},
}

US_INDEX_NAMES = {
    "SPX": "S&P 500",
    "NDX": "Nasdaq Composite",
    "DJI": "Dow Jones Industrial",
    "RUT": "Russell 2000",
    "VIX": "CBOE Volatility Index",
}


class YFinanceProvider:
    def __init__(self, cache: Optional[DataCache] = None, storage: Optional[ParquetStorage] = None):
        self._cache = cache
        self._storage = storage or ParquetStorage()
        import yfinance as yf
        self._yf = yf

    def _cached(self, method: str, ttl: int, fn, *args, **kwargs) -> pd.DataFrame:
        if self._cache:
            cached = self._cache.get("yfinance", method, *args, **kwargs)
            if cached is not None:
                return cached
        df = fn(*args, **kwargs)
        if df is None or df.empty:
            return pd.DataFrame()
        df = standardize(df)
        if self._cache:
            self._cache.set("yfinance", method, df, *args, ttl=ttl, **kwargs)
        return df

    def _build_symbol(self, symbol: str, market: str = "us", asset_type: str = "stock") -> str:
        suffix_info = SUFFIX_MAP.get(market, {}).get(asset_type, "")
        if asset_type == "index" and market in INDEX_TICKERS:
            return INDEX_TICKERS[market].get(symbol, f"^{symbol}")
        return symbol + suffix_info

    def _normalize_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is not None and not df.empty:
            df = df.reset_index()
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]
            df = df.rename(columns={"adj_close": "adjusted_close"})
        return standardize(df) if df is not None and not df.empty else pd.DataFrame()

    # ---- Stock OHLCV (with Parquet incremental) ----

    def get_daily(self, symbol: str, market: str = "us", start: str = "2010-01-01",
                  end: Optional[str] = None) -> pd.DataFrame:
        if end is None:
            end = date.today().strftime("%Y-%m-%d")

        existing = self._storage.load("stock", market, symbol, "daily")
        if not existing.empty:
            _, last_date = self._storage.get_date_range("stock", market, symbol, "daily")
            if last_date:
                start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                if start >= end:
                    return existing

        yf_symbol = self._build_symbol(symbol, market, "stock")
        ticker = self._yf.Ticker(yf_symbol)
        df = ticker.history(start=start, end=end)
        df = self._normalize_df(df)

        if df is None or df.empty:
            return existing if not existing.empty else pd.DataFrame()

        return self._storage.merge_and_save(df, "stock", market, symbol, "daily")

    # ---- Info ----

    def get_info(self, symbol: str, market: str = "us") -> dict:
        yf_symbol = self._build_symbol(symbol, market, "stock")
        ticker = self._yf.Ticker(yf_symbol)
        try:
            return ticker.info or {}
        except Exception:
            return {}

    def get_financials(self, symbol: str, market: str = "us") -> dict[str, pd.DataFrame]:
        yf_symbol = self._build_symbol(symbol, market, "stock")
        ticker = self._yf.Ticker(yf_symbol)
        try:
            return {
                "balance_sheet": ticker.balance_sheet,
                "income": ticker.financials,
                "cashflow": ticker.cashflow,
            }
        except Exception:
            return {}

    # ---- Commodity / Forex / Crypto / Index (generic history) ----

    def get_generic(self, ticker: str, start: str = "2010-01-01",
                    end: Optional[str] = None) -> pd.DataFrame:
        if end is None:
            end = date.today().strftime("%Y-%m-%d")
        yf_ticker = self._yf.Ticker(ticker)
        df = yf_ticker.history(start=start, end=end)
        return self._normalize_df(df)

    def get_commodity(self, ticker: str, start: str = "2010-01-01",
                      end: Optional[str] = None) -> pd.DataFrame:
        return self.get_generic(ticker, start, end)

    def get_forex(self, ticker: str, start: str = "2010-01-01",
                  end: Optional[str] = None) -> pd.DataFrame:
        return self.get_generic(ticker, start, end)

    def get_crypto(self, symbol: str = "BTC-USD", start: str = "2010-01-01",
                   end: Optional[str] = None) -> pd.DataFrame:
        return self.get_generic(symbol, start, end)

    def get_index(self, symbol: str, market: str = "us", start: str = "2010-01-01",
                  end: Optional[str] = None) -> pd.DataFrame:
        return self.get_generic(self._build_symbol(symbol, market, "index"), start, end)

    def get_index_daily(self, symbol: str, market: str = "us", start: str = "2010-01-01",
                        end: Optional[str] = None) -> pd.DataFrame:
        """Fetch index daily OHLCV with Parquet persistence.

        Storage path: data/index/{market}/{symbol}/daily.parquet
        """
        if end is None:
            end = date.today().strftime("%Y-%m-%d")

        existing = self._storage.load("index", market, symbol, "daily")
        if not existing.empty:
            _, last_date = self._storage.get_date_range("index", market, symbol, "daily")
            if last_date and last_date >= date.today() - timedelta(days=1):
                return existing
            start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            if start >= end:
                return existing

        yf_symbol = self._build_symbol(symbol, market, "index")
        ticker = self._yf.Ticker(yf_symbol)
        df = ticker.history(start=start, end=end)
        df = self._normalize_df(df)

        if df is None or df.empty:
            return existing if not existing.empty else pd.DataFrame()

        return self._storage.merge_and_save(df, "index", market, symbol, "daily")

    # ---- DXY (US Dollar Index) ----

    def get_dxy(self, start: str = "2010-01-01", end: Optional[str] = None) -> pd.DataFrame:
        """Fetch US Dollar Index (DXY) historical data.

        DXY measures USD against a basket of 6 major currencies.
        Ticker: DX-Y.NYB (ICE Futures U.S.)

        Stores to: data/forex/dxy.parquet
        """
        if end is None:
            end = date.today().strftime("%Y-%m-%d")

        existing = self._storage.load("forex", "global", "dxy", "daily")
        if not existing.empty:
            _, last_date = self._storage.get_date_range("forex", "global", "dxy", "daily")
            if last_date and last_date >= date.today() - timedelta(days=7):
                return existing

        try:
            # DX-Y.NYB is the ICE futures ticker; fallback to USDX if available
            df = self.get_generic("DX-Y.NYB", start, end)
            if df is None or df.empty:
                df = self.get_generic("USDX", start, end)
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return existing if not existing.empty else pd.DataFrame()

        return self._storage.merge_and_save(df, "forex", "global", "dxy", "daily")

    def get_dxy_current(self) -> Optional[float]:
        """Get current DXY level (most recent value)."""
        try:
            df = self.get_dxy()
            if not df.empty and "close" in df.columns:
                return float(df.iloc[-1]["close"])
        except Exception:
            pass
        # Fallback: try to read from existing parquet
        try:
            df = self._storage.load("forex", "global", "dxy", "daily")
            if not df.empty and "close" in df.columns:
                return float(df.iloc[-1]["close"])
        except Exception:
            pass
        return None
