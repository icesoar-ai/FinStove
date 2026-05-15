# 功能参考

## Skills（自然语言指令）

在 Claude Code 中用 `/` 调用，描述和触发词见各 skill 文件。

### 数据抓取

| Skill | 说明 |
|-------|------|
| `/fetch-all` | 一键拉取全部每日数据（指数/商品/汇率/加密货币/美债） |
| `/fetch-stock <TICKER>` | 股票数据抓取（日线/财报/年报，可组合） |
| `/fetch-index [MARKET] [CODE]` | 全球指数日线（CN/US/HK/JP/UK/DE/FR） |
| `/fetch-commodity [CODE]` | 大宗商品期货（黄金/白银/原油/铜/天然气等 10 种） |
| `/fetch-forex [PAIR]` | 外汇汇率（USDCNY/EURCNY/JPYCNY 等 9 对） |
| `/fetch-crypto [SYMBOL]` | 加密货币（BTC/ETH/SOL 等） |
| `/fetch-flow` | 沪深港通资金流向（北向/南向） |
| `/fetch-yield-curve` | 美国国债收益率曲线（3M/1Y/2Y/5Y/10Y/30Y） |

### 实时行情

| Skill | 说明 |
|-------|------|
| `/spot` | 实时行情（全球指数/外汇/商品/加密货币）+ 涨跌榜 + 个股 |
| `/intraday <TICKER>` | 盘中分钟K线，AKShare→yfinance 自动降级 |

### 分析

| Skill | 维度 | 说明 |
|-------|------|------|
| `/analyze-stock <TICKER>` | 技术面 | 趋势/动量/成交量/支撑阻力/形态识别 |
| `/valuation <TICKER>` | 基本面 | 10 种估值方法综合 |
| `/macro-check` | 宏观 | CN 15+指标 + US via FRED + DXY + VIX |
| `/sentiment <TICKER>` | 情绪 | jieba 分词 + 金融情感词典 |
| `/report-analyze <TICKER>` | 年报文本 | 审计意见/指标提取/风险因素/管理层展望 |
| `/full-report <TICKER>` | 综合 | 10 维度加权评分 + 目标价 + 风险 + 情景 |
| `/review <TICKER>` | 跟踪 | 历史判断回顾，胜率 + 偏差度 |
| `/correlation-check` | 跨市场 | 黄金/DXY/VIX → Risk-On/Risk-Off |
| `/risk-check <TICKER>` | 风险 | VaR/CVaR/最大回撤/波动率/流动性 |
| `/benchmark <TICKER>` | 基准对比 | vs 基准指数 + 股债性价比 |
| `/scenario <TICKER>` | 情景 | 乐观/悲观/反转 + 波动率敏感性 |
| `/market-scan` | 概览 | 全球资产 6 维度涨跌幅 + 均线趋势 |

---

## CLI 命令

不含参数的命令等价于其对应的 Skill，带参数的命令提供更精细控制。

### 数据抓取 (`fetch`)

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
| `fetch financials <TICKER>` | A股/港股/美股 | 三张表 + 财务指标 + 分红记录。`--period all|annual|quarterly` 筛选周期 |
| `fetch reports <TICKER>` | A股/美股 | A股: CNINFO 年报/半年报/季报 PDF+MD；美股: SEC EDGAR 10-K/10-Q 文本。港股暂不支持。`--type all|annual|semi_annual|quarterly`, `--years` 默认近2年 |
| `fetch etf <TICKER>` | A股/美股 | ETF 日线 + 净值 + 持仓 (A股) |
| `fetch flow` | 沪深港通 | 北向 (外资→A股) + 南向 (内资→港股) |
| `fetch yield-curve` | 美债 | 3M/1Y/2Y/5Y/10Y/30Y，需 `FRED_API_KEY` |

### 实时行情 (`live`)

```bash
python -m src.cli.main live spot              # 全球快照
python -m src.cli.main live spot -m cn        # A股涨跌榜 (hk/us)
python -m src.cli.main live spot <TICKER>     # 个股实时行情
python -m src.cli.main live intraday <TICKER> [-i 5m]
```

### 分析

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
