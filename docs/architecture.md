# 金融分析助手 - 架构

## Context

构建一套 Python 金融分析系统，覆盖 A股/港股/美股/日股/英股/德股/法股、美债/中债、汇率、黄金/白银/大宗商品/石油、比特币、美元指数。从宏观、资金流向、技术面、基本面、情绪、政策、跨市场联动七个维度分析，最终汇总为综合判断（内在价值、价格合理性、走势预测）。

全部使用免费数据源（AKShare, yfinance, FRED, CoinGecko），Python 技术栈，以 Claude Code Skills 形式交互。

## 关键提醒

**数据陷阱：**
- 免费数据存在**幸存者偏差**（退市公司消失），回测结果偏乐观。需从指数成分股变更记录反向查
- **前视偏差**：财报发布日期 != 报告期截止日，必须区分"数据发生时点"和"数据可知时点"
- **复权错误**：yfinance 默认复权偶尔有错，AKShare 需手动指定复权因子
- A股财报**审计质量参差**：非标意见、突然大额减值、收入确认激进——结构化的三张表看不出这些问题，必须读财报原文

**各市场定价逻辑差异巨大：**

| | A股 | 美股 | 港股 |
|---|---|---|---|
| 核心驱动力 | 政策 + 流动性 | 盈利增长 | 全球资金流向 |
| PE锚 | 波动极大（20-80倍常见） | 相对稳定 | 流动性折价 |
| 散户占比 | ~60% | ~10% | ~20% |
| 风险溢价来源 | 政策风险 > 经营风险 | 利率 > 其他 | 地缘 + 汇率 > 经营 |

不同市场用不同估值标准，"合理"在不同市场土壤里含义不同。DCF 算出的目标价在 A 股情绪溢价下可能常年偏离。

## 架构概览

```
用户 /analyze-stock 600519.SH
  → Claude Code Skill (.claude/skills/analyze-stock.md)
    → python -m src.cli.main analyze-stock 600519.SH
      → Data Layer (providers → cache → normalizer)
      → Analysis Layer (7 modules, 并行)
      → Integration Layer (scorer → aggregator → report)
    → Markdown 报告输出到终端
  → Claude 展示 + 解读 + 追问
```

## 核心原则

**客观与主观严格分离。** `src/analysis/` 下的分析模块只做确定性计算（估值公式、指标计算、数据标准化），不含可调权重或策略偏好。主观策略（权重配置、场景选择、解读框架）全部放在 `config/scoring.yaml` 和 `config/settings.yaml`，修改观点只需改配置，不动分析代码。

```
客观层 (src/analysis/)          主观层 (config/)
├── fcff.py         ──┐         scoring.yaml     ← 维度权重、场景选择
├── dcf.py          ──┤         settings.yaml    ← 模型参数、阈值
├── technical.py    ──┤         
├── macro.py        ──┤         不可变的          可随认知调整的
├── sentiment.py    ──┤         确定性计算        策略配置
├── ...             ──┘
```

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
docs/               # 文档
```

## 分层设计

### Data Layer (`src/data/`)

DataGateway (`gateway.py`) 为 CLI 唯一入口，持有 8 个 Provider，内置 A股三级降级链 (AKShare → yfinance → Baostock)，统一 Parquet/SQLite 读写路径，聚合宏观数据。

存储方案：Parquet（原始数据）+ SQLite（API 请求缓存）两层架构。Parquet 是真正的数据源，SQLite 只是 API 去重缓存。

详见：`docs/data-flow.md`（数据流与 Provider 详情）、`docs/data-structure.md`（存储目录结构）。

### Analysis Layer (`src/analysis/`)

每个模块继承 AbstractAnalyzer，输入 AnalysisContext，输出 AnalysisResult (score: -2~+2, confidence, signals, summary):

| 模块 | 功能 | 数据源 |
|------|------|--------|
| macro | 利率/收益率曲线/CPI/PPI/PMI(官方+财新+非制造业)/GDP/DXY/M2/社融/进出口/就业/工业 | FRED + AKShare |
| capital_flow | 沪深港通/机构/板块轮动/跨资产 | AKShare + yfinance |
| technical | 多时间框架(日/周/月)趋势/动量/成交量/支撑阻力/形态 | yfinance/AKShare OHLCV |
| fundamental | 多方法估值(FCFF/FCFE/DDM/Graham/EPV等) + 财务健康/盈利质量 | AKShare 财报 + yfinance |
| risk | 尾部风险/集中度/相关性崩盘/流动性/最大回撤 | yfinance + FRED |
| benchmark | 行业排名/指数超额收益(β vs α)/无风险资产对比 | yfinance + AKShare |
| scenario | 乐观/中性/悲观目标价区间 + 压力测试 | 依赖其他模块输出 |
| sentiment | 新闻NLP/恐惧贪婪/VIX/论坛情绪 | jieba + VADER |
| policy | 央行方向/财政/监管/地缘(基于关键词规则) | 新闻 + FRED |
| correlation | 商品-货币/债券-股票/避险流/risk-on-off | yfinance + FRED |
| report_text | 年报文本分析 (审计意见/指标提取/风险/展望) | CNINFO + SEC EDGAR |

### Fundamental Analysis 子模块 (`src/analysis/fundamental/`)

每个方法实现 `ValuationMethod` ABC，输出 `ValuationResult`，聚合器汇总取中位数/加权平均并做一致性判断。

| 分类 | 方法 | 说明 |
|------|------|------|
| DCF | FCFF | 企业自由现金流折现，WACC 折现率 |
| DCF | FCFE | 股权自由现金流折现，COE 折现率 |
| 股利 | DDM | Gordon Growth + 多阶段 |
| 价值 | Graham Number + Graham Formula | √(22.5×EPS×BVPS) / V=EPS×(8.5+2g)×4.4/Y |
| 资产 | EPV | Greenwald 盈利能量价值 |
| 资产 | NCAV / Net-Net | Graham 清算价值 |
| 剩余收益 | Residual Income | Ohlson 模型 |
| 相对 | PE/PB/PS/EV_EBITDA/PEG/FCF_Yield | 当前 vs 历史分位 |
| 质量 | FCF Quality | FCF Yield, FCF Margin, FCF Conversion |
| 健康 | Altman Z + DuPont | 财务风险评分 |

### Risk Analysis (`src/analysis/risk.py`)

| 风险维度 | 指标 |
|---------|------|
| 尾部风险 | 历史 VaR / CVaR |
| 集中度风险 | HHI 指数 |
| 相关性崩盘 | 相关矩阵 + 压力测试 |
| 流动性风险 | Amihud 非流动性指标 |
| 波动率 | 历史波动率 + GARCH |
| 最大回撤 | Max Drawdown |

### Benchmark Comparison (`src/analysis/benchmark.py`)

| 对比维度 | 说明 |
|---------|------|
| 行业排名 | PE/ROE/FCF Margin/ROIC 同行业分位数 |
| 超额收益归因 | β（市场暴露） vs α（选股能力）|
| 无风险对比 | vs 国债的超额收益与风险 |
| 同类替代 | vs 同行业 ETF |

### Scenario Analysis (`src/analysis/scenario.py`)

| 情景 | 方法 |
|------|------|
| 乐观/中性/悲观 | 关键假设变量 ±σ，三档目标价区间 |
| 压力测试 | 历史极端事件重现 |
| 敏感性 | "如果...会怎样" 泰勒展开 |
| 反转情景 | 最拥挤方向的反转演练 |

### Judgment Tracking (`src/track/`)

每次分析结果持久化，定期回溯对错，形成反馈闭环。胜率统计按维度拆开，暴露每个维度的信息价值。

### Integration Layer (`src/integration/`)

- **Scorer**: 加权打分，权重按场景(`scoring.yaml`)
- **Aggregator**: 汇总内在价值判断、价格合理性、趋势预测、风险因素
- **Report**: Jinja2 模板 → markdown，三档 (brief/standard/full)

## CLI 与 Skills

CLI 命令与环境变量方法详见 `docs/capabilities.md`。Skills 详见 CLAUDE.md。

## 关键依赖

```
akshare (CN数据), yfinance (全球), fredapi (US宏观, 需免费key), pycoingecko (加密)
pandas, numpy, pydantic
ta (纯Python技术指标, 非TA-Lib)
jieba (中文分词), nltk/VADER (英文情绪)
typer, rich, PyYAML, jinja2
diskcache (SQLite缓存)
```

---

## 已知限制与待完善

### 数据源

| 数据源 | 限制 |
|--------|------|
| AKShare | 东方财富频繁限流；接口偶尔变更；无港股/美股财报、ETF、可转债 |
| YFinance | 批量请求极快触发 Rate Limit；默认复权偶尔出错；部分品种历史短 (CNY外汇对)；A股/港股延迟 15 分钟 |
| FRED | 需 `FRED_API_KEY` 环境变量；仅美国，无中国/欧洲宏观 |
| CoinGecko | 免费版速率限制严格 (~10-30次/分钟)；历史数据精度不如交易所 API |
| Baostock | 仅 A 股日线，无财务/指数/汇率数据，精度和时效性略低 |
| CNINFO | 仅 A 股年报，缺半年报/季报 |
| SEC EDGAR | 仅支持 10-K 年报，无 10-Q 季报；下载速度慢 |
| News | 仅 CN 新闻 (东方财富 + CCTV)，无 US/HK 源 |

### 功能覆盖

| 类别 | 现状 | 缺失 |
|------|------|------|
| A股财报 | 年报 + 三张表完整 | 缺半年报/季报 |
| 美股财报 | 10-K 年报 + yfinance 三张表 | 缺 10-Q 季报 |
| 港股 | 日线可用 | 缺财报/年报 |
| ETF | 不支持 | 无 ETF 数据 |
| 可转债 | 不支持 | 无可转债数据 |

### 数据质量

| 问题 | 状态 |
|------|------|
| A股幸存者偏差 (退市股) | 未处理 |
| 前视偏差 (财报发布日期 vs 截止日) | 未检测 |
| 复权数据校验 | 未实现 |
| API 限速自动退避/重试 | 无机制 |
| 分析模块并行化 | 未实现 |

### 输出

| 现状 | 缺失 |
|------|------|
| 终端 Rich | 无 JSON 导出 |
| 无 Dashboard | Streamlit demo 骨架存在，需求待细化 |
