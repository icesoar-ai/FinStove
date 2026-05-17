---
name: market-scan
description: 多市场概览扫描（全球指数/商品/外汇/加密货币的近期表现和趋势）
trigger: /market-scan
---

# /market-scan

## 用法

```
/market-scan [--group A股|美股|港股|亚太|欧洲|商品|外汇|加密货币]
```

默认扫描全部分组，可通过 `--group` 过滤。

## 唤醒后执行

```bash
python -m src.cli.main market-scan
```

## 注意事项

- 读取已拉取的 Parquet 数据，展示 1日/5日/1月/3月/6月 涨跌幅和均线趋势
- 覆盖 A股/美股/港股/亚太/欧洲指数、商品、外汇、加密货币
- 数据需提前通过 `/fetch-all` 拉取
