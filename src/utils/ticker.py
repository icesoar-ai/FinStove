import re

from src.data.base import Market


def detect_market(ticker: str) -> Market:
    ticker = ticker.upper().strip()
    if ".HK" in ticker:
        return Market.HK
    if ".SH" in ticker or ".SZ" in ticker:
        return Market.CN
    if re.match(r"^\d{6}$", ticker):
        if ticker[0] in ("0", "3", "5", "6", "8", "9"):
            return Market.CN
    if ".T" in ticker:
        return Market.JP
    if ".L" in ticker:
        return Market.UK
    if ".DE" in ticker:
        return Market.DE
    if ".PA" in ticker:
        return Market.FR
    return Market.US


def parse_ticker(raw: str) -> tuple[str, Market]:
    market = detect_market(raw)
    symbol = raw.split(".")[0].upper() if "." in raw else raw.upper()
    return symbol, market


import json
from pathlib import Path

_NAME_CACHE_FILE = Path.cwd() / "data" / "stock_names.json"


def _load_name_cache() -> dict:
    if _NAME_CACHE_FILE.exists():
        try:
            return json.loads(_NAME_CACHE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_name_cache(cache: dict) -> None:
    _NAME_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _NAME_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


def get_stock_name(symbol: str) -> str:
    """Get stock short name, e.g. '600388' -> '龙净环保'. Cached to disk after first fetch."""
    cache = _load_name_cache()
    if symbol in cache and cache[symbol]:
        return cache[symbol]

    try:
        import akshare as ak
        info = ak.stock_individual_info_em(symbol=symbol)
        d = dict(zip(info["item"], info["value"]))
        name = d.get("股票简称", "")
        if name:
            cache[symbol] = name
            _save_name_cache(cache)
        return name
    except Exception:
        # Try CNINFO profile as fallback
        try:
            import akshare as ak
            profile = ak.stock_profile_cninfo(symbol=symbol)
            if hasattr(profile, 'columns') and 'A股简称' in profile.columns:
                name = str(profile['A股简称'].iloc[0])
                if name:
                    cache[symbol] = name
                    _save_name_cache(cache)
                return name
        except Exception:
            pass
        return ""


def stock_dir(code: str) -> str:
    """Return storage directory name: {code}.{suffix}.

    CN codes: 6xx/8xx/9xx → SH, 0xx/3xx → SZ
    HK codes: ≤5 digit codes → HK
    US/JP/UK etc: alphabetic → US by default

    Examples:
        "601318" → "601318.SH"
        "000002" → "000002.SZ"
        "00700"  → "00700.HK"
        "AAPL"   → "AAPL.US"
    """
    if code.isdigit():
        if len(code) <= 5:
            return f"{code}.HK"
        # CN: 6xx/8xx/9xx/5xx → SH; 0xx/3xx/1xx → SZ
        # 51xxxx = Shanghai ETF; 15xxxx = Shenzhen ETF
        suffix = "SH" if code[0] in ("5", "6", "8", "9") else "SZ"
        return f"{code}.{suffix}"
    return f"{code}.US"


def market_dir(market: Market, code: str) -> str:
    """Return storage directory name: {code}.{market}.

    Deprecated: use stock_dir(code) instead for code-based auto-detection.
    """
    return stock_dir(code)
