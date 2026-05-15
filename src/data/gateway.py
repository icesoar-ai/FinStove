"""统一数据网关 — 封装所有 Provider，CLI 只调 Gateway.

职责：
- 持有所有 Provider 实例
- 统一降级策略（_try 异常捕获）
- 统一读写路径（读优先 Parquet → 写透传 Provider）
- 聚合宏观数据（macro_data.py 逻辑移入）

CLI 命令只调 DataGateway，不感知 Provider 细节。
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

import pandas as pd

from .base import Market
from .cache import DataCache
from .rate_limiter import RateLimiter
from .storage import ParquetStorage

# Providers
from .providers.akshare import AKShareProvider
from .providers.yfinance import YFinanceProvider
from .providers.baostock import BaostockProvider
from .providers.fred import FREDProvider
from .providers.cninfo import CNINFOProvider
from .providers.coingecko import CoinGeckoProvider
from .providers.news import NewsProvider
from .providers.edgar import SECEDGARProvider
from .providers.etf import ETFProvider

from src.utils.ticker import stock_dir, market_dir


class DataGateway:
    """统一数据网关."""

    # Provider → rate limiter key 映射
    _RATE_KEY: dict[str, str] = {
        "_ak": "akshare", "_yf": "yfinance", "_bs": "baostock",
        "_fred": "fred", "_cninfo": "cninfo", "_cg": "coingecko",
        "_news": "news_cn",
    }

    def __init__(self, cache: Optional[DataCache] = None, storage: Optional[ParquetStorage] = None):
        self._cache = cache or DataCache()
        self._storage = storage or ParquetStorage()
        self._rate_limiter = RateLimiter.from_yaml("config/providers.yaml")
        self._ak = AKShareProvider(cache=self._cache, storage=self._storage)
        self._yf = YFinanceProvider(cache=self._cache, storage=self._storage)
        self._bs = BaostockProvider(cache=self._cache, storage=self._storage)
        self._fred = FREDProvider(cache=self._cache, storage=self._storage)
        self._cninfo = CNINFOProvider(storage=self._storage)
        self._edgar = SECEDGARProvider(storage=self._storage)
        self._cg = CoinGeckoProvider(cache=self._cache)
        self._news = NewsProvider(cache=self._cache)
        self._etf = ETFProvider()

    # ── 内部工具 ─────────────────────────────────────────────

    def _try(self, provider_attr: str, fn, *args, **kwargs) -> Optional[pd.DataFrame]:
        """带限速 + 退避重试的 Provider 调用。

        provider_attr: 实例属性名 (如 "_ak", "_yf")，用于查限速配置。
        """
        rkey = self._RATE_KEY.get(provider_attr, "default")
        for attempt in self._rate_limiter.attempts(rkey):
            try:
                result = fn(*args, **kwargs)
                attempt.success()
                return result
            except Exception:
                attempt.failure()
        return None

    def _read_or_fetch(
        self, asset: str, mkt: str, sym: str, dtype: str,
        rkey: str, provider_fn, *args,
        date_col: str = "date",
        ttl: int = 86400,
        **kwargs
    ) -> pd.DataFrame:
        """读路径：Parquet 优先，未命中/过期则调 Provider 并持久化。

        Args:
            asset/mkt/sym/dtype: Parquet 路径参数
            rkey: 限速配置键 (如 "akshare", "yfinance")
            provider_fn: Provider 方法
            *args/**kwargs: Provider 方法参数
            date_col: 日期列名（用于判断新鲜度）
            ttl: API 缓存 TTL（秒）
        """
        existing = self._storage.load(asset, mkt, sym, dtype)
        if not existing.empty:
            # Check freshness
            for col in existing.columns:
                if col.lower() in (date_col.lower(), "date", "trade_date", "日期"):
                    dates = pd.to_datetime(existing[col])
                    if hasattr(dates.iloc[0], "date"):
                        latest = dates.max().date()
                    else:
                        latest = dates.max()
                    if latest >= date.today() - timedelta(days=1):
                        return existing
                    break

        # Fetch fresh
        df = self._try(rkey, provider_fn, *args, **kwargs)
        if df is not None and not df.empty:
            self._cache.set(
                provider_fn.__self__.__class__.__name__,
                provider_fn.__name__, df, *args, ttl=ttl, **kwargs
            )
            self._storage.merge_and_save(df, asset, mkt, sym, dtype)
        return df if df is not None else existing

    def _force_fetch(
        self, asset: str, mkt: str, sym: str, dtype: str,
        rkey: str, provider_fn, *args, **kwargs
    ) -> pd.DataFrame:
        """强制刷新：跳过 Parquet，直接调 Provider 并持久化。"""
        df = self._try(rkey, provider_fn, *args, **kwargs)
        if df is not None and not df.empty:
            self._storage.merge_and_save(df, asset, mkt, sym, dtype)
        return df

    # ── 行情 / 日线 ──────────────────────────────────────

    def get_daily(self, symbol: str, market: Market,
                 start: str = "20200101", end: Optional[str] = None,
                 force: bool = False) -> pd.DataFrame:
        """个股日线 OHLCV。

        A股: AKShare 优先，降级 yfinance。
        美股/港股/其他: 直接 yfinance。
        """
        end = end or date.today().strftime("%Y%m%d")
        # Normalize date formats
        start_fmt = self._normalize_date(start)
        end_fmt = self._normalize_date(end)
        # Unified: all markets → {code}.{suffix} via stock_dir
        dir_name = stock_dir(symbol)

        if market == Market.CN:
            # AKShare uses YYYYMMDD
            if force:
                df = self._try(
                    "_ak", self._ak.get_daily, symbol, start, end,
                    dir_name=dir_name
                )
            else:
                df = self._read_or_fetch(
                    "stock", "cn", dir_name, "daily",
                    "akshare", self._ak.get_daily, symbol, start, end,
                    dir_name=dir_name,
                )
            # Fallback chain: AKShare → yfinance → Baostock
            if df is None or df.empty:
                df = self._try(
                    "_yf", self._yf.get_daily, symbol, "cn", start_fmt, end_fmt,
                    store_symbol=dir_name
                )
            if df is None or df.empty:
                df = self._try(
                    "_bs", self._bs.get_daily, symbol, start, end,
                    store_symbol=dir_name
                )
        else:
            if force:
                df = self._try(
                    "_yf", self._yf.get_daily, symbol, market.value, start_fmt, end_fmt
                )
            else:
                df = self._read_or_fetch(
                    "stock", market.value, dir_name, "daily",
                    "yfinance", self._yf.get_daily, symbol, market.value, start_fmt, end_fmt,
                    store_symbol=dir_name,
                )
        return df if df is not None else pd.DataFrame()

    def get_index(self, market: Market, symbol: Optional[str] = None,
                  force: bool = False) -> pd.DataFrame:
        """指数日线。

        A股: AKShare。
        美股/港股/其他: yfinance。
        """
        if market == Market.CN:
            if symbol:
                return self._fetch_cn_index(symbol, force)
            # All CN indices
            indices = ["000001", "399001", "000300", "000016", "399006", "000688", "000905"]
            results = {}
            for idx in indices:
                df = self._fetch_cn_index(idx, force)
                if df is not None and not df.empty:
                    results[idx] = df
            return results
        else:
            return self._fetch_global_index(market.value, symbol, force)

    def _fetch_cn_index(self, symbol: str, force: bool) -> pd.DataFrame:
        if force:
            df = self._try("_ak", self._ak.get_index_daily, symbol)
        else:
            df = self._read_or_fetch(
                "index", "cn", symbol, "daily",
                "akshare", self._ak.get_index_daily, symbol,
            )
        return df if df is not None else pd.DataFrame()

    def _fetch_global_index(self, market: str, symbol: Optional[str], force: bool) -> pd.DataFrame:
        targets = [
            ("us", "SPX"), ("us", "NDX"), ("us", "DJI"), ("us", "RUT"), ("us", "VIX"),
            ("hk", "HSI"),
            ("jp", "N225"),
            ("uk", "FTSE"),
            ("de", "DAX"),
            ("fr", "CAC"),
        ]
        if symbol:
            for m, s in targets:
                if s == symbol:
                    targets = [(m, s)]
                    break
        results = {}
        for m, s in targets:
            if force:
                df = self._try("_yf", self._yf.get_index, s, m)
            else:
                df = self._read_or_fetch(
                    "index", m, s, "daily",
                    "yfinance", self._yf.get_index, s, m,
                )
            if df is not None and not df.empty:
                results[f"{m}_{s}"] = df
        return results

    def get_intraday(self, symbol: str, market: Market, interval: str = "5") -> pd.DataFrame:
        """盘中分时。

        A股: AKShare 优先，降级 yfinance。
        美股/港股: yfinance。
        """
        if market == Market.CN:
            ak_period = interval.replace("m", "").replace("h", "60")
            df = self._try(
                "_ak", self._ak.get_intraday, symbol, period=ak_period, adjust="qfq"
            )
            if df is None or df.empty:
                df = self._try(
                    "_yf", self._yf.get_intraday, symbol, "cn",
                    interval=interval, period="5d"
                )
        else:
            df = self._try(
                "_yf", self._yf.get_intraday, symbol, market.value,
                interval=interval, period="5d"
            )
        return df if df is not None else pd.DataFrame()

    def get_spot(self, symbol: Optional[str], market: Market) -> pd.DataFrame:
        """实时快照。

        A股个股: AKShare (stock_zh_a_spot_em)。
        A股涨跌榜/全局: AKShare。
        美股/港股/其他: YFinance (概览)。
        """
        if market == Market.CN:
            if symbol:
                return self._ak.get_a_share_spot()
            return self._ak.get_index_spot()
        else:
            return self._yf.get_index_spot()

    # ── 财务 / 年报 ───────────────────────────────────

    def get_financials(self, symbol: str, market: Market = Market.CN) -> dict[str, pd.DataFrame]:
        """三张表。

        A股: AKShare（同花顺）。
        港股: AKShare（东方财富 港股）。
        美股: yfinance。
        """
        if market == Market.CN:
            dir_name = stock_dir(symbol)
            return self._ak.get_financials(symbol, dir_name=dir_name)
        if market == Market.HK:
            result = self._ak.get_hk_financials(symbol)
            if result:
                return result
        result = self._try("_yf", self._yf.get_financials, symbol, market.value)
        return result if result is not None else {}

    def get_dividends(self, symbol: str, market: Market = Market.CN) -> pd.DataFrame:
        """历史分红。

        A股: AKShare。
        港股: AKShare 优先，降级 yfinance。
        美股: yfinance。
        """
        if market == Market.CN:
            dir_name = stock_dir(symbol)
            return self._ak.get_dividends(symbol, dir_name=dir_name)
        if market == Market.HK:
            df = self._ak.get_hk_dividends(symbol)
            if df is not None and not df.empty:
                return df
        result = self._try("_yf", self._yf.get_dividends, symbol, market.value)
        return result if result is not None else pd.DataFrame()

    def get_reports(self, symbol: str, market: Market = Market.CN,
                    since_year: Optional[int] = None,
                    report_types: Optional[list[str]] = None) -> list[dict]:
        """年报/半年报/季报下载。

        A股: CNINFO (PDF+MD)，通过 RateLimiter 限速 + 退避重试。
        美股: SEC EDGAR (10-K/10-Q 文本)。
        """
        if market == Market.CN:
            rkey = "cninfo"
            last_err = None
            for attempt in self._rate_limiter.attempts(rkey):
                try:
                    result = self._cninfo.download_reports(
                        symbol, since_year=since_year, report_types=report_types
                    )
                    attempt.success()
                    return result
                except Exception as e:
                    last_err = e
                    attempt.failure()
            logger.warning("CNINFO download_reports 全部重试失败: %s", last_err)
            return []
        if market == Market.HK:
            logger.warning("港股年报下载暂不支持 (无披露易 Provider)")
            return []
        # US market: map report_types to SEC form types
        if report_types is None:
            form_types = None  # download_filings defaults to ["10-K", "10-Q"]
        else:
            form_types = [self._edgar.FORM_TYPE_MAP.get(rt, "10-K") for rt in report_types]
        return self._edgar.download_filings(
            symbol, since_year=since_year, form_types=form_types
        )

    # ── ETF ─────────────────────────────────────────

    def get_etf_daily(self, code: str, market: Market) -> pd.DataFrame:
        """ETF 日线 OHLCV."""
        mkt = market.value
        dir_name = market_dir(market, code)
        df = self._etf.get_daily(code, mkt)
        if df is not None and not df.empty:
            self._storage.merge_and_save(df, "etf", mkt, dir_name, "daily")
        return df if df is not None else pd.DataFrame()

    def get_etf_nav(self, code: str, market: Market) -> pd.DataFrame:
        """ETF 净值历史."""
        mkt = market.value
        df = self._etf.get_nav(code, mkt)
        if df is not None and not df.empty:
            dir_name = market_dir(market, code)
            self._storage.merge_and_save(df, "etf", mkt, dir_name, "nav")
        return df if df is not None else pd.DataFrame()

    def get_etf_holdings(self, code: str, market: Market) -> pd.DataFrame:
        """ETF 持仓."""
        mkt = market.value
        df = self._etf.get_holdings(code, mkt)
        if df is not None and not df.empty:
            dir_name = market_dir(market, code)
            self._storage.merge_and_save(df, "etf", mkt, dir_name, "holdings")
        return df if df is not None else pd.DataFrame()

    # ── 宏观 ─────────────────────────────────────────

    def get_macro(self) -> dict:
        """整合 CN (AKShare) + US (FRED) + DXY (YFinance) + VIX (YFinance)。

        等价于 macro_data.py 的聚合逻辑。
        """
        result: dict = {
            "policy_rate": {}, "cpi_yoy": {}, "ppi_yoy": {},
            "gdp_growth": {}, "pmi": {}, "yield_curve": {},
            "shibor": {}, "lpr": {}, "unemployment": {},
        }

        # CN data (AKShare)
        for key, fn in [
            ("cpi_yoy", self._ak.get_cpi),
            ("ppi", self._ak.get_ppi),
            ("pmi", self._ak.get_pmi),
            ("gdp", self._ak.get_gdp_cn),
            ("shibor", self._ak.get_shibor_latest),
            ("lpr", self._ak.get_lpr),
            ("fx_reserves", self._ak.get_fx_reserves),
            ("unemployment", self._ak.get_unemployment_cn),
            ("exports_yoy", self._ak.get_exports_yoy),
            ("imports_yoy", self._ak.get_imports_yoy),
            ("industrial_production", self._ak.get_industrial_production),
            ("retail_sales", self._ak.get_retail_sales),
            ("social_financing", self._ak.get_social_financing),
            ("caixin_pmi", self._ak.get_caixin_pmi),
            ("non_man_pmi", self._ak.get_non_man_pmi),
            ("money_supply", self._ak.get_money_supply),
            ("bond_yield", self._ak.get_bond_yield_cn),
        ]:
            try:
                v = fn()
                if v is None:
                    continue
                if isinstance(v, pd.DataFrame):
                    result[key] = v
                elif isinstance(v, dict):
                    result[key] = v
                elif isinstance(v, (int, float)):
                    result[key] = v
            except Exception:
                pass

        # Extract scalar values from DataFrames
        for key in ["cpi_yoy", "ppi_yoy", "gdp", "fx_reserves", "unemployment",
                    "exports_yoy", "imports_yoy", "industrial_production",
                    "caixin_pmi", "non_man_pmi"]:
            if key in result and isinstance(result[key], pd.DataFrame):
                df = result[key]
                col = "今值"
                if col in df.columns:
                    vals = [float(x) for x in reversed(df[col].tolist()) if pd.notna(x) and x != 0]
                    if vals:
                        result[key] = vals[0]

        # SHIBOR
        if "shibor" in result and isinstance(result["shibor"], pd.DataFrame):
            result["shibor"] = self._ak.get_shibor_latest()

        # LPR
        if "lpr" in result and isinstance(result["lpr"], pd.DataFrame):
            lpr_dict = {}
            for col, key in [("LPR1Y", "1Y"), ("LPR5Y", "5Y")]:
                if col in result["lpr"].columns:
                    for v in reversed(result["lpr"][col].tolist()):
                        if pd.notna(v):
                            lpr_dict[key] = float(v)
                            break
            result["lpr"] = lpr_dict

        # Social financing
        if "social_financing" in result and isinstance(result["social_financing"], pd.DataFrame):
            col = "社会融资规模增量"
            if col in result["social_financing"].columns:
                for v in reversed(result["social_financing"][col].tolist()):
                    if pd.notna(v):
                        result["social_financing"] = float(v)
                        break

        # Money supply → m2/m1
        if "money_supply" in result and isinstance(result["money_supply"], pd.DataFrame):
            m2_col = "货币和准货币(M2)-同比增长"
            m1_col = "货币(M1)-同比增长"
            for col, key in [(m2_col, "m2_growth"), (m1_col, "m1_growth")]:
                if col in result["money_supply"].columns:
                    for v in reversed(result["money_supply"][col].tolist()):
                        if pd.notna(v):
                            result[key] = float(v)
                            break
            del result["money_supply"]

        # Retail sales growth
        if "retail_sales" in result and isinstance(result["retail_sales"], pd.DataFrame):
            if "同比增长" in result["retail_sales"].columns:
                for v in reversed(result["retail_sales"]["同比增长"].tolist()):
                    if pd.notna(v):
                        result["retail_sales_growth"] = float(v)
                        break
            del result["retail_sales"]

        # PMI → dict
        if "pmi" in result and isinstance(result["pmi"], pd.DataFrame):
            col = "今值"
            if col in result["pmi"].columns:
                vals = [float(x) for x in reversed(result["pmi"][col].tolist()) if pd.notna(x)]
                if vals:
                    result["pmi"] = {"CN": vals[0]}
            else:
                result["pmi"] = {}

        # Bond yield curve
        if "bond_yield" in result and isinstance(result["bond_yield"], pd.DataFrame):
            if not result["bond_yield"].empty:
                row = result["bond_yield"].iloc[-1]
                curve = {}
                for tenor in ["3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"]:
                    if tenor in row.index and pd.notna(row[tenor]):
                        curve[tenor] = float(row[tenor])
                if curve:
                    result.setdefault("yield_curve", {})["CN"] = curve
            del result["bond_yield"]

        # Clean up scalar CN indicators
        for scalar_key, dict_key in [("cpi_yoy", "cpi_yoy"), ("ppi_yoy", "ppi_yoy"),
                                       ("gdp", "gdp_growth"), ("fx_reserves", "fx_reserves"),
                                       ("unemployment", "unemployment")]:
            if scalar_key in result and isinstance(result[scalar_key], (int, float)):
                if scalar_key == "cpi_yoy":
                    result["cpi_yoy"] = {"CN": result.pop("cpi_yoy")}
                elif scalar_key == "ppi_yoy":
                    result["ppi_yoy"] = {"CN": result.pop("ppi_yoy")}
                elif scalar_key == "gdp":
                    result["gdp_growth"] = {"CN": result.pop("gdp")}
                elif scalar_key == "unemployment":
                    result["unemployment"] = {"CN": result.pop("unemployment")}

        # US data (FRED)
        try:
            us_data = self._fred.get_all_macro_data()
            if us_data:
                for key in ["policy_rate", "cpi_yoy", "gdp_growth", "pmi",
                             "yield_curve", "unemployment"]:
                    if key in us_data and us_data[key]:
                        result[key].update(us_data[key] if isinstance(us_data[key], dict) else {"US": us_data[key]})
        except Exception:
            pass

        # DXY (YFinance)
        try:
            dxy = self._yf.get_dxy_current()
            if dxy:
                result["dxy"] = dxy
        except Exception:
            pass

        # VIX (YFinance)
        try:
            vix_df = self._yf.get_index("VIX", "us")
            if vix_df is not None and not vix_df.empty and "close" in vix_df.columns:
                result["vix"] = float(vix_df["close"].iloc[-1])
        except Exception:
            pass

        # Gold / Oil / Forex / Crypto / Global Indices (from Parquet)
        for asset, mkt, sym, key in [
            ("commodity", "global", "GC", "gold"),
            ("commodity", "global", "CL", "oil_wti"),
            ("commodity", "global", "BZ", "oil_brent"),
            ("forex", "global", "DXY", "dxy"),
            ("forex", "global", "USDCNY", None),
            ("forex", "global", "EURUSD", None),
            ("forex", "global", "USDJPY", None),
            ("crypto", "global", "BTC", None),
            ("crypto", "global", "ETH", None),
        ]:
            df = self._storage.load(asset, mkt, sym, "daily")
            if df is not None and not df.empty and "close" in df.columns:
                val = float(df["close"].iloc[-1])
                if key == "dxy":
                    result["dxy"] = val
                elif key:
                    result[key] = val
                elif sym == "USDCNY":
                    result.setdefault("forex", {})["USDCNY"] = val
                elif sym == "EURUSD":
                    result.setdefault("forex", {})["EURUSD"] = val
                elif sym == "USDJPY":
                    result.setdefault("forex", {})["USDJPY"] = val

        return result

    # ── 新闻 / 资金流向 ─────────────────────────────────

    def get_news(self, symbol: str, days: int = 7) -> list:
        """个股新闻，AKShare（东方财富）。"""
        return self._news.get_all_news(symbol, days=days)

    def get_flow(self) -> dict[str, pd.DataFrame]:
        """沪深港通北向/南向，AKShare。"""
        north = self._ak.get_northbound()
        south = self._ak.get_southbound()
        return {"northbound": north, "southbound": south}

    # ── 加密货币 ───────────────────────────────────────

    def get_crypto(self, symbol: str) -> pd.DataFrame:
        """加密货币，YFinance 优先，降级 CoinGecko。"""
        df = self._try("_yf", self._yf.get_crypto_daily, symbol, "usd", "2020-01-01")
        if df is None or df.empty:
            df = self._try("_cg", self._cg.get_historical, symbol, days=365)
        return df if df is not None else pd.DataFrame()

    # ── 工具 ─────────────────────────────────────────

    @staticmethod
    def _normalize_date(d: str) -> str:
        """Normalize date to YYYY-MM-DD format for yfinance."""
        if d and len(d) == 8 and d.isdigit():
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        return d  # Already YYYY-MM-DD or invalid

    @staticmethod
    def _stock_dir(symbol: str) -> str:
        """Get storage directory name for a stock symbol."""
        from ..utils.ticker import stock_dir
        return stock_dir(symbol)
