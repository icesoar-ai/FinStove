---
name: fetch-stock
description: 抓取股票数据：日线 + 财报摘要 + 三张表 + 分红 + 年报，可组合
trigger: /fetch-stock
---

# /fetch-stock

## 触发词

以下表述均触发此 skill：

| 用户说 | 执行 |
|--------|------|
| `/fetch-stock <TICKER>` | ohlcv + financials + reports（全取） |
| "更新股票 <TICKER>" / "抓取股票 <TICKER>" | ohlcv + financials（**不含年报**） |
| "更新股票数据 <TICKER>" / "抓取股票数据 <TICKER>" | ohlcv + financials（**不含年报**） |
| "更新年报 <TICKER>" / "抓取年报 <TICKER>" | 仅 reports |
| `/fetch-stock <TICKER> ohlcv` | 仅日线 |
| `/fetch-stock <TICKER> financials` | 仅财报（摘要 + 三张表 + 分红） |
| `/fetch-stock <TICKER> reports` | 仅年报 |
| `/fetch-stock <TICKER> ohlcv,financials` | 日线 + 财报（不含年报） |

**核心规则：用户说"更新/抓取股票/股票数据"时，默认不含年报**（年报体积大、耗时久，需明确提及"年报"才拉取）。

## 数据类型

| 参数 | CLI 命令 | 获取内容 | 存储 |
|------|---------|---------|------|
| `ohlcv` | `python -m src.cli.main fetch ohlcv <TICKER>` | 日线 OHLCV | `data/stock/cn/{dir}/daily.parquet` |
| `financials` | `python -m src.cli.main fetch financials <TICKER>` | 财务摘要 (25项) + 详细三表 (资产负债表/利润表/现金流量表) + 历史分红 | `data/stock/cn/{dir}/financials.parquet` + `income.parquet` + `balance_sheet.parquet` + `cashflow.parquet` + `dividends.parquet` |
| `reports` | `python -m src.cli.main fetch reports <TICKER>` | 年报 PDF + Markdown | `data/stock/cn/{dir}/reports/` |

## 执行

按映射表依次执行对应的 CLI 命令。

## 获取后可继续

- `/valuation <TICKER>` — 估值分析
- `/full-report <TICKER>` — 综合多维分析
- `/analyze-stock <TICKER>` — 技术分析
