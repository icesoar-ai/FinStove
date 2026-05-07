import re

from src.data.base import Market


def detect_market(ticker: str) -> Market:
    ticker = ticker.upper().strip()
    if ".HK" in ticker:
        return Market.HK
    if ".SH" in ticker or ".SZ" in ticker:
        return Market.CN
    if re.match(r"^\d{6}$", ticker):
        if ticker[0] in ("0", "3", "6", "8", "9"):
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
