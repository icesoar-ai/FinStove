# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目

金融分析助手 — 多市场、多维度金融分析系统。

## 文档索引

| 文档 | 内容 |
|------|------|
| `docs/architecture.md` | 架构总览、分层设计、分析模块、估值方法、**全部已知限制与待完善项** |
| `docs/capabilities.md` | Skills + CLI 命令完整参考 |
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
src/data/           # 数据层 (gateway 统一读写 Parquet → providers 纯抓取 → cache 去重)
src/analysis/       # 分析模块 (11个维度)
  fundamental/      # 估值子模块 (10个方法 + 聚合器)
src/integration/    # 集成层 (scorer → aggregator → report)
src/track/          # 判断跟踪 (record → review → stats)
src/cli/            # CLI 入口 (Click)
config/             # 配置文件 (主观策略层)
data/               # 原始数据 (Parquet, PDF, MD) — gitignored
tests/              # 单测 — 分析/工具/数据/CLI
.claude/skills/     # Claude Code Skills
docs/               # 详见文档索引
```

## CLI 命令 → 详见 `docs/capabilities.md`

## 使用引导

当用户问"怎么用""有哪些使用方法""能做什么""怎么抓数据""能做哪些分析"等用法问题时，直接展示 README.md 的"使用方法"章节。

## Skills → 详见 `.claude/skills/` 目录

## 已知限制

详见 `docs/architecture.md`。关键操作要点：

- AKShare 限流 → DataGateway 自动降级 (AKShare→yfinance→Baostock)
- yfinance 批量拉取有限速，多品种需加间隔
- FRED 需 `FRED_API_KEY` 环境变量（在 `.env` 中设置，Gateway 自动加载）
