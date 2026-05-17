---
name: sentiment
description: 新闻情绪分析 — jieba分词 + 金融情感词典打分
trigger: /sentiment
---

# /sentiment

## 用法

```
/sentiment <TICKER>           # 近7天新闻情绪
/sentiment <TICKER> -d 14     # 近14天
```

## 数据源

| 源 | 函数 | 说明 |
|----|------|------|
| 东方财富 | `stock_news_em` | 个股新闻 |
| CCTV | `news_cctv` | 宏观政策新闻 |

## 唤醒后执行

```bash
./bin/fstove sentiment <TICKER> [-d DAYS]
```

## 情绪引擎

- jieba 中文分词 + 金融情感词典 (正面/负面/否定词/程度副词)
- 时间加权聚合 (近 2 天半衰期)
- 输出：综合得分 / 正面负面中性比例 / 逐条新闻明细

## 注意事项

- 需要 jieba 分词库
- 东方财富接口可能限流
