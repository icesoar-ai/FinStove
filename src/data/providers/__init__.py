"""Data providers for financial data."""

from .akshare import AKShareProvider
from .yfinance import YFinanceProvider
from .cninfo import CNINFOProvider

# Optional providers (may not be installed)
try:
    from .fred import FREDProvider
    __all__ = ["AKShareProvider", "YFinanceProvider", "CNINFOProvider", "FREDProvider"]
except ImportError:
    __all__ = ["AKShareProvider", "YFinanceProvider", "CNINFOProvider"]

try:
    from .coingecko import CoinGeckoProvider
    if "FREDProvider" not in __all__:
        __all__.append("CoinGeckoProvider")
    else:
        __all__.append("CoinGeckoProvider")
except ImportError:
    pass
