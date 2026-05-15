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
