# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目

金融分析助手 — 多市场、多维度金融分析系统。

## 文档索引

| 文档 | 内容 |
|------|------|
| `docs/architecture.md` | 架构总览、分层设计、分析模块、估值方法、**全部已知限制与待完善项** |
| `docs/capabilities.md` | CLI 命令参考 (fetch/live/分析共 24 个命令) |
| `docs/data-flow.md` | 数据流架构、8 个 Provider 详情与接口清单、各自的限制 |
| `docs/data-structure.md` | Parquet 存储目录结构、命名规则、品种码表 |

## 核心原则

**客观与主观严格分离。** `src/analysis/` 下只做确定性计算，策略偏好全部在 `config/` 中配置。

## 技术栈

Python 3.12+, Click + Rich (CLI), AKShare + yfinance + CNINFO (数据), ta (技术指标), MarkItDown (PDF转换), pandas/numpy/pyarrow

## 技术要求

1. 在 Git 提交前，检查这次修改是否需要更新文档、Skills等。同步更新提交。
2. 抓取数据要支持持久化，存到数据目录下。

## 项目结构

```
src/data/           # 数据层 (gateway → providers: akshare/yfinance/cninfo/fred/coingecko/news → cache → parquet)
src/analysis/       # 分析模块 (11个维度)
  fundamental/      # 估值子模块 (10个方法 + 聚合器)
src/integration/    # 集成层 (scorer → aggregator → report)
src/track/          # 判断跟踪 (record → review → stats)
src/cli/            # CLI 入口 (Click)
config/             # 配置文件 (主观策略层)
data/               # 原始数据 (Parquet, PDF, MD) — gitignored
.claude/skills/     # Claude Code Skills
docs/               # 架构/功能/数据流/存储结构
```

## CLI 命令

```bash
# 数据抓取 (fetch)
python -m src.cli.main fetch ohlcv <TICKER> [--intraday]
python -m src.cli.main fetch index [MARKET] [CODE]
python -m src.cli.main fetch commodity [CODE]
python -m src.cli.main fetch forex [PAIR]
python -m src.cli.main fetch crypto [SYMBOL]
python -m src.cli.main fetch flow
python -m src.cli.main fetch yield-curve
python -m src.cli.main fetch financials <TICKER>
python -m src.cli.main fetch reports <TICKER>

# 实时行情 (live)
python -m src.cli.main live spot                        # 实时行情概览
python -m src.cli.main live spot -m cn [hk] [us]       # 涨跌榜
python -m src.cli.main live spot <TICKER>               # 个股实时行情
python -m src.cli.main live intraday <TICKER> [-i 5m]   # 盘中分钟K线

# 分析
python -m src.cli.main analyze-stock <TICKER>      # 技术分析
python -m src.cli.main macro-check                 # 宏观评估 (CN 15+指标 + US via FRED)
python -m src.cli.main valuation <TICKER>          # 估值分析 (10方法)
python -m src.cli.main full-report <TICKER>        # 综合多维分析
python -m src.cli.main sentiment <TICKER> [-d DAYS] # 新闻情绪分析
python -m src.cli.main report-analyze <TICKER>      # 年报文本分析
python -m src.cli.main correlation-check           # 跨市场联动 (黄金/DXY/VIX)
python -m src.cli.main risk-check <TICKER>         # 风险评估 (VaR/回撤/波动率)
python -m src.cli.main benchmark <TICKER>          # 基准对比 (vs 指数)
python -m src.cli.main scenario <TICKER>           # 情景分析 (乐观/悲观/敏感性)

# 工具
python -m src.cli.main review <TICKER>             # 回顾历史判断
python -m src.cli.main market-scan                 # 多市场扫描
python -m src.cli.main summary                     # 每日数据更新汇总
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
- `/correlation-check` — 跨市场联动分析 (黄金/DXY/VIX → Risk-On/Risk-Off)
- `/risk-check <TICKER>` — 风险评估 (VaR/CVaR/最大回撤/波动率/流动性)
- `/benchmark <TICKER>` — 基准对比 (vs 基准指数 + 股债性价比)
- `/scenario <TICKER>` — 情景分析 (52周高低点 + 波动率敏感性区间)
- `/market-scan` — 多市场扫描 (全球资产 1日/5日/1月/3月/6月 涨跌幅 + 均线趋势)

## 已知限制

详见 `docs/architecture.md`。关键操作要点：

- AKShare 限流 → DataGateway 自动降级 (AKShare→yfinance→Baostock)
- yfinance 批量拉取有限速，多品种需加间隔
- FRED 需 `FRED_API_KEY` 环境变量
