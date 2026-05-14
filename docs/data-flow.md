# 数据流架构

## 整体数据流

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLI 命令层                                     │
│  fetch ohlcv / index / commodity ...    analyze-stock / full-report ...  │
└────────┬───────────────────────────────────────────────┬────────────────┘
         │  写路径 (fetch)                               │  读路径 (analyze)
         ▼                                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         DataGateway                                     │
│                      (src/data/gateway.py)                              │
│                                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────────────┐  │
│  │ _read_or_   │  │ _force_fetch │  │ _try() — 统一异常捕获           │  │
│  │ fetch()     │  │              │  │   AKShare → yfinance 降级       │  │
│  └─────────────┘  └──────────────┘  └────────────────────────────────┘  │
└────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬───────────────────┘
     │      │      │      │      │      │      │      │
     ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌─────┐ ┌─────┐ ┌────┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌──────┐
│ AK  │ │ YF  │ │FRED│ │CG │ │CN │ │SEC│ │BS │ │ News │    ← Data Providers
│Share│ │Fin. │ │    │ │   │ │INFO│ │ED-│ │   │ │      │      (src/data/providers/)
│     │ │     │ │    │ │   │ │    │ │GAR│ │   │ │      │
└──┬──┘ └──┬──┘ └──┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └──┬───┘
   │       │       │     │     │     │     │       │
   ▼       ▼       ▼     ▼     ▼     ▼     ▼       ▼
┌─────────────────────────────────────────────────────────┐
│              DataCache                                   │    ← SQLite 缓存
│         (~/.cache/stocks/)                               │      (src/data/cache.py)
│          API 请求去重 + TTL                              │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│            ParquetStorage                                │    ← 持久化存储
│           (data/*.parquet)                                │      (src/data/storage.py)
│        增量合并 (merge_and_save)                          │
└─────────────────────────────────────────────────────────┘
```

## 读路径 (读优先)

```
CLI analyze 命令
  → gw.get_daily(symbol, market)
     → Parquet.load("stock", market, dir_name, "daily")
         ├─ 有 + 日期够新 → 直接返回
         └─ 无 / 过期
              → Provider API
                   → standardize(df)
                        → DataCache.set(TTL)
                        → Parquet.merge_and_save()
                        → 返回 DataFrame
```

## 写路径 (强制刷新)

```
CLI fetch 命令
  → gw.get_daily(symbol, market, force=True)
     → Provider API (跳过 Parquet 检查)
          → standardize(df)
               → Parquet.merge_and_save()
               → 返回 DataFrame
```

## 增量获取流程

```
请求 fetch 600519.SH
        │
        ▼
  Parquet 有数据？
   ┌─────┴─────┐
  是           否
   │            │
   ▼            ▼
查到最新日期   全量请求 API
   │            │
   │            ▼
   │        _cached() 先查 SQLite
   │         ┌──命中：直接返回
   │         └──未命中：调 API
   │                    │
   ▼                    ▼
只请求 [last+1, today]  合并去重 → 写 Parquet + 写 SQLite
   │
   ▼
合并新数据 → 写回 Parquet
返回合并后的完整数据
```

三种缓存状态下的行为：

| Parquet | SQLite | 行为 |
|---------|--------|------|
| 有，到昨天 | 有 | 只拉 1 天 → 合并写 Parquet (几乎无 API 调用) |
| 有，到昨天 | 空 (被清) | 只拉昨天到今天 ≈2天 → 写 Parquet + 重建缓存 |
| 无 | 无 | 全量拉取 → 写 Parquet + 缓存 |

SQLite 丢了不影响数据完整性，只会多一两次 API 请求。

## 降级路径 (A股专属 — 三级链)

```
gw.get_daily("603650", Market.CN)
  → AKShareProvider.get_daily("603650")
      ├─ 成功 → 返回
      └─ 异常/空
           → YFinanceProvider.get_daily("603650", "cn", store_symbol="603650_彤程新材")
                ├─ 成功 → 返回
                └─ 异常/空
                     → BaostockProvider.get_daily("603650", store_symbol="603650_彤程新材")
                          → baostock API (免费免注册)
                          → Parquet.merge_and_save(→ .../603650_彤程新材/daily.parquet)
```

## 数据生命周期

```
API 请求 → DataCache (去重) → ParquetStorage (持久化)
                │                    │
                TTL 过期自动清理    永久保留，按日期去重
                绕过去重请求        支持增量追加
```

---

## Provider 详情

### 清单

| Provider | 数据源 | 覆盖范围 | 代码量 |
|----------|--------|---------|--------|
| AKShare | 东方财富/同花顺/巨潮 | A股日线/三张表/15+宏观指标/资金流向/新闻/实时行情 | 536 行 |
| YFinance | Yahoo Finance | 全球股票/商品/外汇/指数/加密货币/分红/盘中K线 | 467 行 |
| FRED | 美联储经济数据库 | 利率/CPI/GDP/PMI/失业率/收益率曲线/消费者信心 | 319 行 |
| CoinGecko | CoinGecko | 加密货币价格/历史/市值 | 284 行 |
| CNINFO | 巨潮资讯网 | A股年报 PDF + MD | 193 行 |
| SEC EDGAR | SEC | 美股 10-K 年报 | 84 行 |
| Baostock | baostock | A股日线 (免费免注册，三级降级) | 80 行 |
| News | 东方财富 + CCTV | A股新闻 | 84 行 |

### 各 Provider 接口

#### AKShare

| 方法 | 数据 |
|------|------|
| `get_daily` | A股日线 OHLCV |
| `get_info` | 股票基本信息 |
| `get_dividends` | 分红记录 |
| `get_financials` | 三张表 (同花顺 `stock_financial_*_ths`) |
| `get_index_daily` | A股指数日线 |
| `get_northbound` / `get_southbound` | 沪深港通资金流向 |
| `get_shibor` / `get_shibor_latest` | 银行间拆借利率 |
| `get_cpi` / `get_ppi` | 消费/生产价格指数 |
| `get_pmi` / `get_caixin_pmi` / `get_non_man_pmi` | PMI (官方/财新/非制造业) |
| `get_gdp_cn` | GDP |
| `get_money_supply` | M1/M2 货币供应 |
| `get_lpr` | 贷款市场报价利率 |
| `get_fx_reserves` | 外汇储备 |
| `get_unemployment_cn` | 城镇失业率 |
| `get_exports_yoy` / `get_imports_yoy` | 进出口同比 |
| `get_industrial_production` | 工业增加值 |
| `get_retail_sales` | 社会消费品零售 |
| `get_social_financing` | 社会融资规模 |
| `get_bond_yield_cn` | 中国国债收益率曲线 |
| `get_*_spot` | 各市场实时行情快照 |
| `get_intraday` | A股盘中分钟K线 |

**限制：** 东方财富频繁限流，新 ticker 首次拉取常失败。接口偶尔变更，字段名可能漂移。无港股/美股财报、ETF、可转债。复权需手动指定。

#### YFinance

| 方法 | 数据 |
|------|------|
| `get_daily` | 全球股票日线 |
| `get_info` / `get_financials` / `get_dividends` | 股票信息/财报/分红 |
| `get_commodity` / `get_commodity_daily` | 大宗商品期货 |
| `get_forex` / `get_forex_daily` | 外汇汇率 |
| `get_crypto` / `get_crypto_daily` | 加密货币 |
| `get_index` / `get_index_daily` | 全球指数 |
| `get_dxy` / `get_dxy_current` | 美元指数 |
| `get_intraday` | 盘中分钟K线 |

**限制：** 批量请求易触发 Rate Limit，多品种必须加间隔。默认复权偶尔出错。部分品种历史短 (CNY 相关汇率对、商品连续合约 `GC=F`)。A股/港股延迟 15 分钟。退市标的可能查不到。

#### FRED

| 方法 | 数据 |
|------|------|
| `get_federal_funds_rate` | 联邦基金利率 |
| `get_cpi_yoy` / `get_core_cpi_yoy` | CPI / 核心 CPI |
| `get_gdp_growth` / `get_gdp_yoy` | GDP 增速 |
| `get_unemployment_rate` | 失业率 |
| `get_yield_curve` / `get_yield_curve_history` | 美债收益率曲线 |
| `get_pmi_manufacturing` / `get_pmi_services` | ISM PMI |
| `get_consumer_sentiment` | 消费者信心 |
| `get_all_macro_data` | 全部宏观聚合 |

**限制：** 需 `FRED_API_KEY` 环境变量 (免费注册)。仅美国，无中国/欧洲宏观。有速率限制但不频繁。

#### CoinGecko

| 方法 | 数据 |
|------|------|
| `get_price` | 实时价格 |
| `get_market_data` | 市值/排名等 |
| `get_historical` / `get_historical_ohlcv` | 历史 OHLCV |
| `get_top_coins` | 市值排名 |
| `get_global_stats` | 全局统计 |

**限制：** 免费版严格限速 ~10-30次/分钟。历史精度不如交易所 API。仅主流币种覆盖。

#### CNINFO

| 方法 | 数据 |
|------|------|
| `download_reports` | A股年报 PDF → Markdown 自动转换 |

**限制：** 仅 A 股年报，缺半年报/季报。年报发布后约 1-3 天可查。

#### SEC EDGAR

| 方法 | 数据 |
|------|------|
| `download_10k` | 美股 10-K 年报 |

**限制：** 仅支持 10-K 年报，无 10-Q 季报。下载速度慢，仅美股上市公司。

#### Baostock

| 方法 | 数据 |
|------|------|
| `get_daily` | A股日线 |

**限制：** 仅 A 股日线，无财务/指数/汇率数据。作为第三降级使用。

#### News

**数据源：** 东方财富 (AKShare) + CCTV

**限制：** 仅 CN 新闻，无 US/HK 源，未扩展 RSS 源。

## 各组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| CLI Commands | `src/cli/commands/*.py` | 用户交互，参数解析，Rich 输出 |
| DataGateway | `src/data/gateway.py` | 统一入口，降级策略，数据路由 |
| AKShareProvider | `src/data/providers/akshare.py` | A股/宏观/指数 |
| YFinanceProvider | `src/data/providers/yfinance.py` | 全球股票/商品/外汇/加密 |
| FREDProvider | `src/data/providers/fred.py` | 美国宏观 |
| CoinGeckoProvider | `src/data/providers/coingecko.py` | 加密货币行情 |
| CNINFOProvider | `src/data/providers/cninfo.py` | A股年报 PDF/MD |
| SECEDGARProvider | `src/data/providers/edgar.py` | 美股 10-K 年报 |
| BaostockProvider | `src/data/providers/baostock.py` | A股日线，三级降级 |
| NewsProvider | `src/data/providers/news.py` | 新闻抓取 |
| DataCache | `src/data/cache.py` | API 请求缓存，TTL 控制 |
| ParquetStorage | `src/data/storage.py` | 数据持久化，增量合并 |
