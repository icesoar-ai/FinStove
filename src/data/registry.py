from __future__ import annotations

from typing import Optional

from .base import Market, AssetType
from .cache import DataCache
from .providers.akshare import AKShareProvider
from .providers.yfinance import YFinanceProvider


class ProviderRegistry:
    def __init__(self, cache: Optional[DataCache] = None):
        self._cache = cache or DataCache()
        self._akshare = AKShareProvider(self._cache)
        self._yfinance = YFinanceProvider(self._cache)
        self._providers: dict[str, object] = {
            "akshare": self._akshare,
            "yfinance": self._yfinance,
        }

    def register(self, name: str, provider: object) -> None:
        self._providers[name] = provider

    def resolve(self, market: Market, asset_type: AssetType) -> object:
        if market == Market.CN:
            return self._providers.get("akshare", self._akshare)
        if asset_type in (AssetType.COMMODITY, AssetType.FOREX, AssetType.CRYPTO):
            return self._providers.get("yfinance", self._yfinance)
        return self._providers.get("yfinance", self._yfinance)

    @property
    def akshare(self) -> AKShareProvider:
        return self._akshare

    @property
    def yfinance(self) -> YFinanceProvider:
        return self._yfinance
