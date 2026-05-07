---
name: fetch-stock
description: 抓取股票数据：日线行情 + 财务摘要 + 年报(PDF+MD)，可单独或组合获取
trigger: /fetch-stock
---

# /fetch-stock

## 用法

```
/fetch-stock <TICKER>              # 全抓（日线 + 财报 + 年报）
/fetch-stock <TICKER> ohlcv        # 只日线
/fetch-stock <TICKER> financials   # 只财报
/fetch-stock <TICKER> reports      # 只年报
/fetch-stock <TICKER> ohlcv,reports  # 日线 + 年报
```

## 数据类型

| 参数 | CLI 命令 | 获取内容 | 存储 |
|------|---------|---------|------|
| `ohlcv` | `python -m src.cli.main ohlcv <TICKER>` | 日线 OHLCV | `data/stock/cn/{dir}/daily.parquet` |
| `financials` | `python -m src.cli.main financials <TICKER>` | 财务摘要 (25项) + 详细三表 | `data/stock/cn/{dir}/financials.parquet` |
| `reports` | `python -m src.cli.main reports <TICKER>` | 年报 PDF + Markdown | `data/stock/cn/{dir}/reports/` |

无参数时默认获取全部三类数据。

## 获取后可继续

- `/valuation <TICKER>` — 估值分析
- `/full-report <TICKER>` — 综合多维分析
- `/analyze-stock <TICKER>` — 技术分析
