# A股半年报/季报补齐 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CNINFO 支持下载半年报/季报，Gateway 接入限速，CLI 展示层去掉年度硬编码过滤

**Architecture:** 扩展现有 CNINFO Provider 支持多 category 查询（年度/半年/季度），Gateway 层接入 RateLimiter，CLI 加 `--type`/`--period` 参数

**Tech Stack:** Python 3.12+, requests, Click, Rich

---

### Task 1: CNINFO Provider — 支持多报告类型 + 年份过滤

**Files:**
- Modify: `src/data/providers/cninfo.py`

- [ ] **Step 1: 添加 category 映射常量，修改 `_fetch_page` 接受动态 category**

在 `CNINFOProvider` 类顶部添加映射，修改 `_fetch_page`：

```python
# 在 class CNINFOProvider 内，BASE_URL 之后添加:
CATEGORY_MAP = {
    "annual":       "category_ndbg_szsh",
    "semi_annual":  "category_bndbg_szsh",
    "quarterly":    "category_yjdbg_szsh",
}

TITLE_KEYWORDS = {
    "annual":       "年度报告",
    "semi_annual":  "半年度报告",
    "quarterly":    "季度报告",
}
```

修改 `_fetch_page`，把硬编码的 `"category": "szse"` 改为接收参数：

```python
def _fetch_page(self, stock_id: str, page: int, page_size: int = 50,
                category: str = "category_ndbg_szsh") -> dict:
    data = {
        "pageNum": page, "pageSize": page_size,
        "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": stock_id,
        "searchkey": "", "secid": "",
        "category": category,
        "trade": "", "seDate": "",
        "sortName": "", "sortType": "",
        "isHLtitle": "true",
    }
    r = requests.post(self.BASE_URL, data=data, timeout=self.TIMEOUT)
    r.raise_for_status()
    return r.json()
```

- [ ] **Step 2: 修改 `_resolve_org_id` 中调用 `_fetch_page` 的地方传入默认 category**

两处 `_fetch_page(stock_id, 1, 1)` 保持不变（此处不需要指定 category，用默认值 `category_ndbg_szsh` 即可）。

- [ ] **Step 3: 重写 `list_reports` 支持 `report_types` 和 `since_year`**

```python
def list_reports(self, symbol: str,
                 report_types: Optional[list[str]] = None,
                 since_year: Optional[int] = None) -> list[dict]:
    """List reports for a stock.

    Args:
        symbol: Stock ticker
        report_types: List of types from {"annual", "semi_annual", "quarterly"}.
                      Default to all three.
        since_year: Filter reports earlier than this year. None = no filter.
    """
    if report_types is None:
        report_types = ["annual", "semi_annual", "quarterly"]

    stock_id = self._resolve_org_id(symbol)
    results = []

    for rtype in report_types:
        category = self.CATEGORY_MAP[rtype]
        keyword = self.TITLE_KEYWORDS[rtype]
        resp = self._fetch_page(stock_id, 1, 50, category=category)
        announcements = resp.get("announcements") or []

        for a in announcements:
            title = a.get("announcementTitle", "")
            adjunct = a.get("adjunctUrl", "")
            if not adjunct:
                continue
            if keyword not in title:
                continue

            year_match = re.search(r"(\d{4})", title)
            year = int(year_match.group(1)) if year_match else 0
            if since_year is not None and year < since_year:
                continue

            # Deduplicate: same year + type, keep first (latest from API)
            exists = any(
                r["year"] == year and r["report_type"] == rtype
                for r in results
            )
            if exists:
                continue

            results.append({
                "title": title,
                "year": year,
                "report_type": rtype,
                "kind": "full",  # no summary distinction for interim
                "pdf_url": f"{self.PDF_BASE}/{adjunct}",
                "announcement_id": a.get("announcementId", ""),
                "publish_date": self._parse_time(a.get("announcementTime", "")),
            })

    return sorted(results, key=lambda x: (x["year"], x["report_type"]), reverse=True)
```

- [ ] **Step 4: 修改 `download_reports` 透传新参数**

```python
def download_reports(self, symbol: str,
                     since_year: Optional[int] = None,
                     report_types: Optional[list[str]] = None) -> list[dict]:
    """Download reports (annual + semi + quarterly) for a stock."""
    from src.utils.ticker import stock_dir

    reports = self.list_reports(symbol,
                                report_types=report_types,
                                since_year=since_year)

    dir_name = stock_dir(symbol)
    results = []

    for r in reports:
        safe_title = r["title"].replace("/", "_").replace(":", "_").replace("?", "")

        # PDF
        pdf_dest = self._storage._path("stock", "cn", dir_name,
                                       f"reports/{safe_title}")
        pdf_dest = Path(str(pdf_dest).replace(".parquet", ".pdf"))
        pdf_ok = self._download_file(r["pdf_url"], pdf_dest)

        # Markdown
        md_ok = False
        if pdf_ok:
            md_dest = Path(str(pdf_dest).replace(".pdf", ".md"))
            md_ok = self._convert_to_markdown(pdf_dest, md_dest)

        r["downloaded"] = pdf_ok
        r["pdf_path"] = str(pdf_dest) if pdf_ok else ""
        r["md_path"] = str(pdf_dest).replace(".pdf", ".md") if md_ok else ""
        results.append(r)

        if pdf_ok:
            time.sleep(0.5)

    return results
```

- [ ] **Step 5: 提交**

```bash
git add src/data/providers/cninfo.py
git commit -m "feat: CNINFO 支持半年报/季报多类型查询 + 年份过滤"
```

---

### Task 2: Gateway — CNINFO 接入 RateLimiter

**Files:**
- Modify: `src/data/gateway.py`

- [ ] **Step 1: 修改 `get_reports` 签名并接入限速**

替换现有的 `get_reports` 方法（第 299-307 行）：

```python
def get_reports(self, symbol: str, market: Market = Market.CN,
                since_year: Optional[int] = None,
                report_types: Optional[list[str]] = None) -> list[dict]:
    """年报/半年报/季报下载。

    A股: CNINFO (PDF+MD)，通过 RateLimiter 限速。
    美股: SEC EDGAR (10-K 文本)。
    """
    if market == Market.CN:
        rkey = "cninfo"
        for attempt in self._rate_limiter.attempts(rkey):
            try:
                result = self._cninfo.download_reports(
                    symbol, since_year=since_year, report_types=report_types
                )
                attempt.success()
                return result
            except Exception:
                attempt.failure()
        return []
    return self._edgar.download_10k(symbol)
```

- [ ] **Step 2: 提交**

```bash
git add src/data/gateway.py
git commit -m "feat: Gateway CNINFO 调用接入 RateLimiter 限速"
```

---

### Task 3: CLI `fetch reports` — 加 `--type`，改 `--years` 默认为近 2 年

**Files:**
- Modify: `src/cli/commands/reports.py`

- [ ] **Step 1: 重写 `reports` 命令**

```python
import click
from datetime import date
from rich.console import Console
from rich.table import Table

from src.data.gateway import DataGateway
from src.utils.ticker import parse_ticker, stock_dir

console = Console()

REPORT_TYPE_HELP = {
    "annual": "年度报告",
    "semi_annual": "半年度报告",
    "quarterly": "季度报告",
}


@click.command()
@click.argument("ticker")
@click.option("--type", "report_type", default="all",
              type=click.Choice(["all", "annual", "semi_annual", "quarterly"]),
              help="报告类型，默认 all")
@click.option("--years", default="", help="过滤年份，逗号分隔 (如 2024,2025)，默认近2年")
def reports(ticker: str, report_type: str, years: str):
    """A股报告下载 — PDF 原文 + Markdown 转换文本.

    数据源: CNINFO (巨潮资讯网)，支持年报/半年报/季报。
    """
    symbol, market = parse_ticker(ticker)
    if market.value != "cn":
        console.print("[red]报告下载仅支持A股[/red]")
        return

    # Parse years or default to last 2 years
    if years:
        year_list = [int(y.strip()) for y in years.split(",") if y.strip()]
        since_year = min(year_list) if year_list else date.today().year - 1
    else:
        year_list = None
        since_year = date.today().year - 1

    # Parse report types
    if report_type == "all":
        report_types = ["annual", "semi_annual", "quarterly"]
    else:
        report_types = [report_type]

    gw = DataGateway()
    type_label = "全部" if report_type == "all" else REPORT_TYPE_HELP.get(report_type, report_type)
    scope = f"({years})" if years else "(近2年)"
    console.print(f"[bold]Fetching {type_label} for {symbol} {scope}...[/bold]")

    results = gw.get_reports(symbol, since_year=since_year, report_types=report_types)

    if not results:
        console.print("[yellow]未找到报告[/yellow]")
        return

    table = Table(title=f"{symbol} 报告")
    table.add_column("年份")
    table.add_column("类型")
    table.add_column("标题")
    table.add_column("发布日期")
    table.add_column("PDF")
    table.add_column("MD")

    for r in results:
        pdf_icon = "[green]✓[/green]" if r["downloaded"] else "[red]✗[/red]"
        md_ok = bool(r.get("md_path"))
        md_icon = "[green]✓[/green]" if md_ok else "[dim]-[/dim]"
        kind_label = REPORT_TYPE_HELP.get(r.get("report_type", ""), r.get("kind", ""))
        table.add_row(str(r["year"]), kind_label, r["title"][:50],
                      r["publish_date"], pdf_icon, md_icon)

    console.print(table)

    md_count = sum(1 for r in results if r.get("md_path"))
    if md_count > 0:
        console.print(f"\n[dim]PDF + Markdown 存储于 data/stock/cn/{stock_dir(symbol)}/reports/[/dim]")
```

- [ ] **Step 2: 提交**

```bash
git add src/cli/commands/reports.py
git commit -m "feat: fetch reports 支持 --type 和 --years 默认近2年"
```

---

### Task 4: CLI `fetch financials` — 加 `--period`，去硬编码过滤

**Files:**
- Modify: `src/cli/commands/financials.py`

- [ ] **Step 1: 修改命令参数 + `_display_financials`**

在 `financials` 函数添加 `--period` option：

```python
@click.command()
@click.argument("ticker")
@click.option("--years", default="", help="过滤年份，逗号分隔 (如 2021,2022,2023)")
@click.option("--period", default="all",
              type=click.Choice(["all", "annual", "quarterly"]),
              help="显示周期，默认 all")
def financials(ticker: str, years: str, period: str):
    ...
```

修改 `_display_financials` 去硬编码过滤:

```python
def _display_financials(df, symbol: str, period: str = "all"):
    """Display financial metrics."""
    if period == "annual":
        filtered = df[df["报告期"].str.endswith("-12-31")].sort_values("报告期")
    elif period == "quarterly":
        filtered = df[~df["报告期"].str.endswith("-12-31")].sort_values("报告期")
    else:
        filtered = df.sort_values("报告期")

    if filtered.empty:
        return

    table = Table(title=f"{symbol} 财务摘要")
    ...
```

同时去掉第 62-63 行的硬编码日期过滤 `>= "2021-01-01"`，不再硬编码截止年份。

将 `_display_financials(recent, symbol)` 调用改为 `_display_financials(recent, symbol, period)`。

- [ ] **Step 2: 提交**

```bash
git add src/cli/commands/financials.py
git commit -m "feat: fetch financials 支持 --period，去硬编码年度过滤"
```

---

### Task 5: 年报文本分析 — 兼容新报告类型

**Files:**
- Modify: `src/analysis/report_text.py`

- [ ] **Step 1: 修改 `_find_latest_report` 搜索所有报告类型**

```python
def _find_latest_report(ticker_dir: str, report_type: Optional[str] = None) -> Optional[Path]:
    """Find the most recent report MD file.

    Args:
        ticker_dir: Stock directory name
        report_type: "annual", "semi_annual", "quarterly", or None for any
    """
    reports_dir = Path(f"data/stock/cn/{ticker_dir}/reports")
    if not reports_dir.exists():
        return None

    if report_type == "annual":
        pattern = "*年年度报告*.md"
    elif report_type == "semi_annual":
        pattern = "*半年度报告*.md"
    elif report_type == "quarterly":
        pattern = "*季度报告*.md"
    else:
        pattern = "*.md"

    files = sorted(reports_dir.glob(pattern))
    # Prefer non-summary, non-补充
    full = [f for f in files if "摘要" not in f.name and "补充" not in f.name]
    return full[-1] if full else (files[-1] if files else None)
```

`ReportTextAnalyzer.analyze` 中 `_find_latest_report(ticker_str)` 调用保持不变（默认找最近的报告，不限类型）。`summary` 输出改为 `"报告文本分析{qual}"`（去"年报"字样）。

- [ ] **Step 2: 提交**

```bash
git add src/analysis/report_text.py
git commit -m "feat: 报告文本分析兼容半年报/季报"
```

---

### Task 6: 端到端验证

- [ ] **Step 1: 测试 fetch reports 多类型抓取**

```bash
python -m src.cli.main reports 600519.SH --type all
# 预期: 列出年报 + 半年报 + 季报，下载 PDF + MD
```

- [ ] **Step 2: 测试 --years 默认近 2 年**

```bash
python -m src.cli.main reports 600519.SH
# 预期: 只下载 2025 和 2026 年的报告
```

- [ ] **Step 3: 测试 financials --period**

```bash
python -m src.cli.main financials 600519.SH --period quarterly
# 预期: 只显示季度财务数据
```

- [ ] **Step 4: 测试报告文本分析**

```bash
python -m src.cli.main report-analyze 600519.SH
# 预期: 分析最新可用的报告（不限于年报）
```
