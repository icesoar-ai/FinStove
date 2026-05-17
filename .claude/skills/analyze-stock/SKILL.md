---
name: analyze-stock
description: 个股深度技术分析，含趋势/动量/成交量/支撑阻力信号
trigger: /analyze-stock
---

# /analyze-stock

## 用法

```
/analyze-stock <TICKER> [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

A股格式: `600519.SH`, `000858.SZ`
港股: `00700.HK`
美股: `AAPL` (直接写代码)

## 唤醒后执行

```bash
./bin/fstove analyze-stock "<TICKER>"
```

将输出直接展示给用户。如果 error，按网络问题/限流/无效代码分别解释。

## 追问

展示结果后，可主动问：
- "想看这只股票的宏观环境影响吗？ `/macro-check`"
- "要对比同行业估值吗？ (后续 phase 支持)"
