# 数据流架构

## 整体架构

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
└────┬──────┬──────┬──────┬──────┬──────┬─────────────────────────────────┘
     │      │      │      │      │      │
     ▼      ▼      ▼      ▼      ▼      ▼
┌─────┐ ┌─────┐ ┌────┐ ┌───┐ ┌───┐ ┌──────┐
│ AK  │ │ YF  │ │FRED│ │CG │ │CN │ │ News │     ← Data Providers
│Share│ │Fin. │ │    │ │   │ │INFO│ │      │       (src/data/providers/)
└──┬──┘ └──┬──┘ └──┬─┘ └─┬─┘ └─┬─┘ └──┬───┘
   │       │       │     │     │       │
   ▼       ▼       ▼     ▼     ▼       ▼
┌──────────────────────────────────────────────┐
│              DataCache                         │     ← SQLite 缓存层
│         (~/.cache/stocks/)                     │       (src/data/cache.py)
│          API 请求去重 + TTL                    │
└──────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────┐
│            ParquetStorage                     │     ← 持久化存储
│           (data/*.parquet)                     │       (src/data/storage.py)
│        增量合并 (merge_and_save)               │
└──────────────────────────────────────────────┘
```

## 读路径 (读优先)

```
CLI analyze 命令
  → gw.get_daily(symbol, market)
     → Parquet.load("stock", market, dir_name, "daily")
         ├─ 有 + 日期够新 → 直接返回 ✓
         └─ 无 / 过期
              → Provider API
                   → standardize(df)
                        → DataCache.set(TTL)   ← 写 SQLite
                        → Parquet.merge_and_save() ← 写磁盘
                        → 返回 DataFrame
```

## 写路径 (强制刷新)

```
CLI fetch 命令
  → gw.get_daily(symbol, market, force=True)
     → Provider API (跳过 Parquet 检查)
          → standardize(df)
               → Parquet.merge_and_save() ← 强制写磁盘
               → 返回 DataFrame
```

## 降级路径 (A股专属)

```
gw.get_daily("603650", Market.CN)
  → AKShareProvider.get_daily("603650")
      ├─ 成功 → 返回
      └─ 异常/空
           → YFinanceProvider.get_daily("603650", "cn", store_symbol="603650_彤程新材")
                → _build_symbol("603650", "cn") → "603650.SS"
                → yfinance API
                → Parquet.merge_and_save(→ data/stock/cn/603650_彤程新材/daily.parquet)
```

## 各组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| **CLI Commands** | `src/cli/commands/*.py` | 用户交互，参数解析，Rich 输出 |
| **DataGateway** | `src/data/gateway.py` | 统一入口，降级策略，数据路由 |
| **AKShareProvider** | `src/data/providers/akshare.py` | A股/宏观/指数 (东方财富) |
| **YFinanceProvider** | `src/data/providers/yfinance.py` | 全球股票/商品/外汇/加密 |
| **FREDProvider** | `src/data/providers/fred.py` | 美国宏观 (需 API Key) |
| **CoinGeckoProvider** | `src/data/providers/coingecko.py` | 加密货币行情 |
| **CNINFOProvider** | `src/data/providers/cninfo.py` | A股年报 PDF/MD |
| **NewsProvider** | `src/data/providers/news.py` | 新闻 (东方财富 + CCTV) |
| **DataCache** | `src/data/cache.py` | API 请求缓存，TTL 控制，存 ~/.cache/stocks/ |
| **ParquetStorage** | `src/data/storage.py` | 数据持久化，增量合并，存 data/*.parquet |

## 数据生命周期

```
API 请求 → DataCache (去重) → ParquetStorage (持久化)
                │                    │
                TTL 过期自动清理    永久保留，按日期去重
                绕过去重请求        支持增量追加
```
