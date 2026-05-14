# CLI 命令参考

## 数据抓取 (fetch)

| 命令 | 覆盖范围 | 说明 |
|------|---------|------|
| `fetch ohlcv <TICKER>` | A股/港股/美股 | 个股日线 OHLCV，A股三级降级 (AKShare→yfinance→Baostock) |
| `fetch index [MARKET] [CODE]` | CN/US/HK/JP/UK/DE/FR | 全球指数日线，无参拉全部 |
| `fetch commodity [CODE]` | 10 种大宗商品 | 黄金/白银/WTI/布伦特/天然气/铜/铂金/钯金/铝/锌 |
| `fetch forex [PAIR]` | 9 个汇率对 | USDCNY/EURCNY/JPYCNY/EURUSD/USDJPY/GBPUSD/AUDUSD/USDCAD/GBPCNY |
| `fetch crypto [SYMBOL]` | BTC/ETH/SOL 等 | 加密货币日线 |
| `fetch financials <TICKER>` | A股/美股 | 三张表 + 财务指标 + 分红记录 |
| `fetch reports <TICKER>` | A股 | 年报 PDF + Markdown 自动转换 (CNINFO) |
| `fetch flow` | 沪深港通 | 北向 + 南向资金流向 |
| `fetch yield-curve` | 美债 | 3月/1年/2年/5年/10年/30年收益率 |

## 实时行情 (live)

| 命令 | 说明 |
|------|------|
| `live spot` | 全球指数/外汇/商品/加密货币/A股/港股/美股快照 |
| `live spot -m cn [hk] [us]` | 市场涨跌榜 |
| `live spot <TICKER>` | 个股实时行情 |
| `live intraday <TICKER> [-i 5m]` | 盘中分钟K线 (AKShare→yfinance 自动降级) |

## 分析

| 命令 | 维度 | 说明 |
|------|------|------|
| `analyze-stock <TICKER>` | 技术面 | 趋势/动量/成交量/支撑阻力/形态识别，评分 -2~+2 |
| `macro-check` | 宏观 | CN 15+指标 + US via FRED + DXY + VIX |
| `valuation <TICKER>` | 基本面 | 10 种估值方法综合 |
| `sentiment <TICKER>` | 情绪 | jieba分词 + 金融情感词典 |
| `report-analyze <TICKER>` | 年报文本 | 审计意见/关键指标提取/风险因素/管理层展望 |
| `risk-check <TICKER>` | 风险 | VaR/CVaR/最大回撤/波动率/流动性风险 |
| `benchmark <TICKER>` | 基准对比 | 相对指数表现 + 股债性价比 |
| `scenario <TICKER>` | 情景 | 乐观/悲观/反转情景 + 波动率敏感性 |
| `correlation-check` | 跨市场 | 黄金/DXY/VIX → Risk-On/Risk-Off |
| `full-report <TICKER>` | 综合 | 10 维度加权评分 + 目标价 + 风险 + 情景 |
| `market-scan` | 概览 | 全球资产 1/5/30/90/180 日涨跌幅 + 均线趋势 |
| `review <TICKER>` | 跟踪 | 历史判断回顾，胜率 + 偏差度 |
| `summary` | 总览 | 每日全品种最新价/涨跌幅/数据新鲜度 |
