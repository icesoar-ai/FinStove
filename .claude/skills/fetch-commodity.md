---
name: fetch-commodity
description: 抓取大宗商品期货日线数据（黄金/白银/原油/铜/天然气等）
trigger: /fetch-commodity
---

# /fetch-commodity

## 用法

```
/fetch-commodity              # 拉取全部 10 种商品
/fetch-commodity GC           # 只拉黄金
/fetch-commodity CL           # 只拉 WTI 原油
/fetch-commodity BZ           # 只拉 Brent 原油
```

## 支持的商品

| 代码 | 名称 | 交易所 |
|------|------|--------|
| GC | COMEX Gold | COMEX |
| SI | COMEX Silver | COMEX |
| CL | WTI Crude Oil | NYMEX |
| BZ | Brent Crude Oil | ICE |
| NG | Natural Gas | NYMEX |
| HG | COMEX Copper | COMEX |
| ZC | CBOT Corn | CBOT |
| ZS | CBOT Soybean | CBOT |
| PL | NYMEX Platinum | NYMEX |
| PA | NYMEX Palladium | NYMEX |

## 唤醒后执行

```bash
python -m src.cli.main fetch commodity [SYMBOL]
```

不传 SYMBOL 时拉取全部商品。

## 存储

`data/commodity/global/{SYMBOL}/daily.parquet`

## 注意事项

- 数据源为 Yahoo Finance，均使用连续主力合约（`=F` 后缀）
- 非现货价格，是期货合约价格
- Yahoo Finance 存在速率限制，批量拉取时自动加间隔
