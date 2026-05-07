---
name: financials
description: 拉取A股财务摘要数据（净利润、营收、EPS、ROE等25项核心指标）
trigger: /financials
---

# /financials

## 用法

```
/financials <TICKER> [--years 2021,2022,2023]
```

不指定 `--years` 则展示2021至今全部年度数据。

## 唤醒后执行

```bash
python -m src.cli.main financials "<TICKER>" --years <YEARS>
```

## 输出

- 终端展示年度核心指标对比表
- 数据保存至 `data/stock/cn/{symbol}/financials.parquet`

## 追问

获取财务数据后可进一步分析：
- "分析近年收入增长趋势"
- "评估资产负债率变化"
- "ROE下降的原因是什么"
- `/full-report <TICKER>` 做综合估值
