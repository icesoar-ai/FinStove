import re

from src.data.base import Market


def detect_market(ticker: str) -> Market:
    ticker = ticker.upper().strip()
    if ".HK" in ticker:
        return Market.HK
    if ".SH" in ticker or ".SZ" in ticker:
        return Market.CN
    if re.match(r"^\d{6}$", ticker):
        if ticker[0] in ("0", "1", "3", "5", "6", "8", "9"):
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
