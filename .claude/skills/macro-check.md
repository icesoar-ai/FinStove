---
name: macro-check
description: 宏观环境评估（CPI/PPI/PMI/GDP/利率/M2/社融/进出口/就业/收益率曲线/汇率/商品/全球指数/加密货币）
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

- CN 覆盖 15+ 指标: CPI, PPI, PMI(官方/财新/非制造业), GDP, SHIBOR, LPR, M1/M2,
  社会融资, 外汇储备, 进出口, 工业增加值, 社消零售, 失业率, 国债收益率曲线
- US 覆盖 (via FRED): CPI, GDP, PMI, 政策利率, 收益率曲线, 失业率
- 同时展示黄金/原油价格、汇率快照、全球指数收盘、加密货币行情
- 宏观评分基于全部可获得的数据，置信度低时提醒用户数据不全
