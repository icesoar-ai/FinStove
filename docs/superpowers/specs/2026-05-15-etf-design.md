# ETF 数据支持 — 设计

## 背景

ETF 不支持，无 ETF 数据。

## 摸底

| 数据 | A股 ETF | 美股 ETF | 来源 |
|------|---------|----------|------|
| OHLCV 日线 | ✅ | ✅ | AKShare `fund_etf_hist_em` / yfinance |
| 净值 NAV | ✅ | ✅ | AKShare `fund_etf_fund_info_em` / yfinance |
| 实时行情 (含折溢价/份额) | ✅ | ✅ | AKShare `fund_etf_spot_em` / yfinance |
| 持仓 | ✅ | ❌ | AKShare `fund_portfolio_hold_em` |
| 基本信息 (费率/AUM) | ✅ | ✅ | AKShare / yfinance info |

## 设计

### 1. ETF Provider (`src/data/providers/etf.py`)

新建，封装 AKShare + yfinance 双源：

| 方法 | A股 | 美股 |
|------|-----|------|
| `get_daily(code, market)` | AKShare `fund_etf_hist_em` | yfinance |
| `get_nav(code, market)` | AKShare `fund_etf_fund_info_em` | yfinance history |
| `get_holdings(code, market)` | AKShare `fund_portfolio_hold_em` | 不支持 |
| `get_spot()` | AKShare `fund_etf_spot_em` | yfinance |

### 2. 存储路径

`data/etf/{market}/{code}.{market}/`

- `data/etf/cn/510050.SH/daily.parquet`
- `data/etf/cn/510050.SH/nav.parquet`
- `data/etf/cn/510050.SH/holdings.parquet`
- `data/etf/us/SPY.US/daily.parquet`

### 3. CLI

`fetch etf <TICKER>` — OHLCV + NAV + 持仓（如有）
`live spot` — 已含 ETF（AKShare `fund_etf_spot_em` 返回全市场）

### 4. 不做

- US ETF 持仓（yfinance 不提供）
- ETF 分析模块
- 盘中分时
