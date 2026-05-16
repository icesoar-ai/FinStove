# Provider I/O Separation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gateway 统一负责所有 Parquet 读写，Provider 只从外部 API 抓取数据并返回 DataFrame。

**Architecture:** 移除 AKShare / YFinance / Baostock / FRED / CoinGecko 五个 Provider 的 `self._storage` 依赖，所有 `load()` / `save()` / `merge_and_save()` / `get_date_range()` 调用全部移到 Gateway 层。Provider 的 `_cached()` (diskcache API 去重) 保留不动。

**Tech Stack:** Python 3.12+, pandas, pyarrow, AKShare, yfinance, baostock, fredapi, pycoingecko

---

## 变更文件清单

| 文件 | 变更 |
|------|------|
| `src/data/providers/akshare.py` | 移除 storage 依赖，所有方法纯抓取 |
| `src/data/providers/yfinance.py` | 移除 storage 依赖，所有方法纯抓取 |
| `src/data/providers/baostock.py` | 移除 storage 依赖，get_daily 纯抓取 |
| `src/data/providers/fred.py` | 移除 storage 依赖，get_series 纯抓取 |
| `src/data/providers/coingecko.py` | 移除 storage 依赖 |
| `src/data/gateway.py` | 接管全部 I/O，新增缺失的 Gateway 方法，更新构造函数 |
| `src/data/macro_data.py` | 移除，逻辑已完全在 gateway.get_macro() 中 |
| `src/cli/commands/spot.py` | 改为通过 Gateway 调用 |
| `src/cli/commands/forex.py` | 改为通过 Gateway 调用 |
| `src/cli/commands/commodity.py` | 改为通过 Gateway 调用 |
| `src/cli/commands/index_data.py` | 改为通过 Gateway 调用（或移除，Gateway 已有 get_index） |
| `src/cli/commands/intraday.py` | 改为通过 Gateway 调用（Gateway 已有 get_intraday） |
| `src/cli/commands/crypto.py` | 改为通过 Gateway 调用 |
| `src/cli/commands/yield_curve.py` | 改为通过 Gateway 调用 |
| `src/cli/commands/market_scan.py` | 改为通过 Gateway 调用 |

---

### Task 1: Refactor AKShareProvider — 移除 storage I/O

**Files:**
- Modify: `src/data/providers/akshare.py`

- [ ] **Step 1: 移除 `__init__` 中的 storage 参数**

```python
# Before (line 12-14):
def __init__(self, cache: Optional[DataCache] = None, storage: Optional[ParquetStorage] = None):
    self._cache = cache
    self._storage = storage or ParquetStorage()

# After:
def __init__(self, cache: Optional[DataCache] = None):
    self._cache = cache
```

同时移除文件顶部的 `from ..storage import ParquetStorage` import。

- [ ] **Step 2: 重写 `get_daily()` — 纯抓取，不碰 Parquet**

```python
def get_daily(self, symbol: str, start: str = "20100101", end: Optional[str] = None,
              market: str = "cn") -> pd.DataFrame:
    """Fetch daily OHLCV from AKShare. No storage I/O — Gateway handles persistence."""
    if end is None:
        end = date.today().strftime("%Y%m%d")

    new_df = self._cached("get_daily", 86400, self._ak.stock_zh_a_hist, symbol, "daily", start, end, "qfq")
    return new_df if new_df is not None and not new_df.empty else pd.DataFrame()
```

移除 `dir_name` 参数（存储路径由 Gateway 决定），`market` 参数保留但仅作为透传标记。

- [ ] **Step 3: 重写 `get_dividends()` — 移除 `self._storage.save()`**

```python
def get_dividends(self, symbol: str) -> pd.DataFrame:
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
```

移除 `dir_name` 参数。

- [ ] **Step 4: 重写 `get_financials()` — 移除 `self._storage.save()`**

```python
def get_financials(self, symbol: str) -> dict[str, pd.DataFrame]:
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
                if "报告期" in df.columns:
                    df = df.sort_values("报告期").reset_index(drop=True)
                df = normalize_financials(df)
                result[name] = df
        except Exception:
            pass

    if not result:
        try:
            df = self._ak.stock_financial_abstract_ths(symbol)
            if df is not None and not df.empty:
                result["financials_summary"] = df
        except Exception:
            pass
    return result
```

移除 `dir_name` 参数，移除所有 `self._storage.save()` 调用。

- [ ] **Step 5: 重写 `get_index_daily()` — 纯抓取**

```python
def get_index_daily(self, symbol: str, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
    if end is None:
        end = date.today().strftime("%Y%m%d")
    index_map = {
        "000001": "sh000001", "399001": "sz399001", "000300": "sh000300",
        "000016": "sh000016", "399006": "sz399006", "000688": "sh000688", "000905": "sh000905",
    }
    sym = index_map.get(symbol, f"sh{symbol}" if symbol.startswith(("0", "6")) else f"sz{symbol}")
    df = self._cached("get_index", 86400, self._ak.stock_zh_index_daily, sym)
    return df if df is not None and not df.empty else pd.DataFrame()
```

- [ ] **Step 6: 重写 `get_northbound()` / `get_southbound()` — 纯抓取**

```python
def get_northbound(self, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
    if end is None:
        end = date.today().strftime("%Y%m%d")
    df = self._cached("northbound", 86400, self._ak.stock_hsgt_hist_em, "北向资金")
    return df if df is not None and not df.empty else pd.DataFrame()

def get_southbound(self, start: str = "20100101", end: Optional[str] = None) -> pd.DataFrame:
    if end is None:
        end = date.today().strftime("%Y%m%d")
    df = self._cached("southbound", 86400, self._ak.stock_hsgt_hist_em, "南向资金")
    return df if df is not None and not df.empty else pd.DataFrame()
```

删除 `get_northbound_latest()` 和 `get_southbound_latest()` — 这些是便利方法，由 Gateway 或调用方自行从 DataFrame 中提取。

- [ ] **Step 7: 重写所有宏观方法 — 每个方法只做 `_cached` + fetch，返回 DataFrame**

以 `get_cpi()` 为例：

```python
def get_cpi(self) -> pd.DataFrame:
    df = self._cached("cpi", 86400, self._ak.macro_china_cpi_yearly)
    return df if df is not None and not df.empty else pd.DataFrame()
```

所有宏观方法统一此模式（`get_cpi`, `get_pmi`, `get_ppi`, `get_gdp_cn`, `get_money_supply`, `get_lpr`, `get_fx_reserves`, `get_unemployment_cn`, `get_exports_yoy`, `get_imports_yoy`, `get_industrial_production`, `get_retail_sales`, `get_social_financing`, `get_caixin_pmi`, `get_non_man_pmi`）。

`get_money_supply` 和 `get_retail_sales` 保留 `_fix_month_column()` 调用（数据清洗，非 I/O）。

- [ ] **Step 8: 重写 `get_shibor()` — 纯抓取**

```python
def get_shibor(self) -> pd.DataFrame:
    try:
        df = self._cached("shibor_all", 86400, self._ak.macro_china_shibor_all)
        if df is not None and not df.empty:
            rename_map = {}
            for col in df.columns:
                if col.endswith('-定价'):
                    tenor = col.replace('-定价', '').replace('O/N', 'ON')
                    rename_map[col] = tenor
            df = df.rename(columns=rename_map)
            tenors = ['ON', '1W', '2W', '1M', '3M', '6M', '9M', '1Y']
            keep_cols = ['date'] + [t for t in tenors if t in df.columns]
            df = df[keep_cols].copy()
            df = df.rename(columns={'date': '报告日'})
            df = df.sort_values('报告日').reset_index(drop=True)
            return df
    except Exception:
        pass
    return pd.DataFrame()
```

`get_shibor_latest()` 保留 — 它是从 DataFrame 提取最新值的便利方法，不涉及 I/O。

- [ ] **Step 9: 重写 `get_bond_yield_cn()` — 纯抓取**

```python
def get_bond_yield_cn(self) -> pd.DataFrame:
    df = self._cached("bond_yield_cn", 86400, self._ak.bond_china_yield)
    if df is not None and not df.empty:
        if "曲线名称" in df.columns:
            df = df[df["曲线名称"].str.contains("国债", na=False)]
        return df
    return pd.DataFrame()
```

- [ ] **Step 10: Commit**

```bash
git add src/data/providers/akshare.py
git commit -m "refactor: AKShareProvider 移除 Parquet I/O，纯抓取返回 DataFrame"
```

---

### Task 2: Refactor YFinanceProvider — 移除 storage I/O

**Files:**
- Modify: `src/data/providers/yfinance.py`

- [ ] **Step 1: 移除 `__init__` 中的 storage 参数**

```python
# Before (line 125-127):
def __init__(self, cache: Optional[DataCache] = None, storage: Optional[ParquetStorage] = None):
    self._cache = cache
    self._storage = storage or ParquetStorage()

# After:
def __init__(self, cache: Optional[DataCache] = None):
    self._cache = cache
```

移除 `from ..storage import ParquetStorage` import。

- [ ] **Step 2: 重写 `get_daily()` — 纯抓取**

```python
def get_daily(self, symbol: str, market: str = "us", start: str = "2010-01-01",
              end: Optional[str] = None) -> pd.DataFrame:
    if end is None:
        end = date.today().strftime("%Y-%m-%d")
    yf_symbol = self._build_symbol(symbol, market, "stock")
    ticker = self._yf.Ticker(yf_symbol)
    df = ticker.history(start=start, end=end)
    df = self._normalize_df(df)
    return df if df is not None and not df.empty else pd.DataFrame()
```

移除 `store_symbol` 参数。

- [ ] **Step 3: 重写 `get_index_daily()` — 纯抓取**

```python
def get_index_daily(self, symbol: str, market: str = "us", start: str = "2010-01-01",
                    end: Optional[str] = None) -> pd.DataFrame:
    if end is None:
        end = date.today().strftime("%Y-%m-%d")
    yf_symbol = self._build_symbol(symbol, market, "index")
    ticker = self._yf.Ticker(yf_symbol)
    df = ticker.history(start=start, end=end)
    df = self._normalize_df(df)
    return df if df is not None and not df.empty else pd.DataFrame()
```

- [ ] **Step 4: 重写 `get_dxy()` — 纯抓取**

```python
def get_dxy(self, start: str = "2010-01-01", end: Optional[str] = None) -> pd.DataFrame:
    if end is None:
        end = date.today().strftime("%Y-%m-%d")
    try:
        df = self.get_generic("DX-Y.NYB", start, end)
        if df is None or df.empty:
            df = self.get_generic("USDX", start, end)
    except Exception:
        df = pd.DataFrame()
    return df if df is not None and not df.empty else pd.DataFrame()
```

`get_dxy_current()` 保留 — 从 DataFrame 提取最新值，不涉及 I/O。

- [ ] **Step 5: 重写 `get_commodity_daily()` — 纯抓取**

```python
def get_commodity_daily(self, symbol: str, start: str = "2010-01-01",
                       end: Optional[str] = None) -> pd.DataFrame:
    if end is None:
        end = date.today().strftime("%Y-%m-%d")
    ticker = COMMODITY_TICKERS.get(symbol.upper(), f"{symbol.upper()}=F")
    try:
        df = self.get_generic(ticker, start, end)
    except Exception:
        df = pd.DataFrame()
    return df if df is not None and not df.empty else pd.DataFrame()
```

- [ ] **Step 6: 重写 `get_forex_daily()` — 纯抓取**

```python
def get_forex_daily(self, pair: str, start: str = "2010-01-01",
                    end: Optional[str] = None) -> pd.DataFrame:
    if end is None:
        end = date.today().strftime("%Y-%m-%d")
    ticker = FOREX_PAIRS.get(pair.upper(), f"{pair.upper()}=X")
    try:
        df = self.get_generic(ticker, start, end)
    except Exception:
        df = pd.DataFrame()
    return df if df is not None and not df.empty else pd.DataFrame()
```

- [ ] **Step 7: 重写 `get_crypto_daily()` — 纯抓取**

```python
def get_crypto_daily(self, symbol: str, start: str = "2015-01-01",
                     end: Optional[str] = None) -> pd.DataFrame:
    if end is None:
        end = date.today().strftime("%Y-%m-%d")
    ticker = CRYPTO_TICKERS.get(symbol.upper(), f"{symbol.upper()}-USD")
    try:
        df = self.get_generic(ticker, start, end)
    except Exception:
        df = pd.DataFrame()
    return df if df is not None and not df.empty else pd.DataFrame()
```

- [ ] **Step 8: Commit**

```bash
git add src/data/providers/yfinance.py
git commit -m "refactor: YFinanceProvider 移除 Parquet I/O，纯抓取返回 DataFrame"
```

---

### Task 3: Refactor BaostockProvider — 移除 storage I/O

**Files:**
- Modify: `src/data/providers/baostock.py`

- [ ] **Step 1: 移除 `__init__` 中的 storage 参数**

```python
def __init__(self, cache: Optional[DataCache] = None):
    self._cache = cache
```

移除 `from ..storage import ParquetStorage` import。

- [ ] **Step 2: 重写 `get_daily()` — 纯抓取**

```python
def get_daily(self, symbol: str, start: str = "20100101",
              end: Optional[str] = None) -> pd.DataFrame:
    if end is None:
        end = date.today().strftime("%Y-%m-%d")
    start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:8]}" if len(start) == 8 and start.isdigit() else start
    end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:8]}" if len(end) == 8 and end.isdigit() else end

    if not self._ensure_login():
        return pd.DataFrame()

    try:
        prefix = "sz" if symbol.startswith(("0", "3")) else "sh"
        code = f"{prefix}.{symbol}"
        rs = self._bs.query_history_k_data_plus(
            code, "date,open,high,low,close,volume,amount",
            start_date=start_fmt, end_date=end_fmt,
            frequency="d", adjustflag="2"
        )
        if rs.error_code != "0":
            return pd.DataFrame()
        df = rs.get_data()
        if df is None or df.empty:
            return pd.DataFrame()
        df.columns = ["date", "open", "high", "low", "close", "volume", "amount"]
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[df["open"].notna()]
    finally:
        self._bs.logout()

    return df if df is not None and not df.empty else pd.DataFrame()
```

移除 `store_symbol` 参数。

- [ ] **Step 3: Commit**

```bash
git add src/data/providers/baostock.py
git commit -m "refactor: BaostockProvider 移除 Parquet I/O，纯抓取返回 DataFrame"
```

---

### Task 4: Refactor FREDProvider — 移除 storage I/O

**Files:**
- Modify: `src/data/providers/fred.py`

- [ ] **Step 1: 移除 `__init__` 中的 storage 参数**

```python
def __init__(self, api_key: Optional[str] = None, cache: Optional[DataCache] = None):
    self._api_key = api_key or os.environ.get("FRED_API_KEY")
    self._cache = cache
    self._fred = None
```

移除 `from ..storage import ParquetStorage` import。

- [ ] **Step 2: 重写 `get_series()` — 纯抓取**

```python
def get_series(self, series_id: str, start: Optional[str] = None) -> pd.DataFrame:
    self._init_fred()
    def fetch():
        try:
            df = self._fred.get_series(series_id)
            df = df.to_frame("value")
            df.index.name = "date"
            df = df.reset_index()
            return df
        except Exception:
            return pd.DataFrame()
    df = self._cached(series_id, fetch)
    return df if df is not None and not df.empty else pd.DataFrame()
```

移除所有 `storage_key` / `self._storage.load()` / `self._storage.merge_and_save()` 逻辑。方法变为纯 API 抓取 + diskcache 去重。

- [ ] **Step 3: 删除 `_is_fresh()` 方法**

不再需要 — 新鲜度检查由 Gateway 的 `_read_or_fetch()` 统一处理。

- [ ] **Step 4: 简化 `get_all_macro_data()` 等方法**

`get_federal_funds_rate()`, `get_cpi_yoy()`, `get_unemployment_rate()`, `get_yield_curve()`, `get_pmi_manufacturing()`, `get_pmi_services()`, `get_consumer_sentiment()`, `get_gdp_growth()`, `get_gdp_yoy()`, `get_yield_curve_history()` 这些方法调用 `get_series()` 然后提取最新值或计算。签名不变，但不再有 Parquet I/O（通过 `get_series()` 已纯化）。

`get_all_macro_data()` 保持不变 — 它调用上述方法汇总返回 dict。

- [ ] **Step 5: Commit**

```bash
git add src/data/providers/fred.py
git commit -m "refactor: FREDProvider 移除 Parquet I/O，纯抓取返回 DataFrame"
```

---

### Task 5: Refactor CoinGeckoProvider — 移除 storage I/O

**Files:**
- Modify: `src/data/providers/coingecko.py`

- [ ] **Step 1: 移除 `__init__` 中的 storage 参数**

```python
def __init__(self, api_key: Optional[str] = None, cache: Optional[DataCache] = None):
    self._api_key = api_key or os.environ.get("COINGECKO_API_KEY")
    self._cache = cache
    self._cg = None
```

移除 `from ..storage import ParquetStorage` import。

- [ ] **Step 2: 重写 `get_historical_ohlcv()` — 纯抓取**

```python
def get_historical_ohlcv(self, symbol: str, vs_currency: str = "usd") -> pd.DataFrame:
    coin_id = self.get_coin_id(symbol)
    if not coin_id:
        return pd.DataFrame()
    df = self.get_historical(symbol, days=365, currency=vs_currency)
    if df is None or df.empty:
        return pd.DataFrame()
    ohlcv = pd.DataFrame()
    ohlcv["date"] = df["date"]
    ohlcv["close"] = df["price"]
    ohlcv["open"] = df["price"]
    ohlcv["high"] = df["price"] * 1.02
    ohlcv["low"] = df["price"] * 0.98
    ohlcv["volume"] = df["total_volume"]
    ohlcv["market_cap"] = df["market_cap"]
    return ohlcv
```

移除 `self._storage.load()` / `self._storage.merge_and_save()` 调用。Gateway 负责持久化。

- [ ] **Step 3: Commit**

```bash
git add src/data/providers/coingecko.py
git commit -m "refactor: CoinGeckoProvider 移除 Parquet I/O，纯抓取返回 DataFrame"
```

---

### Task 6: Enhance DataGateway — 接管全部 I/O

**Files:**
- Modify: `src/data/gateway.py`

这是核心变更。Gateway 需要：
1. 不传 storage 给 Provider
2. 增强 `_read_or_fetch()` 以计算增量 start_date
3. 新增缺失的公共方法（forex, commodity, crypto daily, spot 系列等）
4. 更新 `get_macro()` 中的宏观数据获取路径
5. 确保所有数据流经过 `_read_or_fetch()` / `_force_fetch()`

- [ ] **Step 6a: 更新 Provider 实例化 — 不传 storage**

```python
# Before (lines 55-63):
self._ak = AKShareProvider(cache=self._cache, storage=self._storage)
self._yf = YFinanceProvider(cache=self._cache, storage=self._storage)
self._bs = BaostockProvider(cache=self._cache, storage=self._storage)
self._fred = FREDProvider(cache=self._cache, storage=self._storage)
self._cg = CoinGeckoProvider(cache=self._cache)

# After:
self._ak = AKShareProvider(cache=self._cache)
self._yf = YFinanceProvider(cache=self._cache)
self._bs = BaostockProvider(cache=self._cache)
self._fred = FREDProvider(cache=self._cache)
self._cg = CoinGeckoProvider(cache=self._cache)
```

- [ ] **Step 6b: 增强 `_read_or_fetch()` — 支持增量 start 计算**

新增参数 `start_date` / `end_date` (keyword args)，如果提供了，方法会：
1. 从现有 Parquet 数据计算 `last_date`
2. 如果数据存在但不新鲜，将 `start_date` 改为 `last_date + 1`
3. 将 `start_date` / `end_date` 作为 keyword args 传给 provider_fn

```python
def _read_or_fetch(
    self, asset: str, mkt: str, sym: str, dtype: str,
    rkey: str, provider_fn, *args,
    date_col: str = "date",
    ttl: int = 86400,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    freshness_days: int = 1,
    **kwargs
) -> pd.DataFrame:
    existing = self._storage.load(asset, mkt, sym, dtype)
    if not existing.empty:
        _, last = self._storage.get_date_range(asset, mkt, sym, dtype)
        if last and last >= date.today() - timedelta(days=freshness_days):
            return existing
        # Compute incremental start date
        if start_date is not None and last is not None:
            next_day = last + timedelta(days=1)
            # Keep the original format by checking its length/pattern
            if start_date and len(start_date) == 8 and start_date.isdigit():
                start_date = next_day.strftime("%Y%m%d")
            else:
                start_date = next_day.strftime("%Y-%m-%d")

    # Build kwargs for provider call
    call_kwargs = dict(kwargs)
    if start_date is not None:
        call_kwargs["start"] = start_date
    if end_date is not None:
        call_kwargs["end"] = end_date

    df = self._try(rkey, provider_fn, *args, **call_kwargs)
    if df is not None and not df.empty:
        self._cache.set(
            provider_fn.__self__.__class__.__name__,
            provider_fn.__name__, df, *args, ttl=ttl, **call_kwargs
        )
        self._storage.merge_and_save(df, asset, mkt, sym, dtype)
    return df if df is not None else existing
```

- [ ] **Step 6c: 更新 `get_daily()` — CN 路径**

AKShare 的 `get_daily` 不再有 `dir_name` 参数，start/end 改为 keyword args：

```python
if market == Market.CN:
    if force:
        df = self._try("_ak", self._ak.get_daily, symbol, start=start, end=end)
    else:
        df = self._read_or_fetch(
            "stock", "cn", dir_name, "daily",
            "akshare", self._ak.get_daily, symbol,
            start_date=start, end_date=end,
        )
    # Fallback chain unchanged...
```

- [ ] **Step 6d: 更新 `get_daily()` — 非 CN 路径**

```python
else:
    if force:
        df = self._try("_yf", self._yf.get_daily, symbol, market.value,
                       start=start_fmt, end=end_fmt)
    else:
        df = self._read_or_fetch(
            "stock", market.value, dir_name, "daily",
            "yfinance", self._yf.get_daily, symbol, market.value,
            start_date=start_fmt, end_date=end_fmt,
        )
```

- [ ] **Step 6e: 更新 `_fetch_cn_index()` / `_fetch_global_index()`**

同样改为 keyword args 传递 start/end。

- [ ] **Step 6f: 更新 `get_financials()` / `get_dividends()` — 加上持久化**

```python
def get_financials(self, symbol: str, market: Market = Market.CN) -> dict[str, pd.DataFrame]:
    if market == Market.CN:
        dir_name = stock_dir(symbol)
        result = self._ak.get_financials(symbol)
        for name, df in result.items():
            self._storage.save(df, "stock", "cn", dir_name, name)
        return result
    # ... rest unchanged
```

```python
def get_dividends(self, symbol: str, market: Market = Market.CN) -> pd.DataFrame:
    if market == Market.CN:
        dir_name = stock_dir(symbol)
        df = self._ak.get_dividends(symbol)
        if df is not None and not df.empty:
            self._storage.save(df, "stock", "cn", dir_name, "dividends")
        return df
    # ... rest unchanged
```

- [ ] **Step 6g: 更新 `get_flow()` — 加上持久化**

```python
def get_flow(self) -> dict[str, pd.DataFrame]:
    north = self._read_or_fetch(
        "flow", "cn", "northbound", "daily",
        "akshare", self._ak.get_northbound,
        start_date="20100101",
    )
    south = self._read_or_fetch(
        "flow", "cn", "southbound", "daily",
        "akshare", self._ak.get_southbound,
        start_date="20100101",
    )
    return {"northbound": north, "southbound": south}
```

- [ ] **Step 6h: 重写 `get_macro()` — 宏观数据全部走 `_read_or_fetch`**

每个宏观指标使用 `_read_or_fetch` 或直接 `_force_fetch`。关键：
- 对于 `_read_or_fetch` 调用的 `freshness_days` 参数设置为对应频率的合理值（月度=45, 季度=120, 每日=1）
- 后处理逻辑（从 DataFrame 提取标量值）保留不变

```python
def get_macro(self) -> dict:
    result: dict = {
        "policy_rate": {}, "cpi_yoy": {}, "ppi_yoy": {},
        "gdp_growth": {}, "pmi": {}, "yield_curve": {},
        "shibor": {}, "lpr": {}, "unemployment": {},
    }

    # CN macro via _read_or_fetch
    macro_sources = [
        ("cpi_yoy",     self._ak.get_cpi,                   "macro", "cn", "cpi", "monthly", 45),
        ("ppi",         self._ak.get_ppi,                   "macro", "cn", "ppi", "monthly", 45),
        ("pmi",         self._ak.get_pmi,                   "macro", "cn", "pmi", "monthly", 45),
        ("gdp",         self._ak.get_gdp_cn,                "macro", "cn", "gdp", "quarterly", 120),
        ("shibor",      self._ak.get_shibor,                "macro", "cn", "shibor", "daily", 1),
        ("lpr",         self._ak.get_lpr,                   "macro", "cn", "lpr", "monthly", 45),
        ("fx_reserves", self._ak.get_fx_reserves,           "macro", "cn", "fx_reserves", "monthly", 45),
        ("unemployment",self._ak.get_unemployment_cn,       "macro", "cn", "unemployment", "monthly", 45),
        ("exports_yoy", self._ak.get_exports_yoy,           "macro", "cn", "exports_yoy", "monthly", 45),
        ("imports_yoy", self._ak.get_imports_yoy,           "macro", "cn", "imports_yoy", "monthly", 45),
        ("industrial_production", self._ak.get_industrial_production, "macro", "cn", "industrial_production", "monthly", 45),
        ("retail_sales",self._ak.get_retail_sales,          "macro", "cn", "retail_sales", "monthly", 45),
        ("social_financing", self._ak.get_social_financing, "macro", "cn", "social_financing", "monthly", 45),
        ("caixin_pmi",  self._ak.get_caixin_pmi,            "macro", "cn", "caixin_pmi", "monthly", 45),
        ("non_man_pmi", self._ak.get_non_man_pmi,           "macro", "cn", "non_man_pmi", "monthly", 45),
        ("money_supply",self._ak.get_money_supply,          "macro", "cn", "money_supply", "monthly", 45),
        ("bond_yield",  self._ak.get_bond_yield_cn,         "macro", "cn", "bond_yield", "daily", 5),
    ]
    for key, fn, asset, mkt, sym, dtype, freshness in macro_sources:
        try:
            df = self._read_or_fetch(
                asset, mkt, sym, dtype,
                "akshare", fn,
                freshness_days=freshness,
            )
            if df is not None and not df.empty:
                result[key] = df
        except Exception:
            pass

    # Scalar extraction, SHIBOR, LPR, yield curve, FRED, DXY, VIX, etc.
    # ... (保留原有后处理逻辑，不变)
```

- [ ] **Step 6i: 新增 `get_forex_daily()` / `get_commodity_daily()` 方法**

```python
def get_forex_daily(self, pair: str, force: bool = False) -> pd.DataFrame:
    """单个外汇对日线 OHLCV."""
    mkt = "global"
    sym = pair.upper()
    if force:
        df = self._force_fetch("forex", mkt, sym, "daily", "yfinance",
                               self._yf.get_forex_daily, pair)
    else:
        df = self._read_or_fetch(
            "forex", mkt, sym, "daily",
            "yfinance", self._yf.get_forex_daily, pair,
            start_date="2010-01-01",
        )
    return df if df is not None else pd.DataFrame()

def get_commodity_daily(self, symbol: str, force: bool = False) -> pd.DataFrame:
    """单个商品期货日线 OHLCV."""
    mkt = "global"
    sym = symbol.upper()
    if force:
        df = self._force_fetch("commodity", mkt, sym, "daily", "yfinance",
                               self._yf.get_commodity_daily, symbol)
    else:
        df = self._read_or_fetch(
            "commodity", mkt, sym, "daily",
            "yfinance", self._yf.get_commodity_daily, symbol,
            start_date="2010-01-01",
        )
    return df if df is not None else pd.DataFrame()
```

- [ ] **Step 6j: 新增 spot 系列方法（透传，无持久化）**

```python
def get_hk_stock_spot(self) -> pd.DataFrame:
    return self._ak.get_hk_stock_spot()

def get_us_stock_spot(self) -> pd.DataFrame:
    return self._ak.get_us_stock_spot()

def get_forex_spot(self) -> pd.DataFrame:
    return self._ak.get_forex_spot()

def get_futures_spot(self) -> pd.DataFrame:
    return self._ak.get_futures_spot()

def get_crypto_spot(self) -> pd.DataFrame:
    return self._ak.get_crypto_spot()

def get_crypto_market_data(self, symbol: str) -> Optional[dict]:
    return self._cg.get_market_data(symbol)
```

- [ ] **Step 6k: 新增 `get_yield_curve_history()`**

```python
def get_yield_curve_history(self) -> pd.DataFrame:
    return self._fred.get_yield_curve_history()
```

- [ ] **Step 6l: 更新 `get_crypto()` — 加上持久化**

```python
def get_crypto(self, symbol: str) -> pd.DataFrame:
    sym = symbol.upper()
    df = self._read_or_fetch(
        "crypto", "global", sym, "daily",
        "yfinance", self._yf.get_crypto_daily, symbol,
        start_date="2015-01-01",
    )
    if df is None or df.empty:
        df = self._try("_cg", self._cg.get_historical, symbol, days=365)
    return df if df is not None else pd.DataFrame()
```

- [ ] **Step 6m: Commit**

```bash
git add src/data/gateway.py
git commit -m "refactor: Gateway 接管全部 Parquet I/O，Provider 纯抓取"
```

---

### Task 7: 更新 CLI 命令 — 改为通过 Gateway 调用

**Files:**
- Modify: `src/cli/commands/spot.py`, `forex.py`, `commodity.py`, `crypto.py`, `yield_curve.py`, `market_scan.py`
- No change needed: `index_data.py`, `intraday.py` (Gateway 已有对应方法，检查确认)

- [ ] **Step 7a: 更新 `spot.py`**

将直接 import Provider 改为使用 `DataGateway`:

```python
# Before:
from src.data.providers.akshare import AKShareProvider
ak = AKShareProvider()
df = ak.get_a_share_spot()

# After:
from src.data.gateway import DataGateway
gw = DataGateway()
df = gw.get_spot(None, Market.CN)  # 或对应方法
```

具体改动取决于每个 CLI 命令的现有逻辑。原则：所有 `AKShareProvider()` / `YFinanceProvider()` 等直接实例化改为 `DataGateway()`。

- [ ] **Step 7b: 更新 `forex.py`**

```python
# Before: yf = YFinanceProvider(); yf.get_forex_daily(pair)
# After:  gw = DataGateway(); gw.get_forex_daily(pair)
```

- [ ] **Step 7c: 更新 `commodity.py`**

```python
# Before: yf = YFinanceProvider(); yf.get_commodity_daily(symbol)
# After:  gw = DataGateway(); gw.get_commodity_daily(symbol)
```

- [ ] **Step 7d: 更新 `crypto.py`**

```python
# Before: cg = CoinGeckoProvider(); cg.get_market_data(symbol)
# After:  gw = DataGateway(); gw.get_crypto_market_data(symbol)
```

- [ ] **Step 7e: 更新 `yield_curve.py`**

```python
# Before: fred = FREDProvider(); fred.get_yield_curve_history()
# After:  gw = DataGateway(); gw.get_yield_curve_history()
```

- [ ] **Step 7f: 更新 `market_scan.py`**

改为通过 Gateway 的 `get_index()` 获取指数数据。

- [ ] **Step 7g: Commit**

```bash
git add src/cli/commands/
git commit -m "refactor: CLI 命令统一通过 DataGateway 调用，不再直接实例化 Provider"
```

---

### Task 8: 清理 macro_data.py

**Files:**
- Modify: `src/data/macro_data.py`

- [ ] **Step 1: 重写为 Gateway 的薄包装**

```python
"""Macro data convenience functions — thin wrappers over DataGateway."""
from src.data.gateway import DataGateway

def get_all_macro_data() -> dict:
    gw = DataGateway()
    return gw.get_macro()

def get_macro_data_for_analyzer() -> dict:
    return get_all_macro_data()
```

删除 `MacroDataAggregator` 类及其所有方法。

- [ ] **Step 2: 检查谁引用了 `MacroDataAggregator` 或 `get_all_macro_data`**

```bash
grep -r "MacroDataAggregator\|from src.data.macro_data import\|from src.data.macro_data import get_macro_data_for_analyzer" src/ --include="*.py"
```

如果 CLI 或 analysis 模块直接 import，需同步更新。但根据之前的探索，Gateway 的 `get_macro()` 已经包含了所有逻辑，macro_data.py 本身已无外部调用者（Gateway 不 import 它）。

- [ ] **Step 3: Commit**

```bash
git add src/data/macro_data.py
git commit -m "refactor: macro_data 改为 Gateway.get_macro() 薄包装，移除 MacroDataAggregator"
```

---

### Task 9: 验证 — 运行 CLI 命令确认无回归

- [ ] **Step 1: 验证 import 链**

```bash
python -c "from src.data.gateway import DataGateway; gw = DataGateway(); print('OK')"
```

- [ ] **Step 2: 验证关键数据流**

```bash
# 测试 A股日线
python -c "
from src.data.gateway import DataGateway
from src.data.base import Market
gw = DataGateway()
df = gw.get_daily('600519', Market.CN)
print(f'贵州茅台: {len(df)} rows')
"

# 测试美股日线
python -c "
from src.data.gateway import DataGateway
from src.data.base import Market
gw = DataGateway()
df = gw.get_daily('AAPL', Market.US)
print(f'Apple: {len(df)} rows')
"

# 测试宏观数据
python -c "
from src.data.gateway import DataGateway
gw = DataGateway()
macro = gw.get_macro()
print(f'Macro keys: {list(macro.keys())}')
"
```

- [ ] **Step 3: 验证 CLI 命令**

```bash
python -m src.cli.main fetch-stock 600519  # 或其他已有 CLI 命令
```

- [ ] **Step 4: Commit (如有修复)**

---

### Task 10: 更新文档

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/data-flow.md`

- [ ] **Step 1: 更新 architecture.md**

在数据层描述中反映新架构：
- Provider 层：纯外部 API 抓取，不涉及文件 I/O
- Gateway 层：统一读写 Parquet，持有所有 Provider 实例
- Storage 层：ParquetStorage 仅被 Gateway 调用

- [ ] **Step 2: 更新 data-flow.md**

更新数据流图，移除 Provider → Parquet 的直接连线。

- [ ] **Step 3: Commit**

```bash
git add docs/architecture.md docs/data-flow.md
git commit -m "docs: 更新架构文档反映 Provider/Gateway I/O 职责分离"
```

---

## 执行顺序

```
Task 1 (AKShare) ─┐
Task 2 (YFinance) ─┤
Task 3 (Baostock)  ├─ 可并行 ─> Task 6 (Gateway) ─> Task 7 (CLI) ─> Task 8 (macro_data) ─> Task 9 (Verify) ─> Task 10 (Docs)
Task 4 (FRED)     ─┤
Task 5 (CoinGecko)─┘
```
