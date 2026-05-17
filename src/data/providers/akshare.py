from datetime import date, timedelta
from typing import Optional

import pandas as pd

from ..cache import DataCache
from ..normalizer import standardize, normalize_financials


class AKShareProvider:
    def __init__(self, cache: Optional[DataCache] = None):
        self._cache = cache
        import akshare as ak
        self._ak = ak

    def _cached(self, method: str, ttl: int, fn, *args, **kwargs) -> pd.DataFrame:
        """Fetch with diskcache as API-call cache (avoid repeated API hits)."""
        if self._cache:
            cached = self._cache.get("akshare", method, *args, **kwargs)
            if cached is not None:
                return cached
        df = fn(*args, **kwargs)
        if df is None or df.empty:
            return pd.DataFrame()
        df = standardize(df)
        if self._cache:
            self._cache.set("akshare", method, df, *args, ttl=ttl, **kwargs)
        return df

    # ---- Stock OHLCV (pure fetch, no Parquet I/O) ----

    def get_daily(self, symbol: str, start: str = "20100101", end: Optional[str] = None,
                  market: str = "cn") -> pd.DataFrame:
        """Fetch daily OHLCV from AKShare. No storage I/O — Gateway handles persistence."""
        if end is None:
            end = date.today().strftime("%Y%m%d")

        new_df = self._cached("get_daily", 86400, self._ak.stock_zh_a_hist, symbol, "daily", start, end, "qfq")
        return new_df if new_df is not None and not new_df.empty else pd.DataFrame()

    # ---- Stock Info ----
    def get_info(self, symbol: str) -> dict:
        try:
            df = self._ak.stock_individual_info_em(symbol=symbol)
            return dict(zip(df["item"], df["value"])) if not df.empty else {}
        except Exception:
            return {}

    # ---- Dividends ----
    def get_dividends(self, symbol: str) -> pd.DataFrame:
        """Fetch historical dividend records via AKShare.

        Returns DataFrame with columns: 公告日期，派息，送股，转增，进度，
        除权除息日，股权登记日，红股上市日.
        Only includes "实施" (executed) records.
        """
        try:
            df = self._ak.stock_history_dividend_detail(symbol=symbol, indicator="分红")
            if df is not None and not df.empty:
                df = df[df["进度"] == "实施"].copy()
                df["公告日期"] = pd.to_datetime(df["公告日期"])
                df = df.sort_values("公告日期").reset_index(drop=True)
                return df
        except Exception:
            pass
        return pd.DataFrame()

    # ---- Financial Statements ----
    def get_financials(self, symbol: str) -> dict[str, pd.DataFrame]:
        """Fetch detailed financial statements via AKShare.

        Uses stock_financial_*_ths (同花顺 backend) as primary source,
        since stock_*_by_report_em (东方财富 backend) frequently breaks.
        """
        result = {}

        sources = [
            ("balance_sheet", self._ak.stock_financial_debt_ths),
            ("income", self._ak.stock_financial_benefit_ths),
            ("cashflow", self._ak.stock_financial_cash_ths),
        ]

        for name, fn in sources:
            try:
                df = fn(symbol)
                if df is not None and not df.empty:
                    # THS returns newest-first; sort ascending for correct iloc[-1]
                    if "报告期" in df.columns:
                        df = df.sort_values("报告期").reset_index(drop=True)
                    # Normalize formatted strings ("88.54 亿", "60.42%") to floats
                    df = normalize_financials(df)
                    result[name] = df
            except Exception:
                pass

        if not result:
            # Ultimate fallback: financial summary
            try:
                df = self._ak.stock_financial_abstract_ths(symbol)
                if df is not None and not df.empty:
                    result["financials_summary"] = df
            except Exception:
                pass

        return result

    # ---- Major Indices ----
    def get_index_daily(self, symbol: str, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
        """Fetch daily index OHLCV. No storage I/O — Gateway handles persistence."""
        if end is None:
            end = date.today().strftime("%Y%m%d")

        index_map = {
            "000001": "sh000001", "399001": "sz399001", "000300": "sh000300",
            "000016": "sh000016", "399006": "sz399006", "000688": "sh000688", "000905": "sh000905",
        }
        sym = index_map.get(symbol, f"sh{symbol}" if symbol.startswith(("0", "6")) else f"sz{symbol}")

        df = self._cached("get_index", 86400, self._ak.stock_zh_index_daily, sym)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            lo = pd.to_datetime(start, format="%Y%m%d")
            hi = pd.to_datetime(end, format="%Y%m%d")
            df = df[df["date"] >= lo]
            df = df[df["date"] <= hi]
        return df if df is not None and not df.empty else pd.DataFrame()

    # ---- Northbound / Southbound Flow ----
    def get_northbound(self, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
        """Fetch northbound net flow (沪深港通北向资金), pure fetch."""
        if end is None:
            end = date.today().strftime("%Y%m%d")
        df = self._cached("northbound", 86400, self._ak.stock_hsgt_hist_em, "北向资金")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        lo = pd.Timestamp(start).date()
        hi = pd.Timestamp(end).date()
        return df[(df["date"] >= lo) & (df["date"] <= hi)]

    def get_southbound(self, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
        """Fetch southbound net flow (沪深港通南向资金), pure fetch."""
        if end is None:
            end = date.today().strftime("%Y%m%d")
        df = self._cached("southbound", 86400, self._ak.stock_hsgt_hist_em, "南向资金")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        lo = pd.Timestamp(start).date()
        hi = pd.Timestamp(end).date()
        return df[(df["date"] >= lo) & (df["date"] <= hi)]

    # ---- Shibor ----

    def get_shibor(self) -> pd.DataFrame:
        """Fetch SHIBOR rates for all tenors.

        Uses macro_china_shibor_all which returns all tenors in one call.

        Returns DataFrame with columns: 报告日，ON, 1W, 2W, 1M, 3M, 6M, 9M, 1Y
        """
        try:
            df = self._cached("shibor_all", 86400, self._ak.macro_china_shibor_all)
            if df is not None and not df.empty:
                # Rename columns to standard format: O/N-定价 -> ON, 1W-定价 -> 1W, etc.
                rename_map = {}
                for col in df.columns:
                    if col.endswith('-定价'):
                        tenor = col.replace('-定价', '').replace('O/N', 'ON')
                        rename_map[col] = tenor

                df = df.rename(columns=rename_map)
                # Keep only date and tenor columns (standardize converts '日期' to 'date')
                tenors = ['ON', '1W', '2W', '1M', '3M', '6M', '9M', '1Y']
                keep_cols = ['date'] + [t for t in tenors if t in df.columns]
                df = df[keep_cols].copy()
                df = df.rename(columns={'date': '报告日'})
                df = df.sort_values('报告日').reset_index(drop=True)
                return df
        except Exception:
            pass
        return pd.DataFrame()

    def get_shibor_latest(self) -> dict:
        """Get latest SHIBOR rates as dict {tenor: rate}.

        Convenience method for getting current rates without loading full history.
        """
        df = self.get_shibor()
        if df.empty:
            return {}

        result = {}
        tenors = ["ON", "1W", "2W", "1M", "3M", "6M", "9M", "1Y"]
        for tenor in tenors:
            if tenor in df.columns:
                val = df.iloc[-1][tenor]
                if pd.notna(val):
                    result[tenor] = float(val)
        return result

    # ---- Macro Indicators (pure fetch, no Parquet I/O) ----

    def get_cpi(self) -> pd.DataFrame:
        df = self._cached("cpi", 86400, self._ak.macro_china_cpi_yearly)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_pmi(self) -> pd.DataFrame:
        df = self._cached("pmi", 86400, self._ak.macro_china_pmi_yearly)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_ppi(self) -> pd.DataFrame:
        df = self._cached("ppi", 86400, self._ak.macro_china_ppi_yearly)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_gdp_cn(self) -> pd.DataFrame:
        df = self._cached("gdp_cn", 86400, self._ak.macro_china_gdp_yearly)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_money_supply(self) -> pd.DataFrame:
        df = self._cached("money_supply", 86400, self._ak.macro_china_money_supply)
        if df is not None and not df.empty:
            df = self._fix_month_column(df)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_lpr(self) -> pd.DataFrame:
        df = self._cached("lpr", 86400, self._ak.macro_china_lpr)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_fx_reserves(self) -> pd.DataFrame:
        df = self._cached("fx_reserves", 86400, self._ak.macro_china_fx_reserves_yearly)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_unemployment_cn(self) -> pd.DataFrame:
        df = self._cached("unemployment_cn", 86400, self._ak.macro_china_urban_unemployment)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_exports_yoy(self) -> pd.DataFrame:
        df = self._cached("exports_yoy", 86400, self._ak.macro_china_exports_yoy)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_imports_yoy(self) -> pd.DataFrame:
        df = self._cached("imports_yoy", 86400, self._ak.macro_china_imports_yoy)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_industrial_production(self) -> pd.DataFrame:
        df = self._cached("industrial_production", 86400,
                          self._ak.macro_china_industrial_production_yoy)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_retail_sales(self) -> pd.DataFrame:
        df = self._cached("retail_sales", 86400, self._ak.macro_china_consumer_goods_retail)
        if df is not None and not df.empty:
            df = self._fix_month_column(df)
        return df if df is not None and not df.empty else pd.DataFrame()

    @staticmethod
    def _fix_month_column(df: pd.DataFrame) -> pd.DataFrame:
        """Rename '月份' to 'date' with proper format parsing and ascending sort."""
        if "月份" in df.columns:
            df = df.copy()
            df["date"] = pd.to_datetime(df["月份"], format="%Y年%m月份")
            df = df.drop(columns=["月份"])
            df = df.sort_values("date").reset_index(drop=True)
        return df

    def get_social_financing(self) -> pd.DataFrame:
        df = self._cached("social_financing", 86400, self._ak.macro_china_shrzgm)
        if df is not None and not df.empty:
            df = self._fix_month_column(df)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_caixin_pmi(self) -> pd.DataFrame:
        df = self._cached("caixin_pmi", 86400, self._ak.macro_china_cx_pmi_yearly)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_non_man_pmi(self) -> pd.DataFrame:
        df = self._cached("non_man_pmi", 86400, self._ak.macro_china_non_man_pmi)
        return df if df is not None and not df.empty else pd.DataFrame()

    def get_bond_yield_cn(self) -> pd.DataFrame:
        """China treasury bond yield curve (国债收益率)."""
        df = self._cached("bond_yield_cn", 86400, self._ak.bond_china_yield)
        if df is not None and not df.empty:
            # Filter to 国债 rows only
            if "曲线名称" in df.columns:
                df = df[df["曲线名称"].str.contains("国债", na=False)]
            return df
        return pd.DataFrame()

    # ---- Spot / Real-Time Quotes (cached, no Parquet persistence) ----

    def get_a_share_spot(self) -> pd.DataFrame:
        """Real-time A-share quotes (沪深京). TTL=30s."""
        return self._cached("a_share_spot", 30, self._ak.stock_zh_a_spot_em)

    def get_index_spot(self) -> pd.DataFrame:
        """Global index spot prices. TTL=30s."""
        return self._cached("index_spot", 30, self._ak.index_global_spot_em)

    def get_forex_spot(self) -> pd.DataFrame:
        """Forex spot rates (all pairs). TTL=30s."""
        return self._cached("forex_spot", 30, self._ak.forex_spot_em)

    def get_futures_spot(self) -> pd.DataFrame:
        """Global futures spot prices. TTL=30s."""
        return self._cached("futures_spot", 30, self._ak.futures_global_spot_em)

    def get_hk_stock_spot(self) -> pd.DataFrame:
        """HK stock real-time quotes. TTL=30s."""
        return self._cached("hk_spot", 30, self._ak.stock_hk_spot_em)

    def get_us_stock_spot(self) -> pd.DataFrame:
        """US stock real-time quotes (delayed 15min). TTL=30s."""
        return self._cached("us_spot", 30, self._ak.stock_us_spot_em)

    def get_crypto_spot(self) -> pd.DataFrame:
        """Crypto spot quotes from major exchanges. TTL=30s."""
        return self._cached("crypto_spot", 30, self._ak.crypto_js_spot)

    # ---- Intraday (minute bars) ----

    def get_intraday(self, symbol: str, period: str = "5", start: str = None,
                     end: str = None, adjust: str = "qfq") -> pd.DataFrame:
        """A-share minute-level OHLCV via Eastmoney.

        Args:
            symbol: 6-digit stock code.
            period: Bar interval in minutes — '1', '5', '15', '30', '60'.
            start: Start datetime string, e.g. '2026-05-08 09:30:00'.
            end: End datetime string.
            adjust: 'qfq' (forward), 'hfq' (backward), '' (none).
        """
        from datetime import datetime, timedelta

        if end is None:
            end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if start is None:
            start = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d 00:00:00")

        # Bypass _cached — standardize() strips time via .dt.date
        try:
            df = self._ak.stock_zh_a_hist_min_em(
                symbol=symbol, period=period,
                start_date=start, end_date=end, adjust=adjust,
            )
        except Exception:
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        # Map Chinese columns to English, preserve full datetime
        col_map = {
            "时间": "datetime", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
            "成交额": "amount", "振幅": "amplitude",
            "涨跌幅": "chg_pct", "涨跌额": "chg_amt", "换手率": "turnover",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.sort_values("datetime").reset_index(drop=True)

        return df

    # ---- HK Stock ----

    def get_hk_financials(self, symbol: str) -> dict[str, pd.DataFrame]:
        """港股三张表 — 资产负债表 / 利润表 / 现金流量表.

        Data source: AKShare (东方财富 港股).
        """
        import akshare as ak

        sheets = {
            "balance_sheet": "资产负债表",
            "income":        "利润表",
            "cashflow":      "现金流量表",
        }
        result = {}
        for key, sheet_name in sheets.items():
            try:
                df = ak.stock_financial_hk_report_em(
                    stock=symbol, symbol=sheet_name, indicator="年度"
                )
                if df is not None and not df.empty:
                    result[key] = df
            except Exception:
                pass
        return result

    def get_hk_indicators(self, symbol: str) -> pd.DataFrame:
        """港股财务指标 — 36 列 (ROE/ROA/EPS/营收/净利润/资产负债率等).

        Data source: AKShare (东方财富 港股).
        """
        import akshare as ak
        return ak.stock_financial_hk_analysis_indicator_em(symbol=symbol)

    def get_hk_dividends(self, symbol: str) -> pd.DataFrame:
        """港股分红记录.

        Data source: AKShare (东方财富 港股).
        """
        import akshare as ak
        return ak.stock_hk_dividend_payout_em(symbol=symbol)
