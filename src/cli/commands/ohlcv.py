from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.base import Market
from src.data.cache import DataCache
from src.data.registry import ProviderRegistry
from src.utils.ticker import parse_ticker, stock_dir

console = Console()


@click.command("ohlcv")
@click.argument("ticker")
@click.option("--start", default="2010-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
def ohlcv(ticker: str, start: str, end: str):
    """Fetch daily OHLCV bars for a ticker."""
    end = end or date.today().strftime("%Y-%m-%d")
    symbol, market = parse_ticker(ticker)
    cache = DataCache()
    registry = ProviderRegistry(cache)
    dir_name = stock_dir(symbol) if market == Market.CN else symbol

    console.print(f"[bold]Fetching {dir_name} (market={market.value})[/bold]")

    try:
        if market == Market.CN:
            start_fmt = start.replace("-", "") if "-" in start else start
            end_fmt = end.replace("-", "") if "-" in end else end
            df = registry.akshare.get_daily(symbol, start_fmt, end_fmt, dir_name=dir_name)
        else:
            df = registry.yfinance.get_daily(symbol, market.value, start, end)

        if df is None or df.empty:
            console.print("[red]No data returned.[/red]")
            raise SystemExit(1)

        console.print(f"[green]{len(df)} rows[/green]")

        table = Table(title=f"{dir_name} OHLCV")
        table.add_column("Date", style="cyan")
        table.add_column("Open", justify="right")
        table.add_column("High", justify="right")
        table.add_column("Low", justify="right")
        table.add_column("Close", justify="right")
        table.add_column("Volume", justify="right")

        for _, row in df.tail(20).iterrows():
            table.add_row(
                str(row.get("date", "")),
                f"{row.get('open', 0):.2f}",
                f"{row.get('high', 0):.2f}",
                f"{row.get('low', 0):.2f}",
                f"{row.get('close', 0):.2f}",
                f"{row.get('volume', 0):,}",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
