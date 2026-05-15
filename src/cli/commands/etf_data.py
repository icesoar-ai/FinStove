import click
from rich.console import Console
from rich.table import Table

from src.data.gateway import DataGateway
from src.utils.ticker import parse_ticker, market_dir

console = Console()


@click.command(name="etf")
@click.argument("ticker")
def etf_data(ticker: str):
    """ETF 数据 — 日线 / 净值 / 持仓.

    A股 ETF: AKShare (日线/净值/持仓).
    美股 ETF: yfinance (日线).
    """
    code, market = parse_ticker(ticker)
    gw = DataGateway()

    console.print(f"[bold]Fetching ETF data for {code} (market={market.value})...[/bold]")

    # 1. Daily OHLCV
    daily = gw.get_etf_daily(code, market)
    if daily is not None and not daily.empty:
        console.print(f"[green]日线: {len(daily)} 行[/green]")
        table = Table(title=f"{code} OHLCV")
        show_cols = [c for c in ["date", "close", "open", "high", "low", "volume"] if c in daily.columns]
        for col in show_cols:
            table.add_column(col)
        for _, row in daily.tail(10).iterrows():
            table.add_row(*[f"{v}"[:12] for v in row[show_cols]])
        console.print(table)
    else:
        console.print("[yellow]日线: 无数据[/yellow]")

    # 2. NAV
    nav = gw.get_etf_nav(code, market)
    if nav is not None and not nav.empty:
        console.print(f"[green]净值: {len(nav)} 行[/green]")
        table = Table(title=f"{code} 净值")
        nav_cols = nav.columns[:6].tolist()
        for col in nav_cols:
            table.add_column(str(col))
        for _, row in nav.tail(10).iterrows():
            table.add_row(*[f"{v}"[:12] for v in row[nav_cols]])
        console.print(table)
    else:
        console.print("[yellow]净值: 无数据[/yellow]")

    # 3. Holdings (CN only)
    holdings = gw.get_etf_holdings(code, market)
    if holdings is not None and not holdings.empty:
        console.print(f"[green]持仓: {len(holdings)} 项[/green]")
        table = Table(title=f"{code} 前十大持仓")
        hold_cols = [c for c in holdings.columns if c in ["股票名称", "占净值比例", "持股数", "持仓市值"]]
        for col in hold_cols:
            table.add_column(str(col))
        for _, row in holdings.head(10).iterrows():
            table.add_row(*[f"{v}"[:16] for v in row[hold_cols]])
        console.print(table)

    console.print(f"\n[dim]存储于 data/etf/{market.value}/{market_dir(market, code)}/[/dim]")
