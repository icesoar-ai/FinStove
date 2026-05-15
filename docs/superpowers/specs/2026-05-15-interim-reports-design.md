# A股半年报/季报补齐 — 设计

## 背景

当前 CNINFO 只下载年报（`category_ndbg_szsh` + 标题匹配"年度报告"），缺失半年报和季报。AKShare 结构化财务数据虽已按季度存储，但 CLI 展示层硬编码了年度过滤。

## 范围

仅 A股。美股 10-Q 和港股财报另开 spec。

## 设计

### 1. CNINFO Provider (`src/data/providers/cninfo.py`)

**`list_reports(symbol, report_types, since_year)`**

三个新 category 映射：

| 类型 | CNINFO category | 标题匹配 |
|------|----------------|----------|
| `annual` | `category_ndbg_szsh` | 年度报告 |
| `semi_annual` | `category_bndbg_szsh` | 半年度报告 |
| `quarterly` | `category_yjdbg_szsh` | 季度报告 |

- 默认 `report_types=["annual", "semi_annual", "quarterly"]`
- 每 category 独立调用一页 CNINFO API（pageSize=50），合并结果
- `since_year`：过滤早于此年份的报告，None 表示不过滤
- 去重逻辑：同一年内可能有多份报告，取最新的

**`download_reports(symbol, since_year, report_types)`**

- 透传参数给 `list_reports`
- 现有 PDF 下载 + MarkItDown 转换逻辑不变
- 文件名已然含报告类型（原 CNINFO 标题），无需改造存储路径

**限速**: 已有配置（`min_interval_ms: 2000`, `max_retries: 2`, `exponential` backoff），但 Provider 内部没用。改为通过 Gateway `_try` 调用，让配置生效。

### 2. Gateway (`src/data/gateway.py`)

`get_reports(symbol, market, since_year, report_types)`:
- A股走 `self._try("_cninfo", self._cninfo.download_reports, ...)` 替代直接调用
- 其他市场路径不变

### 3. CLI

**`fetch reports <TICKER>`**:

```
--type all|annual|semi_annual|quarterly  [default: all]
--years YYYY,YYYY                         [default: 最近2年]
```

实现：`--years` 未指定时计算 `since_year = current_year - 1`（含去年和今年），传给 `get_reports`。

**`fetch financials <TICKER>`**:

```
--period all|annual|quarterly  [default: all]
```

- 去掉 `_display_financials` 中硬编码的 `df["报告期"].str.endswith("-12-31")` 过滤
- 去掉硬编码的 `>= "2021-01-01"` 截止日期
- 按 `--period` 筛选展示

### 4. 分析模块 (`src/analysis/report_text.py`)

- 当前年报分析逻辑需兼容半年报/季报
- 报告类型从文件名或元数据中提取

### 5. 不做的

- 不新增 Provider，只扩展现有 CNINFO
- 不新增降级链（CNINFO 稳定性高，财报抓取低频）
- 不改变存储目录结构

## 受影响文件

| 文件 | 改动 |
|------|------|
| `src/data/providers/cninfo.py` | 核心改造：多 category，since_year 过滤 |
| `src/data/gateway.py` | CNINFO 调用接入 `_try` 限速 |
| `src/cli/commands/reports.py` | `--type`, `--years` 默认2年 |
| `src/cli/commands/financials.py` | `--period`，去掉硬编码过滤 |
| `src/analysis/report_text.py` | 兼容新报告类型 |
| `config/providers.yaml` | 无需改（限速配置已存在） |
