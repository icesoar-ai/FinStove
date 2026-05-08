---
name: fetch-flow
description: 抓取沪深港通资金流向数据（北向/南向资金）
trigger: /fetch-flow
---

# /fetch-flow

## 用法

```
/fetch-flow              # 拉取北向 + 南向资金流向
```

北向资金 = 沪股通 + 深股通 → A 股（外资流入）
南向资金 = 港股通（沪+深）→ 港股（内地资金南下）

## 唤醒后执行

```bash
python -m src.cli.main flow
```

## 存储

数据写入 `data/flow/cn/northbound/daily.parquet` 和 `data/flow/cn/southbound/daily.parquet`，支持增量更新。
