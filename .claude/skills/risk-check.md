---
name: risk-check
description: 风险评估（VaR/CVaR/最大回撤/波动率/流动性风险）
trigger: /risk-check
---

# /risk-check

## 用法

```
/risk-check <TICKER> [--start 2022-01-01] [--market auto]
```

## 唤醒后执行

```bash
python -m src.cli.main risk-check <TICKER>
```

## 注意事项

- 基于历史日线 OHLCV 计算 VaR(95%)、CVaR、最大回撤、年化波动率、流动性
- 默认分析 2022-01-01 至今的数据，可用 --start 调整
- A 股用 AKShare，其他市场用 yfinance
- 评分从 -2 (高风险) 到 0 (低风险)
