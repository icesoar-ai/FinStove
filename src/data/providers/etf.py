"""ETF data provider — A股 (AKShare) + 美股 (yfinance)."""
from __future__ import annotations

from typing import Optional

import pandas as pd


class ETFProvider:
    """ETF data: OHLCV, NAV, holdings, spot."""

    def __init__(self):
        pass

    def get_daily(self, code: str, market: str) -> pd.DataFrame:
        """ETF OHLCV 日线.

        A股: AKShare fund_etf_hist_em.
        美股: yfinance.
        """
        if market == "cn":
            import akshare as ak
            import time
            for attempt in range(3):
                try:
                    df = ak.fund_etf_hist_em(symbol=code)
                    break
                except Exception:
                    if attempt < 2:
                        time.sleep(2 * (attempt + 1))
            else:
                return pd.DataFrame()
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "日期": "date", "开盘": "open",
                    "最高": "high", "最低": "low",
                    "收盘": "close", "成交量": "volume",
                })
        else:
            import yfinance as yf
            tk = yf.Ticker(code)
            df = tk.history(period="max")
            if df is not None and not df.empty:
                df = df.reset_index()
                df["Date"] = pd.to_datetime(df["Date"]).dt.date
                df = df.rename(columns={
                    "Date": "date", "Open": "open", "High": "high",
                    "Low": "low", "Close": "close", "Volume": "volume",
                })
        return df if df is not None else pd.DataFrame()

    def get_nav(self, code: str, market: str) -> pd.DataFrame:
        """ETF 净值历史.

        A股: AKShare fund_etf_fund_info_em.
        美股: 不支持.
        """
        if market == "cn":
            import akshare as ak
            return ak.fund_etf_fund_info_em(fund=code)
        return pd.DataFrame()

    def get_holdings(self, code: str, market: str) -> pd.DataFrame:
        """ETF 持仓.

        A股: AKShare fund_portfolio_hold_em.
        美股: 不支持.
        """
        if market == "cn":
            import akshare as ak
            from datetime import date
            return ak.fund_portfolio_hold_em(symbol=code, date=str(date.today().year))
        return pd.DataFrame()

    def get_spot(self) -> pd.DataFrame:
        """A股 ETF 实时行情 (全市场)."""
        import akshare as ak
        return ak.fund_etf_spot_em()
