---
name: dividend-yield
description: 股息率曲线分析 — TTM 股息率时间序列、统计摘要与可视化
trigger: /dividend-yield
---

# /dividend-yield <TICKER>

对 A 股个股计算 TTM 股息率时间序列，输出统计摘要、列表和图表。

## 无参数调用

若用户仅输入 `/dividend-yield` 未提供 ticker，询问用户需要分析哪只股票。

## 前置条件

需先拉取数据：`/fetch-stock <TICKER>` 获取日线 + 分红数据。

## 执行

```bash
./bin/fstove dividend-yield <TICKER> --output all
```

## 参数

| 参数 | 说明 |
|------|------|
| `--start YYYY-MM-DD` | 起始日期 |
| `--end YYYY-MM-DD` | 结束日期 |
| `--output summary` | 仅统计摘要 |
| `--output list` | 仅列表 (CSV/JSON) |
| `--output chart` | 仅图表 (SVG/PNG/PDF) |
| `--output all` | 全部 (默认) |
| `--format csv\|json\|svg\|png\|pdf` | 文件格式 |
| `--output-path <DIR>` | 输出目录 (默认: data/stock/cn/<TICKER>/out/) |

文件名格式：`dividend_yield_<YYYYmmdd_HHMMSS>.{ext}`

## 数据要求

| Parquet 文件 | 用途 |
|-------------|------|
| `daily.parquet` | 日线价格 (前复权，内部反推为不复权) |
| `dividends.parquet` | 历史分红记录 (除权日 + 派息 + 送股/转增) |
