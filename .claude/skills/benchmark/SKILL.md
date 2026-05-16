---
name: benchmark
description: 基准对比分析（vs 指数 + 股债性价比）
trigger: /benchmark
---

# /benchmark

## 用法

```
/benchmark <TICKER> [--market auto]
```

## 唤醒后执行

```bash
python -m src.cli.main benchmark <TICKER>
```

## 注意事项

- 对比个股 vs 对应市场基准指数 (CN→沪深300, US→S&P 500, HK→恒生, JP→日经225...)
- 结合国债收益率评估股债相对吸引力
- 基准指数数据需提前通过 `/fetch-index` 拉取
