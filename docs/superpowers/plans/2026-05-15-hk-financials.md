# 港股财报补齐 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AKShare 新增港股三张表+财务指标+分红，Gateway/CLI 加港股路由

**Architecture:** AKShare Provider 加三个 HK 方法（`get_hk_financials`/`get_hk_indicators`/`get_hk_dividends`），ticker 工具加港股目录命名，Gateway `get_financials`/`get_dividends` 加 HK 分支，CLI 适配

**Tech Stack:** Python 3.12+, AKShare, pandas, Click, Rich

---

### Task 1: AKShare Provider — 加港股三张表 + 财务指标 + 分红

**Files:**
- Modify: `src/data/providers/akshare.py`

- [ ] **Step 1: 添加 `get_hk_financials` 方法**

在 `AKShareProvider` 类中添加：

```python
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
```

- [ ] **Step 2: 添加 `get_hk_indicators` 方法**

```python
def get_hk_indicators(self, symbol: str) -> pd.DataFrame:
    """港股财务指标 — 36 列 (ROE/ROA/EPS/营收/净利润/资产负债率等).

    Data source: AKShare (东方财富 港股).
    """
    import akshare as ak
    return ak.stock_financial_hk_analysis_indicator_em(symbol=symbol)
```

- [ ] **Step 3: 添加 `get_hk_dividends` 方法**

```python
def get_hk_dividends(self, symbol: str) -> pd.DataFrame:
    """港股分红记录.

    Data source: AKShare (东方财富 港股).
    """
    import akshare as ak
    return ak.stock_hk_dividend_payout_em(symbol=symbol)
```

- [ ] **Step 4: 验证语法并提交**

```bash
python -m py_compile src/data/providers/akshare.py
git add src/data/providers/akshare.py
git commit -m "feat: AKShare 新增港股三张表 + 财务指标 + 分红方法"
```

---

### Task 2: Ticker 工具 — 加港股目录命名

**Files:**
- Modify: `src/utils/ticker.py`

- [ ] **Step 1: 添加 `hk_stock_dir` 函数**

```python
def hk_stock_dir(code: str) -> str:
    """Return HK stock directory name: {code}_HK_{name}, e.g. '00700_HK_腾讯控股'."""
    name = get_hk_stock_name(code)
    if name:
        return f"{code}_HK_{name}"
    return f"{code}_HK"
```

- [ ] **Step 2: 添加 `get_hk_stock_name` 函数**

```python
def get_hk_stock_name(code: str) -> str:
    """Get HK stock short name from AKShare."""
    try:
        import akshare as ak
        info = ak.stock_individual_info_em(symbol=code)
        if info is not None and not info.empty:
            name_row = info[info["item"] == "股票简称"]
            if not name_row.empty:
                return str(name_row["value"].iloc[0])
    except Exception:
        pass
    return ""
```

- [ ] **Step 3: 验证并提交**

```bash
python -m py_compile src/utils/ticker.py
git add src/utils/ticker.py
git commit -m "feat: ticker 工具新增港股目录命名 hk_stock_dir"
```

---

### Task 3: Gateway — 加港股路由

**Files:**
- Modify: `src/data/gateway.py`

- [ ] **Step 1: 修改 `get_financials` 加 HK 分支**

将 `get_financials` 中 A股/其他 的分支扩展为三步：

```python
def get_financials(self, symbol: str, market: Market = Market.CN) -> dict[str, pd.DataFrame]:
    """三张表。

    A股: AKShare（同花顺）。
    美股/港股: yfinance。
    港股: AKShare（东方财富 港股）。
    """
    if market == Market.CN:
        dir_name = self._stock_dir(symbol)
        return self._ak.get_financials(symbol, dir_name=dir_name)
    if market == Market.HK:
        result = self._ak.get_hk_financials(symbol)
        if result:
            return result
        # Fallback to yfinance
    result = self._try("_yf", self._yf.get_financials, symbol, market.value)
    return result if result is not None else {}
```

- [ ] **Step 2: 修改 `get_dividends` 加 HK 分支**

```python
def get_dividends(self, symbol: str, market: Market = Market.CN) -> pd.DataFrame:
    """历史分红。

    A股: AKShare。
    港股: AKShare 优先，降级 yfinance。
    美股: yfinance。
    """
    if market == Market.CN:
        dir_name = self._stock_dir(symbol)
        return self._ak.get_dividends(symbol, dir_name=dir_name)
    if market == Market.HK:
        df = self._ak.get_hk_dividends(symbol)
        if df is not None and not df.empty:
            return df
    result = self._try("_yf", self._yf.get_dividends, symbol, market.value)
    return result if result is not None else pd.DataFrame()
```

- [ ] **Step 3: 修改 `get_reports` 加港股提示**

港股暂无 PDF 年报数据源：

```python
    if market == Market.HK:
        logger.warning("港股年报下载暂不支持 (无披露易 Provider)")
        return []
```

- [ ] **Step 4: 修改 `get_daily` 港股使用 `hk_stock_dir`**

在 Gateway 文件顶部添加 import，在 `get_daily` 的非 CN 分支中，港股使用 `hk_stock_dir`：

```python
from src.utils.ticker import stock_dir, hk_stock_dir
```

然后在 `_read_or_fetch` 调用中，港股使用 `hk_stock_dir(symbol)` 而非 `symbol` 作为目录名。

- [ ] **Step 5: 验证并提交**

```bash
python -m py_compile src/data/gateway.py
git add src/data/gateway.py
git commit -m "feat: Gateway 加港股三张表/分红/日线路由"
```

---

### Task 4: CLI — 港股适配

**Files:**
- Modify: `src/cli/commands/financials.py`
- Modify: `src/cli/commands/reports.py`

- [ ] **Step 1: `financials.py` 支持港股**

非 CN 分支已走 `gw.get_financials(symbol, market)` — 港股自动路由到 Gateway 新分支。只需更新 docstring：

```python
def financials(ticker: str, years: str, period: str):
    """A股/美股/港股三大财务报表 — 资产负债表 / 利润表 / 现金流量表 / 主要财务指标."""
```

- [ ] **Step 2: `reports.py` 港股不支持报告**

在 reports 命令中添加港股分支（与 US 并列）：

```python
    if market.value == "hk":
        console.print("[red]港股年报下载暂不支持[/red]")
        return
```

- [ ] **Step 3: 验证并提交**

```bash
python -m py_compile src/cli/commands/financials.py src/cli/commands/reports.py
git add src/cli/commands/financials.py src/cli/commands/reports.py
git commit -m "feat: CLI financials/reports 适配港股市场"
```

---

### Task 5: 端到端验证

- [ ] **Step 1: 测试港股三张表**

```bash
python -m src.cli.main fetch financials 0700.HK --period all
# 预期: 显示腾讯资产负债表/利润表/现金流量表
```

- [ ] **Step 2: 测试港股日线 + 目录命名**

```bash
python -m src.cli.main fetch ohlcv 0700.HK
# 预期: 存储于 data/stock/hk/00700_HK_腾讯控股/daily.parquet
```

- [ ] **Step 3: 测试港股分红**

```bash
# 通过 financials 命令包含分红显示
python -m src.cli.main fetch financials 0700.HK
# 预期: 显示分红记录
```
