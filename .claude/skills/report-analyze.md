---
name: report-analyze
description: 年报文本分析 — 提取审计意见、关键指标、风险因素、管理层展望
trigger: /report-analyze
---

# /report-analyze

## 用法

```
/report-analyze <TICKER>         # A股年报文本分析
```

需要先下载年报：`/fetch-stock <TICKER> reports`

## 分析维度

| 维度 | 方法 | 输出 |
|------|------|------|
| 审计意见 | 关键词匹配 | 标准无保留/保留/无法表示/否定 → Signal |
| 关键指标 | 正则提取 | 营业收入/归母净利润/每股收益/ROE/经营现金流 |
| 风险因素 | 关键词计数 | 风险提示数量/重大诉讼/担保/关联交易 |
| 管理层展望 | 关键词计数 | 正面词 vs 负面词 → 乐观/谨慎 |

## 唤醒后执行

```bash
python -m src.cli.main report-analyze <TICKER>
```

## 存储

年报 MD 文件: `data/stock/cn/{CODE}_{NAME}/reports/*.md`

## 注意事项

- 仅支持 A 股（年报通过 CNINFO 下载）
- 文本提取依赖 MarkItDown 转换质量，PDF 转 MD 可能丢失表格结构
- 指标提取为近似匹配，可能与审计后数据有偏差
