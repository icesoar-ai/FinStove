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

- 目前主要覆盖中国数据（CPI/PMI/Shibor），美国宏观需等 FRED provider 完成后支持
- 宏观评分仅基于可获得的数据，置信度低时需提醒用户数据不全
