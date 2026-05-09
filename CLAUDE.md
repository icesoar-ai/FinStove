# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目

金融分析助手 — 多市场、多维度金融分析系统。详见 `docs/architecture.md`。

## 核心原则

**客观与主观严格分离。** `src/analysis/` 下只做确定性计算，策略偏好全部在 `config/` 中配置。

## 技术栈

Python 3.12+, Click + Rich (CLI), AKShare + yfinance + CNINFO (数据), ta (技术指标), MarkItDown (PDF转换), pandas/numpy/pyarrow

## 技术要求

1. 在 Git 提交前，检查这次修改是否需要更新文档、Skills等。同步更新提交。
2. 抓取数据要支持持久化，存到数据目录下。

## 项目结构

```
src/data/           # 数据层 (providers: akshare/yfinance/cninfo → cache → storage → registry)
src/analysis/       # 分析模块 (11个维度)
  fundamental/      # 估值子模块 (10个方法 + 聚合器)
src/integration/    # 集成层 (scorer → aggregator → report)
src/track/          # 判断跟踪 (record → review → stats)
src/cli/            # CLI 入口 (Click)
config/             # 配置文件 (主观策略层)
data/               # 原始数据 (Parquet, PDF, MD) — gitignored
.claude/skills/     # Claude Code Skills
docs/               # 文档 (architecture.md, data-structure.md)
```

## CLI 命令

```bash
python -m src.cli.main spot                        # 实时行情概览
python -m src.cli.main spot -m cn [hk] [us]       # 涨跌榜
python -m src.cli.main spot <TICKER>               # 个股实时行情
python -m src.cli.main intraday <TICKER> [-i 5m]   # 盘中分钟K线
python -m src.cli.main sentiment <TICKER> [-d DAYS] # 新闻情绪分析
python -m src.cli.main report-analyze <TICKER>      # 年报文本分析
python -m src.cli.main ohlcv <TICKER> [--intraday] # 拉取日线 OHLCV
python -m src.cli.main financials <TICKER>         # 财务数据
python -m src.cli.main reports <TICKER>            # 年报 PDF + MD
python -m src.cli.main analyze-stock <TICKER>      # 技术分析
python -m src.cli.main macro-check                 # 宏观评估 (CN 15+指标 + US via FRED)
python -m src.cli.main index [MARKET] [CODE]       # 全球指数 (cn/us/hk/jp/uk/de/fr)
python -m src.cli.main commodity [CODE]            # 大宗商品 (黄金/原油/铜/天然气)
python -m src.cli.main forex [PAIR]                # 外汇汇率
python -m src.cli.main crypto [SYMBOL]             # 加密货币
python -m src.cli.main yield-curve                 # 美债收益率曲线
python -m src.cli.main flow                        # 资金流向
python -m src.cli.main valuation <TICKER>          # 估值分析 (10方法)
python -m src.cli.main full-report <TICKER>        # 综合多维分析
python -m src.cli.main review <TICKER>             # 回顾历史判断
```

## Skills

- `/fetch-all` — 一键拉取全部每日数据（指数/商品/汇率/加密货币/美债）
- `/fetch-stock <TICKER>` — 数据抓取 (日线/财报/年报，可组合)
- `/analyze-stock <TICKER>` — 个股技术分析
- `/fetch-index [MARKET] [CODE]` — 全球指数数据抓取 (CN/US/HK/JP/UK/DE/FR)
- `/fetch-commodity [CODE]` — 大宗商品期货
- `/fetch-forex [PAIR]` — 外汇汇率
- `/fetch-crypto [SYMBOL]` — 加密货币
- `/fetch-flow` — 资金流向数据
- `/fetch-yield-curve` — 美债收益率曲线
- `/macro-check` — 宏观环境评估 (CN CPI/PPI/PMI/GDP/M2/社融/LPR/进出口/就业/国债收益率 + US via FRED)
- `/valuation <TICKER>` — 基本面估值分析 (10种方法)
- `/full-report <TICKER>` — 综合多维分析报告
- `/spot` — 实时行情查询（全球指数/外汇/商品/加密货币/A股/港股/美股）
- `/spot` — 实时行情（全球指数/外汇/商品/加密货币/个股）
- `/intraday <TICKER>` — 盘中分钟K线（自动切换AKShare/yfinance）
- `/sentiment <TICKER>` — 新闻情绪分析（jieba分词+情感词典）
- `/report-analyze <TICKER>` — 年报文本分析（审计意见/风险/展望）
- `/review <TICKER>` — 回顾历史判断

## 已实现模块

| 层 | 模块 | 状态 |
|----|------|------|
| 数据 | AKShare (A股日线/指数/15+宏观指标/三张表 via 同花顺) | 可用 |
| 数据 | YFinance (全球股票/商品/外汇/指数/加密货币) | 可用 (受速率限制) |
| 数据 | CNINFO (年报PDF+MD) | 可用 |
| 数据 | 实时行情 (YFinance 概览 + AKShare 个股) | 可用 |
| 数据 | 盘中分钟K线 (AKShare → yfinance 自动降级) | 可用 |
| 数据 | 新闻抓取 (AKShare 东方财富 + CCTV) | 可用 |
| 数据 | Parquet 存储 + 增量获取 | 可用 |
| 分析 | 新闻 NLP 情绪 (jieba + 金融情感词典) | 可用 |
| 分析 | 年报文本分析 (审计意见/指标提取/风险/展望) | 可用 |
| 分析 | 技术分析 | 可用 |
| 分析 | 宏观分析 | 可用 (CN 15+指标 + US FRED) |
| 分析 | 基本面估值 (10方法) | 可用 |
| 分析 | 其余 7 模块 | 代码完成 |
| 集成 | 打分/聚合/报告 | 可用 |
| 跟踪 | 判断记录/回测 | 可用 (需积累数据) |

## 已知限制

- AKShare 被东方财富频繁限流，新 ticker 首次拉取可能失败
- 详细三张表使用同花顺接口 (stock_financial_*_ths)，已替代不稳定的东方财富接口
- 新闻抓取使用 AKShare 东方财富 + CCTV，未实现 RSS 源
- yfinance 批量拉取有限速，多品种间需加间隔
- FRED 需要环境变量 `FRED_API_KEY`（免费申请）
- 商品期货数据来自连续主力合约 (`GC=F`)，非现货价格
- CNY 相关汇率对历史数据可能较短
