---
name: macro-check
description: 宏观环境评估，含利率/通胀/PMI/流动性信号
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
- 宏观评分仅基于可获得的数据，置信度低时需提醒用户数据不全
