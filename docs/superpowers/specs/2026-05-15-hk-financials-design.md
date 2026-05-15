# 港股财报补齐 — 设计

## 背景

港股仅有日线（yfinance），缺财报/年报/三张表。

## 摸底

| 数据类型 | 来源 | 状态 |
|----------|------|------|
| 三张表（资产负债表/利润表/现金流量表） | AKShare 东方财富 `stock_financial_hk_report_em` | ✅ |
| 财务指标（36项） | AKShare 东方财富 `stock_financial_hk_analysis_indicator_em` | ✅ |
| 分红 | AKShare `stock_hk_dividend_payout_em` / yfinance dividends | ✅ |
| PDF 年报/半年报 | HKEX 披露易 | ❌ 无 API |

## 设计

### 1. AKShare Provider — 加港股分支 (`src/data/providers/akshare.py`)

新增三个方法：
- `get_hk_financials(symbol)` → `dict[str, pd.DataFrame]`，三张表
- `get_hk_financial_indicators(symbol)` → `pd.DataFrame`，36 列
- `get_hk_dividends(symbol)` → `pd.DataFrame`

### 2. 目录命名 (`src/utils/ticker.py`)

`stock_dir` 改为兼容港股：`{code}_HK_{name}`。
- A股保持现状 `{code}_{name}`
- 港股新增 `hk_stock_dir(code)` 返回 `{code}_HK_{name}`

### 3. Gateway — 加港股路由

`get_financials`: `Market.HK` → AKShare HK 分支
`get_dividends`: `Market.HK` → AKShare HK 优先，降级 yfinance

### 4. CLI

`fetch financials <TICKER>` — 已支持 A股/美股，天然兼容港股（市场从 ticker 解析）
`fetch reports <TICKER>` — 港股暂无 PDF 年报数据源，提示不支持

### 5. 不受影响

- 日线：yfinance 已有港股路径
- report_text：港股暂无 PDF→MD，不涉及

## 不做

- PDF 年报下载（HKEX 披露易无 API）
- 半年报单独处理（三张表已含所有期间）
