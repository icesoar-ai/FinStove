---
name: correlation-check
description: 跨市场联动分析（黄金/DXY/VIX 信号判断 Risk-On/Risk-Off 体制）
trigger: /correlation-check
---

# /correlation-check

## 用法

```
/correlation-check
```

## 唤醒后执行

```bash
./bin/fstove correlation-check
```

## 注意事项

- 分析黄金、美元指数(DXY)、VIX 恐慌指数三个维度
- 判断当前市场处于 Risk-On / Risk-Off / 混合体制
- 数据从已拉取的 Parquet 文件读取，首次使用需先 `/fetch-all`
