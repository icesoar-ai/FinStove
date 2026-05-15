# CLI 命令参考

## 数据抓取 (`fetch`)

```bash
python -m src.cli.main fetch ohlcv <TICKER> [--start DATE] [--intraday]
python -m src.cli.main fetch index [MARKET] [CODE] [--spot]
python -m src.cli.main fetch commodity [CODE] [--spot]
python -m src.cli.main fetch forex [PAIR] [--spot]
python -m src.cli.main fetch crypto [SYMBOL] [--spot]
python -m src.cli.main fetch financials <TICKER>
python -m src.cli.main fetch reports <TICKER>
python -m src.cli.main fetch flow
python -m src.cli.main fetch yield-curve [--history]
```

| 命令 | 覆盖 | 说明 |
|------|------|------|
| `fetch ohlcv <TICKER>` | A股/港股/美股 | 个股日线，A股三级降级 (AKShare→yfinance→Baostock) |
| `fetch index [MARKET] [CODE]` | CN/US/HK/JP/UK/DE/FR | 无参拉全部；cn 走 AKShare，其它走 yfinance |
| `fetch commodity [CODE]` | 黄金/白银/WTI/布伦特/天然气/铜/铂/钯/铝/锌 | 无参拉全部 10 种 |
| `fetch forex [PAIR]` | 9 对 | USDCNY/EURCNY/JPYCNY/EURUSD/USDJPY/GBPUSD/AUDUSD/USDCAD/GBPCNY |
| `fetch crypto [SYMBOL]` | BTC/ETH/SOL 等 | YFinance 优先，降级 CoinGecko |
| `fetch financials <TICKER>` | A股/美股 | 三张表 + 财务指标 + 分红记录 |
| `fetch reports <TICKER>` | A股 | 年报 PDF + Markdown (CNINFO) |
| `fetch flow` | 沪深港通 | 北向 (外资→A股) + 南向 (内资→港股) |
| `fetch yield-curve` | 美债 | 3M/1Y/2Y/5Y/10Y/30Y，需 `FRED_API_KEY` |

## 实时行情 (`live`)

```bash
python -m src.cli.main live spot              # 全球快照
python -m src.cli.main live spot -m cn        # A股涨跌榜 (hk/us)
python -m src.cli.main live spot <TICKER>     # 个股实时行情
python -m src.cli.main live intraday <TICKER> [-i 5m]
```

## 分析

```bash
python -m src.cli.main analyze-stock <TICKER>      # 技术分析
python -m src.cli.main macro-check                 # 宏观评估
python -m src.cli.main valuation <TICKER>          # 估值分析 (10方法)
python -m src.cli.main full-report <TICKER>        # 综合多维分析
python -m src.cli.main sentiment <TICKER> [-d 7]   # 新闻情绪
python -m src.cli.main report-analyze <TICKER>     # 年报文本分析
python -m src.cli.main correlation-check           # 跨市场联动
python -m src.cli.main risk-check <TICKER>         # 风险评估
python -m src.cli.main benchmark <TICKER>          # 基准对比
python -m src.cli.main scenario <TICKER>           # 情景分析
python -m src.cli.main review <TICKER>             # 回顾历史判断
python -m src.cli.main market-scan                 # 多市场扫描
python -m src.cli.main summary                     # 每日数据汇总
```
