import click
from rich.console import Console
from rich.table import Table

from src.utils.ticker import parse_ticker, stock_dir

console = Console()


@click.command()
@click.argument("ticker")
@click.option("--years", default="", help="过滤年份，逗号分隔 (如 2021,2022,2023)，默认下载全部可用年报")
def reports(ticker: str, years: str):
    """A股年报下载 — PDF 原文 + Markdown 转换文本.

    数据源: CNINFO (巨潮资讯网)，PDF 自动转 MD 方便文本分析。
    """
    symbol, market = parse_ticker(ticker)
    if market.value != "cn":
        console.print("[red]年报下载仅支持A股[/red]")
        return

    year_list = None
    if years:
        year_list = [int(y.strip()) for y in years.split(",") if y.strip()]

    gw = DataGateway()
    scope = f"({years})" if year_list else "(全部可用)"
    console.print(f"[bold]Fetching annual reports for {symbol} {scope}...[/bold]")

    results = gw.get_reports(symbol)

    if not results:
        console.print("[yellow]未找到年报[/yellow]")
        return

    table = Table(title=f"{symbol} 年报")
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
        kind = "摘要" if r["kind"] == "summary" else "年报"
        table.add_row(str(r["year"]), kind, r["title"][:50], r["publish_date"], pdf_icon, md_icon)

    console.print(table)

    md_count = sum(1 for r in results if r.get("md_path"))
    if md_count > 0:
        console.print(f"\n[dim]PDF + Markdown 存储于 data/stock/cn/{stock_dir(symbol)}/reports/[/dim]")
