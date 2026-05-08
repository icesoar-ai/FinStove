---
name: fetch-all
description: 一键抓取全部每日数据（全球指数/大宗商品/汇率/加密货币/美债）
trigger: /fetch-all
---

# /fetch-all

## 用法

```
/fetch-all    # 拉取全部每日数据（增量更新）
```

## 唤醒后执行

```bash
python -m src.cli.main index       # 全球指数 (17)
python -m src.cli.main commodity   # 大宗商品 (10)
python -m src.cli.main forex       # 汇率 (9)
python -m src.cli.main crypto      # BTC + ETH
python -m src.cli.main yield-curve # 美债收益率曲线
python -m src.cli.main summary     # 汇总报告
```

## 覆盖范围

| 类别 | 命令 | 品种数 |
|------|------|--------|
| 全球指数 | index | 17 (CN 7 + US 5 + HK/JP/UK/DE/FR 5) |
| 大宗商品 | commodity | 10 (黄金/白银/原油/天然气/铜/玉米/大豆/铂/钯) |
| 外汇 | forex | 9 (USD/EUR/JPY/GBP/AUD/CAD × CNY/USD) |
| 加密货币 | crypto | 2 (BTC + ETH) |
| 美债 | yield-curve | 6 期限 (3M/1Y/2Y/5Y/10Y/30Y) |

全部支持 Parquet 增量更新，已有数据只拉最新交易日。

## 注意事项

- Yahoo Finance 存在速率限制，连续拉取多个品种可能被限流
- FRED 需要环境变量 `FRED_API_KEY`
- 总耗时约 2-5 分钟（取决于 yfinance 速率限制）
