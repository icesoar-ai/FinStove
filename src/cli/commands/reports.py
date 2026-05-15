import click
from datetime import date
from rich.console import Console
from rich.table import Table

from src.data.gateway import DataGateway, Market
from src.utils.ticker import parse_ticker, stock_dir

console = Console()

REPORT_TYPE_HELP = {
    "annual":       "年报",
    "semi_annual":  "半年报",
    "quarterly":    "季报",
}

US_REPORT_TYPE_HELP = {
    "annual":       "10-K 年报",
    "quarterly":    "10-Q 季报",
}


@click.command()
@click.argument("ticker")
@click.option("--type", "report_type", default="all",
              type=click.Choice(["all", "annual", "semi_annual", "quarterly"]),
              help="报告类型，默认 all")
@click.option("--years", default="", help="过滤年份，逗号分隔 (如 2024,2025)，默认近2年")
def reports(ticker: str, report_type: str, years: str):
    """报告下载 — PDF 原文 / SEC 文本.

    A股: CNINFO (年报/半年报/季报)。
    美股: SEC EDGAR (10-K 年报 / 10-Q 季报)。
    """
    symbol, market = parse_ticker(ticker)

    # Parse years or default to last 2 years
    if years:
        parsed = [int(y.strip()) for y in years.split(",") if y.strip()]
        since_year = min(parsed) if parsed else date.today().year - 1
    else:
        since_year = date.today().year - 1

    # Parse report types
    if market.value == "cn":
        if report_type == "all":
            report_types = ["annual", "semi_annual", "quarterly"]
        else:
            report_types = [report_type]
        label_map = REPORT_TYPE_HELP
    else:
        # US: no semi_annual
        if report_type == "all":
            report_types = ["annual", "quarterly"]
        elif report_type == "semi_annual":
            console.print("[red]美股不支持半年报[/red]")
            return
        else:
            report_types = [report_type]
        label_map = US_REPORT_TYPE_HELP

    gw = DataGateway()
    type_label = "全部" if report_type == "all" else REPORT_TYPE_HELP.get(report_type, report_type)
    scope = f"({years})" if years else "(近2年)"
    mkt_label = "A股" if market.value == "cn" else "美股"
    console.print(f"[bold]Fetching {mkt_label} {type_label} for {symbol} {scope}...[/bold]")

    results = gw.get_reports(symbol, market, since_year=since_year, report_types=report_types)

    if not results:
        console.print("[yellow]未找到报告[/yellow]")
        return

    table = Table(title=f"{symbol} 报告")
    table.add_column("年份")
    table.add_column("类型")
    table.add_column("标题")
    table.add_column("发布日期")
    table.add_column("文件")

    for r in results:
        file_ok = r.get("downloaded")
        file_icon = "[green]✓[/green]" if file_ok else "[red]✗[/red]"
        kind_label = label_map.get(r.get("report_type", ""), r.get("form", ""))
        title = r.get("title", r.get("description", ""))[:50]
        pub_date = r.get("publish_date", r.get("filing_date", ""))
        year = r.get("year", r.get("report_date", "")[:4])
        table.add_row(str(year), kind_label, title, pub_date, file_icon)

    console.print(table)

    if market.value == "cn":
        md_count = sum(1 for r in results if r.get("md_path"))
        if md_count > 0:
            console.print(f"\n[dim]PDF + Markdown 存储于 data/stock/cn/{stock_dir(symbol)}/reports/[/dim]")
    else:
        console.print(f"\n[dim]文本存储于 data/stock/us/{symbol}/reports/[/dim]")
