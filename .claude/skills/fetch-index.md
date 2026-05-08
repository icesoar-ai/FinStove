---
name: fetch-index
description: 抓取指数日线数据（CN: 上证/深证/沪深300等, US: S&P 500/Nasdaq/Dow等）
trigger: /fetch-index
---

# /fetch-index

## 用法

```
/fetch-index                # 拉取全部 CN + US 指数
/fetch-index cn             # 只拉 CN 指数
/fetch-index us             # 只拉 US 指数
/fetch-index cn 000300      # 只拉 CN 沪深300
/fetch-index us SPX         # 只拉 US S&P 500
```

## CN 指数

| 代码 | 名称 |
|------|------|
| 000001 | 上证指数 |
| 399001 | 深证成指 |
| 000300 | 沪深300 |
| 000016 | 上证50 |
| 399006 | 创业板指 |
| 000688 | 科创50 |
| 000905 | 中证500 |

## US 指数

| 代码 | 名称 |
|------|------|
| SPX | S&P 500 |
| NDX | Nasdaq Composite |
| DJI | Dow Jones Industrial |
| RUT | Russell 2000 |
| VIX | CBOE Volatility Index |

## 唤醒后执行

```bash
# CN
python -m src.cli.main index [CODE]

# US
python -m src.cli.main us-index [CODE]
```

不传 CODE 时拉取全部指数。

## 存储

- CN: `data/index/cn/{code}/daily.parquet`
- US: `data/index/us/{code}/daily.parquet`

均支持增量更新。

## 注意事项

- CN 数据源为 AKShare（东方财富），US 数据源为 Yahoo Finance
- Yahoo Finance 存在速率限制，连续请求可能被限流
