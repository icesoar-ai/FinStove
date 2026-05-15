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

GLOBAL_INDEX_NAMES = {
    **US_INDEX_NAMES,
    "HSI": "Hang Seng Index",
    "N225": "Nikkei 225",
    "FTSE": "FTSE 100",
    "DAX": "DAX 40",
    "CAC": "CAC 40",
}

COMMODITY_TICKERS = {
    "GC": "GC=F",
    "SI": "SI=F",
    "CL": "CL=F",
    "BZ": "BZ=F",
    "NG": "NG=F",
    "HG": "HG=F",
    "ZC": "ZC=F",
    "ZS": "ZS=F",
    "PL": "PL=F",
    "PA": "PA=F",
}

COMMODITY_NAMES = {
    "GC": "COMEX Gold",
    "SI": "COMEX Silver",
    "CL": "WTI Crude Oil",
    "BZ": "Brent Crude Oil",
    "NG": "Natural Gas",
    "HG": "COMEX Copper",
    "ZC": "CBOT Corn",
    "ZS": "CBOT Soybean",
    "PL": "NYMEX Platinum",
    "PA": "NYMEX Palladium",
}

FOREX_PAIRS = {
    "USDCNY": "USDCNY=X",
    "EURCNY": "EURCNY=X",
    "JPYCNY": "JPYCNY=X",
    "EURUSD": "EURUSD=X",
    "USDJPY": "USDJPY=X",
    "GBPUSD": "GBPUSD=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "GBPCNY": "GBPCNY=X",
}

FOREX_NAMES = {
    "USDCNY": "USD/CNY",
    "EURCNY": "EUR/CNY",
    "JPYCNY": "JPY/CNY",
    "EURUSD": "EUR/USD",
    "USDJPY": "USD/JPY",
    "GBPUSD": "GBP/USD",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "GBPCNY": "GBP/CNY",
}

CRYPTO_TICKERS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "BNB": "BNB-USD",
    "XRP": "XRP-USD",
    "DOGE": "DOGE-USD",
    "ADA": "ADA-USD",
    "LINK": "LINK-USD",
    "DOT": "DOT-USD",
}

CRYPTO_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "BNB": "BNB",
    "XRP": "XRP",
    "DOGE": "Dogecoin",
    "ADA": "Cardano",
    "LINK": "Chainlink",
    "DOT": "Polkadot",
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
                  end: Optional[str] = None,
                  store_symbol: Optional[str] = None) -> pd.DataFrame:
        """Fetch daily OHLCV. store_symbol overrides the Parquet directory name."""
        if end is None:
            end = date.today().strftime("%Y-%m-%d")

        store_sym = store_symbol or symbol

        existing = self._storage.load("stock", market, store_sym, "daily")
        if not existing.empty:
            _, last_date = self._storage.get_date_range("stock", market, store_sym, "daily")
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

        return self._storage.merge_and_save(df, "stock", market, store_sym, "daily")

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

    def get_dividends(self, symbol: str, market: str = "us") -> pd.DataFrame:
        """Fetch historical dividends as a DataFrame."""
        yf_symbol = self._build_symbol(symbol, market, "stock")
        ticker = self._yf.Ticker(yf_symbol)
        try:
            series = ticker.dividends
            if series is None or series.empty:
                return pd.DataFrame()
            df = series.reset_index()
            df.columns = ["date", "dividend"]
            df["date"] = pd.to_datetime(df["date"]).dt.date
            return df.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame()

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

        existing = self._storage.load("forex", "global", "DXY", "daily")
        if not existing.empty:
            _, last_date = self._storage.get_date_range("forex", "global", "DXY", "daily")
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

        return self._storage.merge_and_save(df, "forex", "global", "DXY", "daily")

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
            df = self._storage.load("forex", "global", "DXY", "daily")
            if not df.empty and "close" in df.columns:
                return float(df.iloc[-1]["close"])
        except Exception:
            pass
        return None

    # ---- Commodity Daily (with Parquet incremental) ----

    def get_commodity_daily(self, symbol: str, start: str = "2010-01-01",
                           end: Optional[str] = None) -> pd.DataFrame:
        """Fetch commodity futures daily OHLCV with Parquet persistence.

        Storage path: data/commodity/global/{symbol}/daily.parquet
        Commodity futures are continuous front-month contracts (e.g. GC=F).
        """
        if end is None:
            end = date.today().strftime("%Y-%m-%d")

        ticker = COMMODITY_TICKERS.get(symbol.upper(), f"{symbol.upper()}=F")

        existing = self._storage.load("commodity", "global", symbol.upper(), "daily")
        if not existing.empty:
            _, last_date = self._storage.get_date_range("commodity", "global", symbol.upper(), "daily")
            if last_date and last_date >= date.today() - timedelta(days=1):
                return existing
            start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            if start >= end:
                return existing

        try:
            df = self.get_generic(ticker, start, end)
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return existing if not existing.empty else pd.DataFrame()

        return self._storage.merge_and_save(df, "commodity", "global", symbol.upper(), "daily")

    # ---- Forex Daily (with Parquet incremental) ----

    def get_forex_daily(self, pair: str, start: str = "2010-01-01",
                        end: Optional[str] = None) -> pd.DataFrame:
        """Fetch forex pair daily OHLCV with Parquet persistence.

        Storage path: data/forex/global/{pair}/daily.parquet
        """
        if end is None:
            end = date.today().strftime("%Y-%m-%d")

        ticker = FOREX_PAIRS.get(pair.upper(), f"{pair.upper()}=X")

        existing = self._storage.load("forex", "global", pair.upper(), "daily")
        if not existing.empty:
            _, last_date = self._storage.get_date_range("forex", "global", pair.upper(), "daily")
            if last_date and last_date >= date.today() - timedelta(days=1):
                return existing
            start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            if start >= end:
                return existing

        try:
            df = self.get_generic(ticker, start, end)
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return existing if not existing.empty else pd.DataFrame()

        return self._storage.merge_and_save(df, "forex", "global", pair.upper(), "daily")

    # ---- Crypto Daily (with Parquet incremental) ----

    def get_crypto_daily(self, symbol: str, start: str = "2015-01-01",
                         end: Optional[str] = None) -> pd.DataFrame:
        """Fetch cryptocurrency daily OHLCV with Parquet persistence.

        Uses Yahoo Finance as data source (faster, no rate limit).
        For market cap data, use CoinGeckoProvider instead.

        Storage path: data/crypto/global/{symbol}/daily.parquet
        """
        if end is None:
            end = date.today().strftime("%Y-%m-%d")

        ticker = CRYPTO_TICKERS.get(symbol.upper(), f"{symbol.upper()}-USD")

        existing = self._storage.load("crypto", "global", symbol.upper(), "daily")
        if not existing.empty:
            _, last_date = self._storage.get_date_range("crypto", "global", symbol.upper(), "daily")
            if last_date and last_date >= date.today() - timedelta(days=1):
                return existing
            start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            if start >= end:
                return existing

        try:
            df = self.get_generic(ticker, start, end)
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return existing if not existing.empty else pd.DataFrame()

        return self._storage.merge_and_save(df, "crypto", "global", symbol.upper(), "daily")

    # ---- Intraday (minute bars) ----

    def get_intraday(self, ticker: str, market: str = "us", interval: str = "5m",
                     period: str = "5d") -> pd.DataFrame:
        """Global minute-level OHLCV via Yahoo Finance.

        Args:
            ticker: Symbol (e.g. 'AAPL', '000001').
            market: Market code ('cn', 'us', 'hk', etc.).
            interval: Bar interval — '1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h'.
            period: Lookback — '1d', '5d', '1mo'. Limited by interval:
                    1m max 7d, 2m-90m max 60d, 1h max 730d.
        """
        sym = self._build_symbol(ticker, market)
        tk = self._yf.Ticker(sym)
        try:
            df = tk.history(interval=interval, period=period)
        except Exception:
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        col_map = {
            "Datetime": "datetime", "Date": "datetime",
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.sort_values("datetime").reset_index(drop=True)

        # Drop timezone info for clean storage
        if "datetime" in df.columns and hasattr(df["datetime"].dtype, "tz"):
            try:
                df["datetime"] = df["datetime"].dt.tz_localize(None)
            except Exception:
                pass

        return df
