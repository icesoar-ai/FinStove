---
name: reports
description: 下载A股年报PDF全文+摘要，并自动转换为Markdown
trigger: /reports
---

# /reports

## 用法

```
/reports <TICKER> [--years 2023,2024]
```

不指定 `--years` 则下载全部可用年报。

## 唤醒后执行

```bash
python -m src.cli.main reports "<TICKER>" --years <YEARS>
```

## 输出

年报 PDF + Markdown 文本存储于 `data/stock/cn/{symbol}/reports/` 目录下，每个年份产生：
- `{year}_年报.pdf` + `{year}_年报.md`
- `{year}_摘要.pdf` + `{year}_摘要.md`

## 追问

下载后可进一步分析：
- "分析 2024 年年报中的风险因素"
- "对比近 3 年收入变化趋势"
- "提取管理层讨论部分"
