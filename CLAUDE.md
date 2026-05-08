# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目

金融分析助手 — 多市场、多维度金融分析系统。详见 `docs/architecture.md`。

## 核心原则

**客观与主观严格分离。** `src/analysis/` 下只做确定性计算，策略偏好全部在 `config/` 中配置。

## 技术栈

Python 3.12+, Click + Rich (CLI), AKShare + yfinance + CNINFO (数据), ta (技术指标), MarkItDown (PDF转换), pandas/numpy/pyarrow

## Git提交要求

在 Git 提交前，检查这次修改是否需要更新文档、Skills等。同步更新提交。

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
docs/               # 文档
```

## CLI 命令

```bash
python -m src.cli.main ohlcv <TICKER>              # 拉取日线 OHLCV
python -m src.cli.main financials <TICKER>         # 财务数据
python -m src.cli.main reports <TICKER>            # 年报 PDF + MD
python -m src.cli.main analyze-stock <TICKER>      # 技术分析
python -m src.cli.main macro-check                 # 宏观评估
python -m src.cli.main index [CODE]               # 指数数据
python -m src.cli.main flow                    # 资金流向
python -m src.cli.main valuation <TICKER>          # 估值分析 (10方法)
python -m src.cli.main full-report <TICKER>        # 综合多维分析
python -m src.cli.main review <TICKER>             # 回顾历史判断
```

## Skills

- `/fetch-stock <TICKER>` — 数据抓取 (日线/财报/年报，可组合)
- `/analyze-stock <TICKER>` — 个股技术分析
- `/fetch-index [CODE]` — 指数数据抓取
- `/fetch-flow` — 资金流向数据
- `/macro-check` — 宏观环境评估
- `/valuation <TICKER>` — 基本面估值分析 (10种方法)
- `/full-report <TICKER>` — 综合多维分析报告
- `/review <TICKER>` — 回顾历史判断

## 已实现模块

| 层 | 模块 | 状态 |
|----|------|------|
| 数据 | AKShare (A股日线/指数/宏观/三张表 via 同花顺) | 可用 |
| 数据 | YFinance (全球股票/商品/外汇) | 可用 (受速率限制) |
| 数据 | CNINFO (年报PDF+MD) | 可用 |
| 数据 | Parquet 存储 + 增量获取 | 可用 |
| 分析 | 技术分析 | 可用 |
| 分析 | 宏观分析 | 可用 (中国数据) |
| 分析 | 基本面估值 (10方法) | 可用 |
| 分析 | 其余 7 模块 | 代码完成 |
| 集成 | 打分/聚合/报告 | 可用 |
| 跟踪 | 判断记录/回测 | 可用 (需积累数据) |

## 已知限制

- AKShare 被东方财富频繁限流，新 ticker 首次拉取可能失败
- 详细三张表使用同花顺接口 (stock_financial_*_ths)，已替代不稳定的东方财富接口
- CoinGecko/news provider 未实现
- 美股/港股/商品/外汇/加密数据未接入
- 商品/外汇/加密数据未接入
- yfinance 有速率限制
