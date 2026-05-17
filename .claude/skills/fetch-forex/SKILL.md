---
name: fetch-forex
description: 抓取外汇汇率日线数据（USD/CNY, EUR/CNY, JPY/CNY 等）
trigger: /fetch-forex
---

# /fetch-forex

## 用法

```
/fetch-forex                  # 拉取全部 9 个汇率对
/fetch-forex USDCNY           # 只拉美元/人民币
/fetch-forex EURCNY           # 只拉欧元/人民币
/fetch-forex JPYCNY           # 只拉日元/人民币
```

## 支持的汇率对

| 代码 | 名称 |
|------|------|
| USDCNY | 美元/人民币 |
| EURCNY | 欧元/人民币 |
| JPYCNY | 日元/人民币 |
| GBPCNY | 英镑/人民币 |
| EURUSD | 欧元/美元 |
| USDJPY | 美元/日元 |
| GBPUSD | 英镑/美元 |
| AUDUSD | 澳元/美元 |
| USDCAD | 美元/加元 |

## 唤醒后执行

```bash
./bin/fstove fetch forex [PAIR]
```

不传 PAIR 时拉取全部汇率对。

## 存储

`data/forex/global/{PAIR}/daily.parquet`

## 注意事项

- 数据源为 Yahoo Finance
- CNY 相关汇率对历史数据可能较短
