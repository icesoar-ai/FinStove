---
name: fetch-index
description: 抓取全球股票指数日线数据（CN/US/HK/JP/UK/DE/FR）
trigger: /fetch-index
---

# /fetch-index

## 用法

```
/fetch-index                  # 拉取全部全球指数
/fetch-index cn               # 只拉 CN 指数
/fetch-index us               # 只拉 US 指数
/fetch-index cn 000300        # 只拉 CN 沪深300
/fetch-index us SPX           # 只拉 S&P 500
/fetch-index hk               # 只拉恒生指数
/fetch-index jp               # 只拉日经225
```

## CN 指数 (数据源: AKShare)

| 代码 | 名称 |
|------|------|
| 000001 | 上证指数 |
| 399001 | 深证成指 |
| 000300 | 沪深300 |
| 000016 | 上证50 |
| 399006 | 创业板指 |
| 000688 | 科创50 |
| 000905 | 中证500 |

## 全球指数 (数据源: Yahoo Finance)

| 市场 | 代码 | 名称 |
|------|------|------|
| us | SPX | S&P 500 |
| us | NDX | Nasdaq Composite |
| us | DJI | Dow Jones Industrial |
| us | RUT | Russell 2000 |
| us | VIX | CBOE Volatility Index |
| hk | HSI | Hang Seng Index |
| jp | N225 | Nikkei 225 |
| uk | FTSE | FTSE 100 |
| de | DAX | DAX 40 |
| fr | CAC | CAC 40 |

## 唤醒后执行

```bash
./bin/fstove fetch index [MARKET] [CODE]
```

不传参数拉取全部指数。

## 存储

- CN: `data/index/cn/{code}/daily.parquet` (AKShare)
- 全球: `data/index/{market}/{code}/daily.parquet` (Yahoo Finance)

均支持增量更新。

## 注意事项

- CN 数据源为 AKShare（东方财富），其余市场为 Yahoo Finance
- Yahoo Finance 存在速率限制，批量拉取多市场时可能被限流
