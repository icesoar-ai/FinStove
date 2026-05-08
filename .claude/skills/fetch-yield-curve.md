---
name: fetch-yield-curve
description: 显示美国国债收益率曲线（3M/1Y/2Y/5Y/10Y/30Y）
trigger: /fetch-yield-curve
---

# /fetch-yield-curve

## 用法

```
/fetch-yield-curve               # 显示最新收益率曲线 + 利差
/fetch-yield-curve --history     # 显示历史曲线数据
```

## 唤醒后执行

```bash
python -m src.cli.main yield-curve
python -m src.cli.main yield-curve --history    # 历史模式
```

## 数据来源

FRED (Federal Reserve Economic Data)，需设置环境变量 `FRED_API_KEY`。

免费申请: https://fred.stlouisfed.org/docs/api/api_key.html

## 存储

```
data/macro/us/treasury_3m/daily.parquet
data/macro/us/treasury_1y/daily.parquet
data/macro/us/treasury_2y/daily.parquet
data/macro/us/treasury_5y/daily.parquet
data/macro/us/treasury_10y/daily.parquet
data/macro/us/treasury_30y/daily.parquet
```

## 输出示例

```
US Treasury Yield Curve
  30Y: 4.65%
  10Y: 4.32%
   5Y: 4.15%
   2Y: 4.28%
   1Y: 4.18%
   3M: 4.35%

  10Y-2Y Spread: +0.04%
  10Y-3M Spread: -0.03%
```

## 注意事项

- 利差为负（红色）表示收益率曲线倒挂，通常预示经济衰退
- 需要 FRED_API_KEY，无 key 时显示提示
