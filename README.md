# 金融分析助手

多市场、多维度金融分析系统。覆盖 A 股 / 港股 / 美股 / 日股 / 英股 / 德股 / 法股，整合宏观、技术面、基本面、情绪、资金流向等维度，输出综合判断。

## 快速开始

```bash
pip install -e .
python -m src.cli.main --help
```

## Skills（22 个）

### 数据抓取

| Skill | 说明 |
|-------|------|
| `/fetch-all` | 一键拉取全部每日数据（指数/商品/汇率/加密货币/美债） |
| `/fetch-stock <TICKER> [ohlcv\|financials\|reports]` | 股票数据抓取（日线/财报/年报，可组合） |
| `/fetch-index [MARKET] [CODE]` | 全球指数日线（CN/US/HK/JP/UK/DE/FR） |
| `/fetch-commodity [CODE]` | 大宗商品期货（黄金/白银/原油/铜/天然气等 10 种） |
| `/fetch-forex [PAIR]` | 外汇汇率（USD/CNY, EUR/CNY, JPY/CNY 等 9 对） |
| `/fetch-crypto [SYMBOL]` | 加密货币（BTC, ETH, SOL 等） |
| `/fetch-flow` | 沪深港通资金流向（北向/南向） |
| `/fetch-yield-curve` | 美国国债收益率曲线（3M→30Y） |

### 实时行情

| Skill | 说明 |
|-------|------|
| `/spot` | 实时行情概览（全球指数/外汇/商品/加密货币）+ 涨跌榜 + 个股 |
| `/intraday <TICKER>` | 盘中分钟 K 线（1m/5m/15m/30m/60m），AKShare→yfinance 自动降级 |

### 分析

| Skill | 说明 |
|-------|------|
| `/analyze-stock <TICKER>` | 技术分析（趋势/动量/成交量/支撑阻力） |
| `/valuation <TICKER>` | 基本面估值（10 种方法：FCFF/FCFE/DDM/Graham/EPV/NCAV/RI/倍数/FCF质量/财务健康） |
| `/macro-check` | 宏观环境评估（CN 15+指标: CPI/PPI/PMI/GDP/M2/社融/LPR/进出口/就业/国债收益率 + US via FRED） |
| `/sentiment <TICKER>` | 新闻情绪分析（jieba 分词 + 金融情感词典） |
| `/report-analyze <TICKER>` | 年报文本分析（审计意见/指标提取/风险因素/管理层展望） |
| `/full-report <TICKER>` | 综合多维分析报告（10 维度加权评分） |
| `/review <TICKER>` | 回顾历史判断，对比实际走势 |
| `/correlation-check` | 跨市场联动分析（黄金/DXY/VIX → Risk-On/Risk-Off） |
| `/risk-check <TICKER>` | 风险评估（VaR/CVaR/最大回撤/波动率/流动性） |
| `/benchmark <TICKER>` | 基准对比（vs 基准指数 + 股债性价比） |
| `/scenario <TICKER>` | 情景分析（52周高低点 + 波动率敏感性区间） |
| `/market-scan` | 多市场扫描（全球资产 6维度涨跌幅 + 均线趋势） |

## CLI 命令（2 组 + 13 命令，共 24 个子命令）

### 数据抓取 (`fetch`)

```bash
python -m src.cli.main fetch ohlcv <TICKER> [--start DATE] [-i 5m]
python -m src.cli.main fetch index [MARKET] [CODE] [--spot]
python -m src.cli.main fetch commodity [CODE] [--spot]
python -m src.cli.main fetch forex [PAIR] [--spot]
python -m src.cli.main fetch crypto [SYMBOL] [--spot]
python -m src.cli.main fetch flow
python -m src.cli.main fetch yield-curve
python -m src.cli.main fetch financials <TICKER>
python -m src.cli.main fetch reports <TICKER>
```

### 实时行情 (`live`)

```bash
python -m src.cli.main live spot                     # 全球概览
python -m src.cli.main live spot -m cn               # 涨跌榜
python -m src.cli.main live spot <TICKER>            # 个股行情
python -m src.cli.main live intraday <TICKER> [-i 5m]
```

### 分析

```bash
python -m src.cli.main analyze-stock <TICKER>
python -m src.cli.main valuation <TICKER>
python -m src.cli.main macro-check
python -m src.cli.main sentiment <TICKER> [-d 7]
python -m src.cli.main report-analyze <TICKER>
python -m src.cli.main full-report <TICKER> [--context long_term|short_term] [--format brief|standard|full]
python -m src.cli.main review <TICKER>
python -m src.cli.main correlation-check
python -m src.cli.main risk-check <TICKER>
python -m src.cli.main benchmark <TICKER>
python -m src.cli.main scenario <TICKER>
python -m src.cli.main market-scan
```

### 工具

```bash
python -m src.cli.main summary                       # 每日数据更新汇总
```

## 数据架构

```
data/
├── stock/{market}/{CODE}_{NAME}/    # 个股：日线/财报/分红/年报/盘中K线/实时快照
├── index/{market}/{CODE}/           # 全球指数
├── commodity/global/{CODE}/         # 大宗商品
├── forex/global/{PAIR}/             # 外汇
├── crypto/global/{SYMBOL}/          # 加密货币
├── macro/{cn,us}/{indicator}/       # 宏观经济
├── flow/{market}/{channel}/         # 资金流向
└── news/{market}/{CODE}/            # 新闻数据
```

详见 `docs/data-structure.md`。

## 技术栈

Python 3.12+ / Click + Rich (CLI) / AKShare + yfinance + CoinGecko + FRED + CNINFO (数据) / ta (技术指标) / jieba (中文分词) / MarkItDown (PDF转换) / pandas + pyarrow (存储)

## 文档

- `docs/architecture.md` — 系统架构与实施计划
- `docs/data-structure.md` — 数据持久化目录结构
- `.claude/skills/` — Skills 定义文件
