---
name: scenario
description: 情景分析（乐观/悲观/反转情景 + 波动率敏感性区间）
trigger: /scenario
---

# /scenario

## 用法

```
/scenario <TICKER> [--market auto]
```

## 唤醒后执行

```bash
python -m src.cli.main scenario <TICKER>
```

## 注意事项

- 基于 52 周高低点推演乐观/悲观情景
- 波动率敏感性：1σ (1月)、2σ (3月) 价格区间
- 200 日均线反转信号
- 默认分析近 3 年数据
