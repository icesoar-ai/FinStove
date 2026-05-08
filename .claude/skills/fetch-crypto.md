---
name: fetch-crypto
description: 抓取加密货币日线 OHLCV 数据（BTC, ETH, SOL 等）
trigger: /fetch-crypto
---

# /fetch-crypto

## 用法

```
/fetch-crypto                 # 拉取 BTC + ETH
/fetch-crypto BTC             # 只拉 Bitcoin
/fetch-crypto ETH             # 只拉 Ethereum
/fetch-crypto SOL             # 只拉 Solana
```

## 支持的币种

| 代码 | 名称 |
|------|------|
| BTC | Bitcoin |
| ETH | Ethereum |
| SOL | Solana |
| BNB | BNB |
| XRP | XRP |
| DOGE | Dogecoin |
| ADA | Cardano |
| LINK | Chainlink |
| DOT | Polkadot |

## 唤醒后执行

```bash
python -m src.cli.main crypto [SYMBOL]
python -m src.cli.main crypto [SYMBOL] --source coingecko   # 如需市值数据
```

不传 SYMBOL 时拉取 BTC + ETH。

## 存储

YFinance: `data/crypto/global/{SYMBOL}/daily.parquet`
CoinGecko: `data/crypto/global/{symbol_lower}_{coingecko_id}/daily.parquet`

## 注意事项

- 默认数据源为 Yahoo Finance（速度快、无限制）
- 使用 `--source coingecko` 可获取市值数据，但 CoinGecko 免费 API 有限制
- YFinance 的加密货币数据从 2015 年开始
