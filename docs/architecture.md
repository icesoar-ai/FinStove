# 金融分析助手 - 架构与实施计划

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

## 分层设计

### Data Layer (`src/data/`)

**Provider 协议**: 按能力拆分为 StockProvider, MacroProvider, FlowProvider 等 Protocol，组合优于继承
**ProviderRegistry**: `(Market, AssetType) → Provider` 路由表，读 `config/providers.yaml`
**标准化**: 所有数据通过 Pydantic models (OHLCVRow, MacroPoint, FlowData) 和 normalizer 统一
**适配器**: akshare(CN), yfinance(global), fred(US macro), coingecko(crypto), news(RSS+爬虫)

**存储方案：Parquet（原始数据）+ SQLite（API 请求缓存）两层架构**

Parquet 是真正的数据源（`src/data/storage.py`），SQLite 只是 API 去重缓存（`src/data/cache.py`）。

**Parquet 存储路径规则：**

```
data/{asset_type}/{market}/{symbol}/{data_type}.parquet
```

| asset_type | market | symbol 示例 | data_type |
|-----------|--------|-----------|-----------|
| stock | cn | 600795_国电电力 | daily, balance_sheet, income, cashflow, financials |
| stock | us | AAPL | daily, balance_sheet, income, cashflow |
| stock | hk | 00700 | daily, balance_sheet, income, cashflow |
| index | cn | 000001 | daily |
| macro | cn | cpi, pmi, shibor | daily, monthly |
| flow | cn | northbound, southbound | daily |
| commodity | global | gold, oil | daily |
| forex | global | dxy | daily |
| crypto | global | btc | daily |

- **symbol 格式**：`{code}_{name}`，如 `600795_国电电力`。股票名称从 `data/stock_names.json` 缓存获取，未命中时调用 AKShare API 查询并缓存。
- **PDF/MD 报告**：`data/stock/cn/{code}_{name}/reports/{year} 年年度报告.md/.pdf`

**数据获取流程：**

```
请求 fetch 600519.SH
        │
        ▼
  Parquet 有数据？
   ┌─────┴─────┐
  是           否
   │            │
   ▼            ▼
查到最新日期   全量请求 API
   │            │
   │            ▼
   │        _cached() 先查 SQLite
   │         ┌──命中：直接返回
   │         └──未命中：调 AKShare API
   │                    │
   ▼                    ▼
只请求 [last+1, today]  合并去重 → 写 Parquet + 写 SQLite
   │
   ▼
合并新数据 → 写回 Parquet
返回合并后的完整数据
```

**三种缓存状态下的行为：**

| Parquet | SQLite | 行为 |
|---------|--------|------|
| 有，到昨天 | 有 | 只拉 1 天 → 合并写 Parquet (几乎无 API 调用) |
| 有，到昨天 | 空 (被清) | 只拉昨天到今天 ≈2天 → 写 Parquet + 重建缓存 |
| 无 | 无 | 全量拉取 → 写 Parquet + 缓存 |

SQLite 丢了不影响数据完整性，只会多一两次 API 请求。

```
data/                          # Parquet 原始数据
├── stock/
│   ├── cn/600519/
│   │   ├── daily.parquet      # 日线 OHLCV
│   │   ├── financials.parquet # 财报（资产负债表/利润/现金流）
│   │   └── info.json          # 公司概况
│   ├── us/AAPL/
│   └── hk/00700/
├── index/cn/000001/daily.parquet
├── macro/cn/{cpi,pmi,shibor}/
│   └── daily.parquet
├── flow/cn/{northbound,southbound}.parquet
├── commodity/{gold,oil}.parquet
├── forex/dxy.parquet
└── crypto/btc.parquet

~/.cache/stocks/cache.db       # SQLite API 请求缓存 (diskcache)
~/.cache/stocks/tracking/      # 判断跟踪记录 (JSON)
```

### Analysis Layer (`src/analysis/`)
每个模块继承 AbstractAnalyzer，输入 AnalysisContext，输出 AnalysisResult (score: -2~+2, confidence, signals, summary):

| 模块 | 功能 | 免费数据源 |
|------|------|-----------|
| macro | 利率/收益率曲线/CPI/PMI/GDP/DXY | FRED + AKShare |
| capital_flow | 沪深港通/机构/板块轮动/跨资产 | AKShare + yfinance |
| technical | 多时间框架(日/周/月)趋势/动量/成交量/支撑阻力/形态 | yfinance/AKShare OHLCV |
| fundamental | 多方法估值(FCFF/FCFE/DDM/Graham/EPV等) + 财务健康/盈利质量 | AKShare 财报 + yfinance |
| risk | 尾部风险/集中度/相关性崩盘/流动性/最大回撤 | yfinance + FRED |
| benchmark | 行业排名/指数超额收益(β vs α)/无风险资产对比 | yfinance + AKShare |
| scenario | 乐观/中性/悲观目标价区间 + 压力测试 | 依赖其他模块输出 |
| sentiment | 新闻NLP/恐惧贪婪/VIX/论坛情绪 | RSS + jieba + VADER |
| policy | 央行方向/财政/监管/地缘(基于关键词规则) | 新闻 + FRED |
| correlation | 商品-货币/债券-股票/避险流/risk-on-off | yfinance + FRED |

### Fundamental Analysis 子模块 (`src/analysis/fundamental/`)

基本面的核心是估值。每个方法实现一个 `ValuationMethod` ABC，输出标准化的 `ValuationResult(value_range_low, value_range_high, fair_value, confidence, assumptions)`，此聚合器汇总所有方法取中位数/加权平均并做一致性判断。

```
src/analysis/fundamental/
├── __init__.py           # 调度器，跑全部估值方法
├── base.py               # ValuationMethod ABC, ValuationResult
├── fcff.py               # FCFF: 企业自由现金流折现，折现率 WACC，得企业价值减净负债
├── fcfe.py               # FCFE: 股权自由现金流折现，折现率 COE，直接得股权价值
├── ddm.py                # 股利折现: Gordon Growth + 多阶段 DDM
├── graham.py             # Graham Number + Graham Revised Formula
├── epv.py                # EPV (Greenwald): 可持续盈利折现 + 冗余资产
├── ncav.py               # Net-Net / NCAV: 流动资产 - 总负债，Graham 清算法
├── residual_income.py    # 剩余收益模型 (Ohlson): BV + ∑(RI/(1+r)^t)
├── multiples.py          # 相对估值: PE/PB/PS/EV_EBITDA/PEG/FCF_Yield/EV_FCF 分位 vs 历史 vs 行业
├── fcf_quality.py        # FCF 质量: FCF Yield, FCF Margin, FCF Conversion (FCF/NP), EV/FCF
├── health.py             # 财务健康: Altman Z, 流动/速动比率, 负债率趋势, ROE DuPont
└── aggregator.py         # 多方法汇总: 中位数、加权平均、一致性（方法间分歧大 → warning）
```

**覆盖的估值方法清单：**

| 分类 | 方法 | 说明 |
|------|------|------|
| DCF | **FCFF** | 企业自由现金流折现，WACC 折现率 |
| DCF | **FCFE** | 股权自由现金流折现，COE 折现率 |
| DCF | **Monte Carlo DCF** | 对关键假设做概率分布采样（Phase 5） |
| 股利 | **DDM** | Gordon Growth + 多阶段 |
| 价值 | **Graham Number** | √(22.5 × EPS × BVPS) |
| 价值 | **Graham Formula** | V = EPS × (8.5 + 2g) × 4.4/Y |
| 资产 | **EPV** | Greenwald 盈利能量价值 |
| 资产 | **NCAV / Net-Net** | Graham 清算价值 |
| 剩余 | **Residual Income** | Ohlson 模型 |
| 相对 | **PE/PB/PS 分位** | 当前 vs 历史 vs 行业 |
| 相对 | **EV/EBITDA** | 跨资本结构可比 |
| 相对 | **PEG** | 成长性调整 PE |
| 相对 | **FCF Yield / EV/FCF** | 更干净的现金流倍数 |
| 质量 | **FCF Margin / Conversion** | 盈利质量辅助 |
| 健康 | **Altman Z / DuPont** | 财务风险评分 |

### Risk Analysis (`src/analysis/risk.py`)

不只判断"会不会涨"，还要量化"可能跌多少"：

| 风险维度 | 指标 | 计算方式 |
|---------|------|---------|
| **尾部风险** | 历史 VaR / CVaR | 在类似宏观+技术条件下，最差 5%/1% 情景的回撤 |
| **集中度风险** | HHI 指数 | 持仓的行业/因子/市值暴露集中度 |
| **相关性崩盘** | 相关矩阵 + 压力测试 | 熊市里资产相关性趋近于 1，分散失效 |
| **流动性风险** | Amihud 非流动性指标 | 成交额弹性，跌停板概率（A股特有） |
| **波动率曲面** | 历史波动率 + GARCH | 波动率聚集效应 |
| **最大回撤** | Max Drawdown | 历史上类似条件下多深多长 |

### Benchmark Comparison (`src/analysis/benchmark.py`)

分析报告不为孤立的"好"做背书，必须可比较：

| 对比维度 | 说明 |
|---------|------|
| **行业排名** | PE/ROE/FCF Margin/ROIC 在同行业 GICS 分类中的分位数 |
| **指数超额收益归因** | 相对于沪深300/标普500，超额来源是 β（市场暴露）还是 α（选股能力） |
| **无风险资产对比** | 相对于持有国债（如中国 10 年期 ~2.5%、美国 ~4%），多获了多少超额收益，多承担了多少风险 |
| **同类替代** | 如果买同行业的 ETF（费用率更低、分散更好），是否更优 |

### Scenario Analysis (`src/analysis/scenario.py`)

单点目标价是幻觉，区间判断才是诚实分析：

| 情景 | 方法 | 输出 |
|------|------|------|
| **乐观/中性/悲观** | 关键假设变量（收入增速 ±σ、折现率 ±σ、PE 终值敏感度） | 三档目标价区间 |
| **压力测试** | 历史极端事件重现（2008 金融危机、2015 A股股灾、2020 新冠） | 最大回撤估计、恢复期预估 |
| **泰勒展开** | 每个分析维度的"如果...会怎样"：利率上调 1% → 目标价下降 x% | 敏感性表格 |
| **反转情景** | 当前最拥挤的做多/做空方向的反转演练 | 反向风险提示 |

### Judgment Tracking (`src/track/`)

系统每次输出的判断持久化，定期回溯对错，形成反馈闭环：

```
src/track/
├── __init__.py
├── record.py           # 每次分析结果入库
├── review.py           # 定期回测：N 天/周/月后看结果
├── stats.py            # 统计：胜率、偏差度、马后炮检测
└── models.py           # TrackRecord, ReviewResult
```

- 每次 `/analyze-stock` 或 `/full-report` 自动存一条记录
- 定期回测命令 `stocks-cli review <TICKER>` 对比历史判断和实际走势
- 胜率统计按维度拆开（技术面胜率？基本面胜率？），暴露每个维度的信息价值

### Integration Layer (`src/integration/`)
- **Scorer**: 加权打分，权重按场景(`scoring.yaml`)：长期投资(基本面0.4+宏观0.2)、短期交易(技术0.35+资金0.25)、宏观评估
- **Aggregator**: 汇总内在价值判断、价格合理性、趋势预测、风险因素
- **Report**: Jinja2 模板 → markdown，三档(brief ~20行/standard ~60行/full ~200行)

### CLI (`src/cli/`)
Click + Rich:
- `stocks-cli market-scan` — 多市场概览
- `stocks-cli analyze-stock <TICKER>` — 个股深度
- `stocks-cli macro-check` — 宏观环境
- `stocks-cli capital-flow` — 资金流向
- `stocks-cli sentiment-check` — 情绪检测
- `stocks-cli correlation-check` — 跨市场联动
- `stocks-cli risk-check <TICKER>` — 风险评估
- `stocks-cli benchmark <TICKER>` — 基准对比
- `stocks-cli scenario <TICKER>` — 情景分析
- `stocks-cli full-report <TICKER>` — 全面综合报告
- `stocks-cli review <TICKER>` — 回顾历史判断

### Skills (`.claude/skills/`)
Skill 只做编排（调 Python CLI），不含分析逻辑：
- `/fetch-stock` — 数据抓取 (ohlcv + financials + reports，可组合)
- `/analyze-stock` — 技术分析
- `/macro-check` — 宏观评估
- `/valuation` — 估值分析 (10种方法)
- `/full-report` — 综合多维分析
- `/review` — 回顾历史判断

## 关键依赖

```
akshare (CN数据), yfinance (全球), fredapi (US宏观, 需免费key), pycoingecko (加密)
pandas, numpy, pydantic
ta (纯Python技术指标, 非TA-Lib)
jieba (中文分词), nltk/VADER (英文情绪)
typer, rich, PyYAML, jinja2
diskcache (SQLite缓存)
```

## 实施阶段

### Phase 1: 基础骨架 + 数据层
1. 项目结构 + pyproject.toml + config YAML
2. data/base.py (Protocol定义) + models.py
3. cache.py + normalizer.py
4. providers/akshare.py + providers/yfinance.py
5. registry.py
6. CLI 入口 (`stocks-cli fetch <TICKER>` 可拉取数据)
7. **验证**: 取到 600519.SH 和 AAPL 的 OHLCV

### Phase 2: 首批分析模块
1. analysis/base.py (AbstractAnalyzer, AnalysisResult)
2. analysis/technical.py (趋势/RSI/MACD/支撑阻力)
3. CLI analyze-stock 命令 + Rich 输出
4. `.claude/skills/analyze-stock.md`
5. analysis/macro.py (利率/收益率曲线/CPI/PMI)
6. `.claude/skills/macro-check.md`
7. **验证**: `/analyze-stock 600519.SH` 和 `/macro-check` 可用

### Phase 3: 全部分析模块 + 数据源
1. providers/fred.py + providers/coingecko.py + providers/news.py
2. analysis/fundamental/ (FCFF/FCFE/DDM/Graham/EPV/NCAV/RI/multiples/fcf_quality/health/aggregator) + capital_flow.py + sentiment.py + correlation.py + policy.py + risk.py + benchmark.py + scenario.py
3. 剩余 CLI 命令 + Skills

### Phase 4: 集成 + 汇总 + 跟踪
1. scoring.yaml + scorer.py (加权打分)
2. aggregator.py + report.py + Jinja2 模板
3. CLI full-report 命令 + `/full-report` skill
4. src/track/ (record.py + review.py + stats.py)
5. CLI review 命令
6. **验证**: `/full-report 600519.SH` 输出完整多维分析报告 + 风险 + 基准 + 情景

### Phase 5: 打磨
1. JSON 输出 + 配置管理命令
2. 并行化分析模块 (ThreadPoolExecutor)
3. 数据源健康检查 + 降级
4. 错误处理（网络/无效ticker/限流）
5. --watchlist 批量分析
6. 可选 Streamlit dashboard

## 验证方案

每个 Phase 结束后的验证：
- **Phase 1**: `python -m src.cli.main ohlcv 600519.SH` 返回标准化的 OHLCV DataFrame
- **Phase 2**: `/analyze-stock 600519.SH` 输出技术面 + `/macro-check` 输出宏观评估
- **Phase 3**: 每个 `/xxx-check` skill 可独立运行，返回有意义的分析
- **Phase 4**: `/full-report 600519.SH` 输出 7 维度加权综合评分 + 判断 + 风险
- **Phase 5**: 多股票批量分析不超时，降级可用

---

## 开发进度 (2026-05-07)

### 已完成

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | 项目骨架 + 数据层 (AKShare/yfinance/CNINFO providers, Parquet 存储, 增量获取) | ✓ |
| 2 | 分析基类 + 技术分析 + 宏观分析 | ✓ |
| 3 | 基本面估值子模块 (10个方法) | ✓ 代码完成 |
| 3 | 其余分析模块 (7个, 代码完成) | ✓ 代码完成 |
| 3 | CNINFO 年报下载 + MarkItDown | ✓ 超出计划 |
| 4 | 集成层 (scorer/aggregator/report) + 跟踪 | ✓ |
| — | CLI 命令: ohlcv, analyze-stock, financials, reports, macro-check, valuation, full-report, review | ✓ |
| — | Skills: /fetch-stock, /analyze-stock, /macro-check, /valuation, /full-report, /review | ✓ |

### 待完成

**数据源 (Phase 3 遗留):**
- [ ] `providers/fred.py` — 美国宏观数据 (FRED)
- [ ] `providers/coingecko.py` — 加密货币数据
- [ ] `providers/news.py` — RSS 新闻抓取 + NLP 情绪

**CLI + Skills (Phase 3 遗留):**
- [ ] `market-scan` — 多市场概览 `/market-scan`
- [ ] `capital-flow` — 资金流向 `/capital-flow`
- [ ] `sentiment-check` — 情绪检测 `/sentiment-check`
- [ ] `correlation-check` — 跨市场联动 `/correlation-check`
- [ ] `risk-check` — 风险评估 `/risk-check`
- [ ] `benchmark` — 基准对比 `/benchmark`
- [ ] `scenario` — 情景分析 `/scenario`

**基本面 (Phase 3 遗留):**
- [ ] 财报文本分析 (MarkItDown 已集成, 提取会计政策/关联交易/风险因素/管理层展望)
- [x] AKShare 三张表接口不稳定 → 已切换到同花顺 stock_financial_*_ths，三张表稳定可用

**Phase 5 打磨:**
- [ ] JSON 输出 + 配置管理命令
- [ ] 并行化分析模块 (ThreadPoolExecutor)
- [ ] 数据源健康检查 + 降级
- [ ] `--watchlist` 批量分析
- [ ] 可选 Streamlit dashboard

**数据质量:**
- [x] 同花顺财务数据清洗 (normalize_financials, 2026-05-07) — 存储层统一转换带单位字符串为浮点数
- [x] 估值方法 NaN 传播修复 (2026-05-07) — 所有 10 个方法的 float(x or 0) 陷阱已修复
- [x] 估值方法失败原因标注 (reason 字段, 2026-05-07) — 区分"数据缺失"、"模型不适用"、"结果不合理"
- [x] 分红数据抓取 (ak.stock_history_dividend_detail, 2026-05-07) — 存储为 dividends.parquet，DDM 优先使用
- [x] DDM 参数修复 (2026-05-07) — 年度化 DPS、分红 CAGR 替代净利润增长、3% 最小利差防 Gordon 爆炸
- [x] 股本数据修补 (2026-05-07) — BS 股本为 0 时从摘要 净利润/EPS 反推
- [ ] A股幸存者偏差处理 (退市公司历史)
- [ ] 前视偏差检测 (财报发布日期 vs 截止日)
- [ ] 复权数据校验
