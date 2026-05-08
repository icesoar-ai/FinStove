---
name: macro-check
description: 宏观环境评估（利率/通胀/GDP/PMI/收益率曲线/黄金/原油/汇率/全球指数/加密货币）
trigger: /macro-check
---

# /macro-check

## 用法

```
/macro-check [--country cn,us]
```

默认检查中国和美国。

## 唤醒后执行

```bash
python -m src.cli.main macro-check
```

## 注意事项

- 覆盖中美两国数据（CN: CPI/PMI/Shibor, US: CPI/GDP/利率/收益率曲线/失业率/消费者信心）
- 同时展示黄金/原油价格、汇率快照、全球指数收盘、加密货币行情（从已拉取的 Parquet 数据读取）
- 宏观评分仅基于可获得的数据，置信度低时需提醒用户数据不全
