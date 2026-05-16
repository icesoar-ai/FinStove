---
name: valuation
description: 基本面估值分析，10种估值方法（FCFF/FCFE/DDM/Graham/EPV/NCAV/剩余收益/倍数/FCF质量/财务健康）
trigger: /valuation
---

# /valuation <TICKER>

对 A 股个股执行多方法基本面估值分析。

## 前置条件

需要事先拉取数据：
- `/fetch-stock <TICKER>` — 获取日线 + 财务数据（必须）
- 至少需要利润表数据（来自财务摘要），理想情况需要完整的资产负债表 + 利润表 + 现金流量表

## 执行

```bash
python -m src.cli.main valuation <TICKER>
```

## 数据要求

| 数据 | Parquet 文件 | 需要的方法 |
|------|-------------|-----------|
| 利润表 | `income.parquet` 或 `financials.parquet` | 全部方法 |
| 资产负债表 | `balance_sheet.parquet` 或 `financials.parquet` | Graham/NCAV/Health/FCFF |
| 现金流量表 | `cashflow.parquet` | FCFF/FCFE |
| 日线行情 | `daily.parquet` | Multiples (获取当前PE/PB) |

缺少现金流数据时，FCFF/FCFE 方法会标记为不可用，其余方法正常执行。

## 输出

- 合理价值中位数 + 价值区间 (25-75%分位)
- 方法间一致性评估（高/中/低）
- 每个方法的合理价值、悲观/乐观区间、置信度、关键假设
- 异常警告（如方法间分歧大）

## 注意

- 估值分析只读取已有数据，不会自动拉取。数据不足时报告错误。
- A 股财报审计质量参差，结构化数据可能无法反映真实财务状况，建议结合年报文本分析。
- 所有输出仅供参考，不构成投资建议。
