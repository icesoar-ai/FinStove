# 港股财报补齐 — 设计

## 目录命名统一

`{code}.{market}` — 等同于 ticker 格式，去除后缀 `.SH` → `600519.SH`。

- 点分隔，和 ticker 格式一致
- 纯代码，不加名（改名不影响路径）
- 现有 CN/US 数据路径暂不动，新市场走新规则

### `market_dir(market, code)` 集中管理

统一入口，上层不感知路径细节。港股及后续市场走 `{code}.{market}`。

## 数据摸底

| 数据类型 | 来源 | 状态 |
|----------|------|------|
| 三张表 | AKShare 东方财富 `stock_financial_hk_report_em` | ✅ |
| 财务指标 | AKShare `stock_financial_hk_analysis_indicator_em` | ✅ |
| 分红 | AKShare `stock_hk_dividend_payout_em` | ✅ |
| 日线 | yfinance | ✅ |
| PDF 年报 | HKEX 披露易 | ❌ 无 API |

## 设计

### 1. 命名工具 (`src/utils/ticker.py`)

新增 `market_dir(market: Market, code: str) -> str`：
- `Market.HK, "00700"` → `"00700.HK"`
- 后续新市场同规则

### 2. AKShare Provider

新增三个 HK 方法：`get_hk_financials`, `get_hk_indicators`, `get_hk_dividends`

### 3. Gateway

- `get_financials` / `get_dividends` → `Market.HK` 走 AKShare HK 分支
- `get_daily` → HK 使用 `market_dir` 生成存储路径
- `get_reports` → HK 暂不支持（无披露易 Provider）

### 4. CLI

`financials` 兼容港股，`reports` 提示不支持。

## 不做

- PDF 年报下载
- 存量数据迁移
