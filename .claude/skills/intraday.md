---
name: intraday
description: 盘中分钟K线数据 — A股/AKShare优先，限流自动降级yfinance
trigger: /intraday
---

# /intraday

## 用法

```
/intraday <TICKER> -i 5m         # 5分钟K线（默认）
/intraday <TICKER> -i 1m         # 1分钟K线
/intraday <TICKER> -i 15m        # 15分钟K线
/intraday <TICKER> -i 1m --save  # 持久化到 Parquet
```

## 自动切换

| 市场 | 优先源 | 降级源 |
|------|--------|--------|
| A股 | AKShare (东方财富) | YFinance |
| 美股/港股/其他 | YFinance | — |

## 唤醒后执行

```bash
python -m src.cli.main intraday <TICKER> [-i INTERVAL] [-p PERIOD] [--save]
```

## 存储

`data/stock/{market}/{CODE}/intraday_{interval}.parquet`

## 注意事项

- AKShare 东方财富接口有频率限制，限流时自动降级 yfinance
- yfinance 1m 最长 7 天，5m-60m 最长 60 天
- datetimestep 去重（非 date），同一天多根 K 线不会被误删
