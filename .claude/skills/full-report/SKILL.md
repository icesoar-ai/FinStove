---
name: full-report
description: 全面多维分析报告，7维度加权评分
trigger: /full-report
---

# /full-report

## 用法

```
/full-report <TICKER> [--context long_term|short_term] [--format brief|standard|full]
```

## 唤醒后执行

```bash
./bin/fstove full-report "<TICKER>" --context long_term --format standard
```

输出包含：综合评分 + 分级判断 + 各维度评分表 + 信号摘要 + 风险/趋势/基准判断。

## 追问

报告展示后可深入：
- `/analyze-stock <TICKER>` — 技术面细节
- `/macro-check` — 宏观环境细节
- `/review <TICKER>` — 回顾历史判断
