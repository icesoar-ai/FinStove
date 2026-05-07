# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目

金融分析助手 — 多市场、多维度金融分析系统。详见 `docs/architecture.md`。

## 核心原则

**客观与主观严格分离。** `src/analysis/` 下只做确定性计算，策略偏好全部在 `config/` 中配置。

## 技术栈

Python 3.12+, Click + Rich (CLI), AKShare + yfinance + FRED (数据), ta (技术指标), pandas/numpy

## 项目结构

```
src/data/           # 数据层 (providers → cache → normalizer → registry)
src/analysis/       # 分析模块 (11个维度)
  fundamental/      # 估值子模块 (10个方法 + 聚合器)
src/integration/    # 集成层 (scorer → aggregator → report)
src/track/          # 判断跟踪 (record → review → stats)
src/cli/            # CLI 入口 (Click)
config/             # 配置文件 (主观策略层)
data/               # 原始数据存储 (Parquet)
.claude/skills/     # Claude Code Skills
docs/               # 文档
```

## CLI 命令

```bash
python -m src.cli.main fetch <TICKER>              # 拉取 OHLCV
python -m src.cli.main analyze-stock <TICKER>      # 技术分析
python -m src.cli.main macro-check                 # 宏观评估
python -m src.cli.main full-report <TICKER>        # 综合多维分析
python -m src.cli.main review <TICKER>             # 回顾历史判断
```

## Skills

- `/analyze-stock <TICKER>` — 个股技术分析
- `/macro-check` — 宏观环境评估
- `/full-report <TICKER>` — 综合多维分析报告
- `/review <TICKER>` — 回顾历史判断

## 已实现的分析模块

| 模块 | 文件 | 状态 |
|------|------|------|
| 技术分析 | `src/analysis/technical.py` | 可用 |
| 宏观分析 | `src/analysis/macro.py` | 可用 (CN数据) |
| 基本面估值 | `src/analysis/fundamental/` | 代码完成，等AKShare财报接口修复 |
| 资金流向 | `src/analysis/capital_flow.py` | 代码完成 |
| 情绪分析 | `src/analysis/sentiment.py` | 代码完成 |
| 政策分析 | `src/analysis/policy.py` | 代码完成 |
| 跨市场联动 | `src/analysis/correlation.py` | 代码完成 |
| 风险评估 | `src/analysis/risk.py` | 代码完成 |
| 基准对比 | `src/analysis/benchmark.py` | 代码完成 |
| 情景分析 | `src/analysis/scenario.py` | 代码完成 |

## 已知限制

- AKShare 财报接口 (stock_*_by_report_em) 当前不可用，东方财富网站改版导致
- yfinance 有速率限制
- FRED provider 未实现
- 美股宏观数据不完整
