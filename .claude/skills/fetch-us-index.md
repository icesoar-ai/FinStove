---
name: fetch-us-index
description: 抓取美股指数日线数据（S&P 500/Nasdaq/Dow/Russell/VIX）
trigger: /fetch-us-index
---

# /fetch-us-index

## 用法

```
/fetch-us-index             # 拉取全部 5 个指数
/fetch-us-index SPX         # 只拉 S&P 500
/fetch-us-index NDX --start 2025-01-01  # Nasdaq，指定起始日
```

支持指数：

| 代码 | 名称 |
|------|------|
| SPX | S&P 500 |
| NDX | Nasdaq Composite |
| DJI | Dow Jones Industrial |
| RUT | Russell 2000 |
| VIX | CBOE Volatility Index |

## 唤醒后执行

```bash
python -m src.cli.main us-index <CODE>
```

不传 CODE 时拉取全部指数。

## 注意事项

- 数据源为 Yahoo Finance，存在速率限制，连续请求可能被限流
- 存储于 `data/index/us/{code}/daily.parquet`，支持增量更新

## 存储

数据写入 `data/index/us/{code}/daily.parquet`，支持增量更新。
