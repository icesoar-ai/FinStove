---
name: validate
description: 校验 Parquet 数据文件的完整性和合理性——列完整性/OHLCV 合理性/日期/新鲜度
trigger: /validate
---

# /validate

当用户提到"校验/检查/验证 [数据/数据质量/数据完整性]"时，使用此 skill。

## 用法

```
/validate               # 全量校验
/validate --errors-only # 仅显示错误
```

## 唤醒后执行

```bash
./bin/fstove validate
```

如果用户要求只看错误：

```bash
./bin/fstove validate --errors-only
```

## 校验内容

| 检查项 | 严重度 | 说明 |
|--------|--------|------|
| 列完整性 | ERROR | OHLCV 数据缺少必要列 |
| 数据合理性 | ERROR/WARNING | high<low、负成交量；close 超出 [low, high] 范围 |
| 日期合理性 | ERROR/WARNING | 未来日期、非单调递增 |
| 数据新鲜度 | WARNING | 超过阈值未更新（日线 3 天/月频 35 天/季频 95 天） |

非 OHLCV 数据（宏观指标、资金流向等）自动跳过列和 OHLCV 检查，只做日期和新鲜度校验。

## 注意事项

- 只读操作，不触发数据抓取，不修改 Parquet 文件
- 商品/外汇的 close 超出 high/low 警告通常因 24 小时交易导致，属于预期行为
