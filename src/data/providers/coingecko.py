"""CoinGecko provider for cryptocurrency data.

Free API tier: 10-50 calls/min, no key required for basic endpoints.
For higher rate limits, register at https://www.coingecko.com/api/pricing
"""
from datetime import date, timedelta
from typing import Optional
import os

import pandas as pd

from ..cache import DataCache
from ..storage import ParquetStorage


# CoinGecko ID 映射 (常用加密货币)
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "USDC": "usd-coin",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "TRX": "tron",
    "LINK": "chainlink",
    "MATIC": "matic-network",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "LTC": "litecoin",
}

# 法币映射
CURRENCY_MAP = {
    "usd": "usd",
    "cny": "cny",
    "eur": "eur",
    "jpy": "jpy",
    "gbp": "gbp",
}


class CoinGeckoProvider:
    """CoinGecko cryptocurrency data provider."""

    def __init__(self, api_key: Optional[str] = None, cache: Optional[DataCache] = None,
                 storage: Optional[ParquetStorage] = None):
        self._api_key = api_key or os.environ.get("COINGECKO_API_KEY")
        self._cache = cache
        self._storage = storage or ParquetStorage()
        self._cg = None

    def _init_cg(self):
        if self._cg is None:
            try:
                from pycoingecko import CoinGeckoAPI
                self._cg = CoinGeckoAPI(api_key=self._api_key)
            except ImportError:
                # Fallback to requests if pycoingecko not installed
                self._cg = "requests"

    def _request(self, url: str, params: Optional[dict] = None) -> dict:
        """Make HTTP request to CoinGecko API."""
        import requests

        base = "https://api.coingecko.com/api/v3"
        if self._api_key:
            base = "https://pro-api.coingecko.com/api/v3"
            headers = {"x-cg-pro-api-key": self._api_key}
        else:
            headers = {}

        try:
            resp = requests.get(f"{base}{url}", params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {}

    def _cached(self, key: str, data: dict, ttl: int = 300):
        """Cache API response."""
        if self._cache and data:
            self._cache.set("coingecko", key, data, ttl=ttl)

    def _get_cached(self, key: str) -> Optional[dict]:
        """Get cached data."""
        if self._cache:
            return self._cache.get("coingecko", key)
        return None

    def get_coin_id(self, symbol: str) -> Optional[str]:
        """Get CoinGecko ID for a symbol."""
        return COINGECKO_IDS.get(symbol.upper())

    def get_price(self, symbol: str, currency: str = "usd") -> Optional[float]:
        """Get current price for a cryptocurrency."""
        coin_id = self.get_coin_id(symbol)
        if not coin_id:
            return None

        cache_key = f"price_{coin_id}_{currency}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached.get("price")

        data = self._request("/simple/price", {"ids": coin_id, "vs_currencies": currency})
        if coin_id in data:
            price = data[coin_id].get(currency)
            self._cached(cache_key, {"price": price}, ttl=60)
            return price
        return None

    def get_market_data(self, symbol: str, currency: str = "usd") -> Optional[dict]:
        """Get comprehensive market data for a cryptocurrency.

        Returns:
            dict with: price, market_cap, volume_24h, change_24h, change_7d,
                       circulating_supply, total_supply, ath, atl
        """
        coin_id = self.get_coin_id(symbol)
        if not coin_id:
            return None

        cache_key = f"market_{coin_id}_{currency}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            data = self._request(f"/coins/{coin_id}", {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
            })

            if not data or "market_data" not in data:
                return None

            md = data["market_data"]
            cur = md.get("current_price", {})
            result = {
                "price": cur.get(currency),
                "market_cap": md.get("market_cap", {}).get(currency),
                "volume_24h": md.get("total_volume", {}).get(currency),
                "change_24h": md.get("price_change_percentage_24h"),
                "change_7d": md.get("price_change_percentage_7d"),
                "change_30d": md.get("price_change_percentage_30d"),
                "circulating_supply": md.get("circulating_supply"),
                "total_supply": md.get("total_supply"),
                "max_supply": md.get("max_supply"),
                "ath": md.get("ath", {}).get(currency),
                "ath_date": md.get("ath_date", {}).get(currency),
                "atl": md.get("atl", {}).get(currency),
                "atl_date": md.get("atl_date", {}).get(currency),
            }
            self._cached(cache_key, result, ttl=300)
            return result
        except Exception:
            return None

    def get_historical(self, symbol: str, days: int = 365,
                       currency: str = "usd") -> pd.DataFrame:
        """Get historical price data.

        Args:
            symbol: Crypto symbol (BTC, ETH, etc.)
            days: Number of days of history (max 365 for free tier)
            currency: Quote currency

        Returns DataFrame with: date, price, market_cap, total_volume
        """
        coin_id = self.get_coin_id(symbol)
        if not coin_id:
            return pd.DataFrame()

        cache_key = f"hist_{coin_id}_{days}_{currency}"
        cached = self._get_cached(cache_key)
        if cached:
            return pd.DataFrame(cached)

        try:
            data = self._request(f"/coins/{coin_id}/market_chart", {
                "vs_currency": currency,
                "days": str(days),
            })

            if not data or "prices" not in data:
                return pd.DataFrame()

            # Parse prices
            prices = data.get("prices", [])
            market_caps = data.get("market_caps", [])
            volumes = data.get("total_volumes", [])

            df = pd.DataFrame(prices, columns=["timestamp", "price"])
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
            df["market_cap"] = [x[1] for x in market_caps] if len(market_caps) == len(prices) else None
            df["total_volume"] = [x[1] for x in volumes] if len(volumes) == len(prices) else None
            df = df[["date", "price", "market_cap", "total_volume"]]

            result = df.to_dict("records")
            self._cached(cache_key, result, ttl=3600)
            return df
        except Exception:
            return pd.DataFrame()

    def get_historical_ohlcv(self, symbol: str, vs_currency: str = "usd") -> pd.DataFrame:
        """Get historical OHLCV data from CoinGecko.

        Note: CoinGecko doesn't provide traditional OHLCV.
        This method fetches daily prices and creates pseudo-OHLCV.
        For real OHLCV, use exchange-specific APIs.
        """
        coin_id = self.get_coin_id(symbol)
        if not coin_id:
            return pd.DataFrame()

        store_symbol = symbol.upper()
        existing = self._storage.load("crypto", "global", store_symbol, "daily")
        if not existing.empty:
            _, last_date = self._storage.get_date_range("crypto", "global", store_symbol, "daily")
            if last_date and last_date >= date.today() - timedelta(days=1):
                return existing

        # Get last 365 days (CoinGecko free tier limit)
        df = self.get_historical(symbol, days=365, currency=vs_currency)

        if df is None or df.empty:
            return existing if not existing.empty else pd.DataFrame()

        # Create pseudo-OHLCV (CoinGecko only gives closing prices)
        ohlcv = pd.DataFrame()
        ohlcv["date"] = df["date"]
        ohlcv["close"] = df["price"]
        ohlcv["open"] = df["price"]  # Same as close (limitation)
        ohlcv["high"] = df["price"] * 1.02  # Estimate
        ohlcv["low"] = df["price"] * 0.98  # Estimate
        ohlcv["volume"] = df["total_volume"]
        ohlcv["market_cap"] = df["market_cap"]

        ohlcv = self._storage.merge_and_save(ohlcv, "crypto", "global", store_symbol, "daily")
        return ohlcv

    def get_top_coins(self, limit: int = 100, currency: str = "usd") -> pd.DataFrame:
        """Get top cryptocurrencies by market cap.

        Returns DataFrame with: rank, id, symbol, name, price, market_cap,
                               volume_24h, change_24h, change_7d
        """
        try:
            data = self._request("/coins/markets", {
                "vs_currency": currency,
                "order": "market_cap_desc",
                "per_page": str(limit),
                "page": "1",
                "sparkline": "false",
            })

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)
            return df
        except Exception:
            return pd.DataFrame()

    def get_global_stats(self) -> Optional[dict]:
        """Get global cryptocurrency market statistics.

        Returns:
            dict with: active_cryptos, active_markets, total_market_cap,
                       total_volume, market_cap_percentage, etc.
        """
        try:
            data = self._request("/global")
            if data and "data" in data:
                return data["data"]
        except Exception:
            pass
        return None
