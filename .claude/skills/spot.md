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

| 品种 | 概览/加密货币 | 涨跌榜/个股 |
|------|-------------|-----------|
| 全球指数 | **YFinance** | — |
| 外汇 | **YFinance** | — |
| 商品期货 | **YFinance** | — |
| 加密货币 | **YFinance** | — |
| A股 | — | AKShare (东方财富) |
| 港股 | — | AKShare (东方财富) |
| 美股 | — | AKShare + YFinance |

## 唤醒后执行

```bash
python -m src.cli.main live spot [TICKER] [-m MARKET] [-w WATCHLIST] [-n LIMIT]
```

## 注意事项

- 纯实时查询，不写入 Parquet 存储
- 概览全部走 YFinance，不受东方财富限流影响
- 涨跌榜/个股行情走 AKShare（东方财富），有频率限制，避免短时间内大量调用
- 美股个股优先用 YFinance fast_info，备选 AKShare
