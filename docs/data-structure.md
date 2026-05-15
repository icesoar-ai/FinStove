# 数据持久化目录结构

所有原始数据以 Parquet 格式存储在 `data/` 目录下。

## 整体结构

```
data/
├── stock/           # 个股数据
│   └── {market}/    #   cn / us / hk
│       └── {CODE}.{SUFFIX}/  # 例: 601318.SH (中国平安), AAPL.US
│           ├── __{名称}.name.txt     # 名称标记文件 (label-data 命令生成)
│           ├── daily.parquet        # 日线 OHLCV
│           ├── income.parquet       # 利润表
│           ├── balance_sheet.parquet # 资产负债表
│           ├── cashflow.parquet     # 现金流量表
│           ├── financials_summary.parquet # 主要财务指标
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
│   │   ├── cpi/                └── monthly.parquet
│   │   ├── ppi/                └── monthly.parquet
│   │   ├── pmi/                └── monthly.parquet
│   │   ├── caixin_pmi/         └── monthly.parquet
│   │   ├── non_man_pmi/        └── monthly.parquet
│   │   ├── gdp/                └── quarterly.parquet
│   │   ├── money_supply/       └── monthly.parquet
│   │   ├── social_financing/   └── monthly.parquet
│   │   ├── lpr/                └── monthly.parquet
│   │   ├── fx_reserves/        └── monthly.parquet
│   │   ├── exports_yoy/        └── monthly.parquet
│   │   ├── imports_yoy/        └── monthly.parquet
│   │   ├── industrial_production/ └── monthly.parquet
│   │   ├── retail_sales/       └── monthly.parquet
│   │   ├── unemployment/       └── monthly.parquet
│   │   ├── bond_yield/         └── daily.parquet
│   │   └── shibor/             └── daily.parquet
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

# 实时快照（通过 fetch --spot flag 生成，单行覆盖写入）
# data/index/{market}/{CODE}/spot.parquet
# data/commodity/global/{CODE}/spot.parquet
# data/forex/global/{PAIR}/spot.parquet
# data/crypto/global/{CODE}/spot.parquet

# 盘中分钟K线（通过 intraday 命令或 ohlcv --intraday flag 生成，datetime 去重）
# data/stock/{market}/{CODE}/intraday_{interval}.parquet
# 例: data/stock/cn/600388_龙净环保/intraday_5m.parquet

# 新闻数据（通过 NewsProvider 抓取）
# data/news/{market}/{CODE}/news.parquet
```

## 命名规则

| 维度 | 规则 |
|------|------|
| **目录层级** | `资产类别 > 市场(或global) > 代码` |
| **品种目录** | A股: `{CODE}_{名称}`，其余: `{CODE}` |
| **频率** | `daily.parquet` / `monthly.parquet` / `quarterly.parquet` / `intraday_{interval}.parquet` |
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

## 名称标记文件

每个资产目录下可放置 `__{名称}.name.txt` 标记文件，方便在文件系统中直接识别资产。

运行 `python -m src.cli.main label-data` 自动为 `data/` 下所有资产生成标记文件。

名称来源：A 股走 AKShare + `stock_names.json` 缓存，指数/商品/外汇/加密走硬编码中文映射，美股/港股走 yfinance。

```
data/stock/cn/601318.SH/__中国平安.name.txt
data/commodity/global/GC/__黄金.name.txt
data/forex/global/USDCNY/__美元_人民币.name.txt
```

该文件不影响数据读写——Storage 模块仅访问 `.parquet` 路径。