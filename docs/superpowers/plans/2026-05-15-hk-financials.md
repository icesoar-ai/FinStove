# 港股财报补齐 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** AKShare 新增港股三张表+财务指标+分红，Gateway/CLI 加港股路由

**Architecture:** AKShare Provider 加三个 HK 方法，ticker 工具加 `market_dir` 统一命名（`{code}.{market}`），Gateway `get_financials`/`get_dividends` 加 HK 分支，CLI 适配

**Tech Stack:** Python 3.12+, AKShare, pandas, Click, Rich

---

### Task 1: Ticker 工具 — `market_dir` 统一目录命名

**Files:**
- Modify: `src/utils/ticker.py`

- [ ] **Step 1: 添加 `market_dir` 函数**

```python
def market_dir(market, code: str) -> str:
    """Return storage directory name: {code}.{market}.

    Examples:
        market_dir(Market.HK, "00700") → "00700.HK"
        market_dir(Market.US, "AAPL") → "AAPL.US"
    """
    return f"{code}.{market.value}"
```

- [ ] **Step 2: 验证并提交**

```bash
python -m py_compile src/utils/ticker.py
git add src/utils/ticker.py
git commit -m "feat: ticker 工具新增 market_dir 统一目录命名"
```

---

### Task 2: AKShare Provider — 加港股三张表 + 财务指标 + 分红

**Files:**
- Modify: `src/data/providers/akshare.py`

- [ ] **Step 1: 添加三个 HK 方法**

```python
def get_hk_financials(self, symbol: str) -> dict[str, pd.DataFrame]:
    """港股三张表 — 资产负债表 / 利润表 / 现金流量表."""
    import akshare as ak
    sheets = {
        "balance_sheet": "资产负债表",
        "income":        "利润表",
        "cashflow":      "现金流量表",
    }
    result = {}
    for key, sheet_name in sheets.items():
        try:
            df = ak.stock_financial_hk_report_em(stock=symbol, symbol=sheet_name, indicator="年度")
            if df is not None and not df.empty:
                result[key] = df
        except Exception:
            pass
    return result

def get_hk_indicators(self, symbol: str) -> pd.DataFrame:
    """港股财务指标 — 36 列."""
    import akshare as ak
    return ak.stock_financial_hk_analysis_indicator_em(symbol=symbol)

def get_hk_dividends(self, symbol: str) -> pd.DataFrame:
    """港股分红记录."""
    import akshare as ak
    return ak.stock_hk_dividend_payout_em(symbol=symbol)
```

- [ ] **Step 2: 验证并提交**

```bash
python -m py_compile src/data/providers/akshare.py
git add src/data/providers/akshare.py
git commit -m "feat: AKShare 新增港股三张表 + 财务指标 + 分红方法"
```

---

### Task 3: Gateway — 港股市路由 + 目录命名

**Files:**
- Modify: `src/data/gateway.py`

- [ ] **Step 1: Import `market_dir`**

在文件顶部 ticker 导入行添加：

```python
from src.utils.ticker import stock_dir, market_dir
```

- [ ] **Step 2: `get_financials` 加 HK 分支**

```python
def get_financials(self, symbol: str, market: Market = Market.CN) -> dict[str, pd.DataFrame]:
    if market == Market.CN:
        dir_name = stock_dir(symbol)
        return self._ak.get_financials(symbol, dir_name=dir_name)
    if market == Market.HK:
        result = self._ak.get_hk_financials(symbol)
        if result:
            return result
    result = self._try("_yf", self._yf.get_financials, symbol, market.value)
    return result if result is not None else {}
```

- [ ] **Step 3: `get_dividends` 加 HK 分支**

```python
def get_dividends(self, symbol: str, market: Market = Market.CN) -> pd.DataFrame:
    if market == Market.CN:
        dir_name = stock_dir(symbol)
        return self._ak.get_dividends(symbol, dir_name=dir_name)
    if market == Market.HK:
        df = self._ak.get_hk_dividends(symbol)
        if df is not None and not df.empty:
            return df
    result = self._try("_yf", self._yf.get_dividends, symbol, market.value)
    return result if result is not None else pd.DataFrame()
```

- [ ] **Step 4: `get_daily` HK 使用 `market_dir`**

在 `get_daily` 非 CN 分支中，存储路径使用 `market_dir`：

```python
# In get_daily, else branch (non-CN market):
store_sym = market_dir(market, symbol)
df = self._read_or_fetch(
    "stock", market.value, store_sym, "daily",
    "yfinance", self._yf.get_daily, symbol, market.value, start_fmt, end_fmt,
)
```

- [ ] **Step 5: `get_reports` 加港股提示**

```python
if market == Market.HK:
    logger.warning("港股年报下载暂不支持 (无披露易 Provider)")
    return []
```

- [ ] **Step 6: 验证并提交**

```bash
python -m py_compile src/data/gateway.py
git add src/data/gateway.py
git commit -m "feat: Gateway 加港股市路由 + 目录命名"
```

---

### Task 4: CLI — 港股适配

**Files:**
- Modify: `src/cli/commands/reports.py`
- Modify: `src/cli/commands/financials.py`

- [ ] **Step 1: `reports.py` 港股分支**

```python
if market.value == "hk":
    console.print("[red]港股年报下载暂不支持[/red]")
    return
```

- [ ] **Step 2: `financials.py` 更新 docstring**

```python
def financials(ticker: str, years: str, period: str):
    """A股/美股/港股三大财务报表 — 资产负债表 / 利润表 / 现金流量表 / 主要财务指标."""
```

- [ ] **Step 3: 非 CN 分支使用 `market_dir` 存储**

在 `financials` 的非 A 股分支，保存数据时用 `market_dir` 生成路径。

- [ ] **Step 4: 验证并提交**

```bash
python -m py_compile src/cli/commands/financials.py src/cli/commands/reports.py
git add src/cli/commands/financials.py src/cli/commands/reports.py
git commit -m "feat: CLI 适配港股市场"
```

---

### Task 5: 端到端验证

- [ ] **Step 1: 港股三张表 + 分红**

```bash
python -m src.cli.main fetch financials 0700.HK
```

- [ ] **Step 2: 港股日线 + 新目录命名**

```bash
python -m src.cli.main fetch ohlcv 0700.HK
# 预期: data/stock/hk/00700.HK/daily.parquet
```

- [ ] **Step 3: 港股报告不支持提示**

```bash
python -m src.cli.main fetch reports 0700.HK
# 预期: 港股年报下载暂不支持
```
