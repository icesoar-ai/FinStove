---
name: fetch-stock
description: 一键抓取股票数据——年报(PDF+MD) + 财务三表。年份范围根据用户要求灵活决定
trigger: /fetch-stock
---

# /fetch-stock

## 用法

```
/fetch-stock <TICKER>
```

如果用户说了具体年份范围（如"最近10年"、"近3年"、"2018-2023"），根据用户的要求计算对应的 `--years` 参数。用户没有说的话，默认最近 5 年。

## 唤醒后执行

根据用户指定的年份范围，依次运行：

```bash
python -m src.cli.main financials "<TICKER>"
python -m src.cli.main reports "<TICKER>" --years <计算出的年份>
```

## 追问

数据拉取完成后，可继续：
- `/full-report <TICKER>` — 综合多维分析
- 直接提问："分析这只股票的财务状况"
