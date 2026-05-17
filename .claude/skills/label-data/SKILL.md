---
name: label-data
description: 为 data/ 下所有资产目录生成/刷新名称标记文件，让文件系统一眼可识别
trigger: /label-data
---

# /label-data

当用户提到"刷新/更新/标记/生成 [名字/名称/简称/说明/标记]"时，使用此 skill。

## 用法

```
/label-data           # 生成标记文件（跳过已存在）
/label-data --force   # 覆盖所有已存在的标记文件
/label-data --refresh # 清除名称缓存后重新查 API（股票改名时用）
```

## 唤醒后执行

```bash
./bin/fstove label-data
```

如果用户要求刷新或覆盖，加 `--force` 或 `--refresh`：

```bash
./bin/fstove label-data --force    # 覆盖已有
./bin/fstove label-data --refresh  # 清缓存重查 API
```

## 效果

为 `data/` 下每个资产目录创建 `__{名称}.name.txt` 标记文件：

```
data/stock/cn/601318.SH/__中国平安.name.txt
data/commodity/global/GC/__黄金.name.txt
data/index/us/SPX/__标普500.name.txt
data/forex/global/USDCNY/__美元_人民币.name.txt
```

名称来源：
- A股/美股/港股/ETF → DataGateway.name() 统一查询，内建 name cache + AKShare/yfinance 调用
- 指数/商品/外汇/加密 → 硬编码中文映射

## 注意事项

- 幂等操作，可随时重复执行
- 所有名称查询统一通过 DataGateway，不直接碰 Provider
- 不影响 Parquet 数据读写
