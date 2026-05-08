---
name: spot
description: 实时行情查询 — 全球指数/外汇/商品/加密货币/A股/港股/美股
trigger: /spot
---

# /spot

## 用法

```
/spot                   # 全球概览：A股指数、外汇、商品、加密货币
/spot -m cn             # A股涨幅榜+跌幅榜
/spot -m hk             # 港股涨幅榜+跌幅榜
/spot -m us             # 美股涨幅榜+跌幅榜 (延迟15分钟)
/spot 600519            # A股个股实时行情
/spot AAPL              # 美股个股行情
/spot -w config/watchlist.txt  # 查看自选股
/spot -m cn -n 20       # 显示前20名
```

## 数据源

| 品种 | 数据源 | 说明 |
|------|--------|------|
| A股 | AKShare (东方财富) | 全部A股实时行情 |
| 港股 | AKShare (东方财富) | 港股实时行情 |
| 美股 | AKShare (东方财富) | 美股行情 (延迟15分钟) |
| 全球指数 | AKShare (东方财富) | 包含CN/US/HK/JP/UK/DE/FR |
| 外汇 | AKShare (东方财富) | 全部汇率实时行情 |
| 商品期货 | AKShare (东方财富) | 国际期货行情 |
| 加密货币 | CoinGecko | BTC/ETH实时报价 |

## 唤醒后执行

```bash
python -m src.cli.main spot [TICKER] [-m MARKET] [-w WATCHLIST] [-n LIMIT]
```

## 注意事项

- 纯实时查询，不写入 Parquet 存储
- AKShare 的东方财富接口有频率限制，避免短时间内大量调用
- 美股数据延迟约15分钟（东方财富源）
- 加密货币优先使用 CoinGecko（需网络），备选 AKShare
