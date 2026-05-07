from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from .base import Market


class Ticker(BaseModel):
    raw: str
    market: Market
    symbol: str
    currency: str = "CNY"

    def __hash__(self) -> int:
        return hash((self.market, self.symbol))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Ticker):
            return False
        return self.market == other.market and self.symbol == other.symbol


class OHLCVRow(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    adjusted_close: Optional[float] = None


class MacroPoint(BaseModel):
    date: date
    indicator: str
    value: float
    country: str
    unit: str = ""


class FlowData(BaseModel):
    date: date
    direction: str
    net_flow: float
    cumulative: float = 0.0


class FinancialReport(BaseModel):
    ticker: str
    period: str
    report_date: date
    currency: str = "CNY"
    balance_sheet: dict = {}
    income_statement: dict = {}
    cash_flow: dict = {}


class NewsItem(BaseModel):
    date: datetime
    title: str
    source: str
    url: str
    summary: str = ""
    sentiment_score: Optional[float] = None
