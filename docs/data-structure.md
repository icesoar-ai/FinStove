# 数据持久化目录结构

所有原始数据以 Parquet 格式存储在 `data/` 目录下。

## 整体结构

```
data/
├── stock/           # 个股数据
│   └── {market}/    #   cn / us / hk
│       └── {CODE}_{NAME}/    # 例: 600388_龙净环保
│           ├── daily.parquet        # 日线 OHLCV
│           ├── income.parquet       # 利润表
│           ├── balance_sheet.parquet # 资产负债表
│           ├── cashflow.parquet     # 现金流量表
│           ├── financials.parquet   # 主要财务指标
│           ├── dividends.parquet    # 分红记录
│           └── reports/             # 年报 PDF/MD
├── index/           # 全球指数
│   ├── cn/          # A股: 000001(上证), 000300(沪深300), 399001(深证), 399006(创业板), 000688(科创50), 000016(上证50), 000905(中证500)
│   ├── us/          # 美股: SPX, NDX, DJI, RUT, VIX
│   ├── hk/          # 港股: HSI
│   ├── jp/          # 日股: N225
│   ├── uk/          # 英股: FTSE
│   ├── de/          # 德股: DAX
│   └── fr/          # 法股: CAC
│       └── {CODE}/
│           └── daily.parquet
├── commodity/       # 大宗商品期货 (全球)
│   └── global/
│       ├── GC/      # 黄金
│       ├── CL/      # 原油
│       ├── SI/      # 白银
│       ├── HG/      # 铜
│       ├── NG/      # 天然气
│       ├── BZ/      # 布伦特原油
│       ├── PL/      # 铂金
│       ├── PA/      # 钯金
│       ├── ZC/      # 玉米
│       └── ZS/      # 大豆
│           └── daily.parquet
├── forex/           # 外汇
│   └── global/
│       ├── dxy/             # 美元指数
│       ├── USDCNY/          # 美元/人民币
│       ├── EURUSD/ EURCNY/  # 欧元
│       ├── USDJPY/ JPYCNY/  # 日元
│       ├── GBPUSD/ GBPCNY/  # 英镑
│       ├── AUDUSD/          # 澳元
│       └── USDCAD/          # 加元
│           └── daily.parquet
├── crypto/          # 加密货币
│   └── global/
│       ├── BTC/
│       └── ETH/
│           └── daily.parquet
├── macro/           # 宏观经济
│   ├── cn/
│   │   ├── cpi/             └── monthly.parquet
│   │   ├── pmi/             └── monthly.parquet
│   │   └── shibor/          └── daily.parquet
│   └── us/
│       ├── gdp/             └── quarterly.parquet
│       ├── cpi/             └── monthly.parquet
│       ├── core_cpi/        └── monthly.parquet
│       ├── unemployment/    └── monthly.parquet
│       ├── consumer_sentiment/ └── monthly.parquet
│       ├── fed_funds_rate/  └── monthly.parquet
│       └── treasury_3m/1y/2y/5y/10y/30y/ └── daily.parquet
├── flow/            # 资金流向
│   └── cn/
│       ├── northbound/      └── daily.parquet   # 北向资金
│       └── southbound/      └── daily.parquet   # 南向资金
└── stock_names.json  # A股名称缓存

# 实时快照（通过 fetch 命令 --spot flag 生成，单行覆盖写入）
# data/index/{market}/{CODE}/spot.parquet
# data/commodity/global/{CODE}/spot.parquet
# data/forex/global/{PAIR}/spot.parquet
# data/crypto/global/{CODE}/spot.parquet
```

## 命名规则

| 维度 | 规则 |
|------|------|
| **目录层级** | `资产类别 > 市场(或global) > 代码` |
| **品种目录** | A股: `{CODE}_{名称}`，其余: `{CODE}` |
| **频率** | `daily.parquet` / `monthly.parquet` / `quarterly.parquet` |
| **格式** | Apache Parquet (Snappy 压缩) |

## 核心品种码表

| 代码 | 品种 | 类别 |
|------|------|------|
| GC=F | COMEX 黄金期货 | commodity |
| CL=F | WTI 原油期货 | commodity |
| HG=F | COMEX 铜期货 | commodity |
| SPX / NDX / DJI / RUT | 标普 / 纳斯达克 / 道琼斯 / 罗素 | index/us |
| 000300 / 000905 | 沪深300 / 中证500 | index/cn |
| USDCNY / DXY | 美元人民币 / 美元指数 | forex |
| BTC / ETH | 比特币 / 以太坊 | crypto |

## 数据来源

| 类别 | 来源 | 说明 |
|------|------|------|
| A股日线/指数 | akshare | 东方财富接口 |
| A股财报 | akshare (同花顺) | stock_financial_*_ths |
| 全球品种 | yfinance | 美股/商品/外汇/加密货币/美指 |
| 美债收益率 | FRED | 需 FRED_API_KEY |
| 资金流向 | akshare | 沪深港通 |
