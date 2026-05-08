---
name: fetch-index
description: 抓取中国股市指数日线数据（上证/深证/沪深300/上证50/创业板/科创50/中证500）
trigger: /fetch-index
---

# /fetch-index

## 用法

```
/fetch-index              # 拉取全部 7 个指数
/fetch-index <CODE>       # 只拉指定指数
```

支持指数：

| 代码 | 名称 |
|------|------|
| 000001 | 上证指数 |
| 399001 | 深证成指 |
| 000300 | 沪深300 |
| 000016 | 上证50 |
| 399006 | 创业板指 |
| 000688 | 科创50 |
| 000905 | 中证500 |

## 唤醒后执行

```bash
python -m src.cli.main index <CODE>
```

不传 CODE 时拉取全部指数。

## 存储

数据写入 `data/index/cn/{code}/daily.parquet`，支持增量更新。
