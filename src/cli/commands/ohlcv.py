from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.base import Market
from src.data.gateway import DataGateway
from src.utils.ticker import parse_ticker, stock_dir

console = Console()

@click.command("ohlcv")
@click.argument("ticker")
@click.option("--start", default="2010-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
@click.option("--intraday", "-i", default=None,
              help="Also fetch intraday bars: 1m/5m/15m/30m/60m/1h")
def ohlcv(ticker: str, start: str, end: str, intraday: str):
    """个股日线 OHLCV — A股/港股/美股.

    --intraday 可同时拉取盘中分钟K线。
    """
    end = end or date.today().strftime("%Y-%m-%d")
    symbol, market = parse_ticker(ticker)
    gw = DataGateway()
    dir_name = stock_dir(symbol) if market == Market.CN else symbol

    console.print(f"[bold]Fetching {dir_name} (market={market.value})[/bold]")

    try:
        df = gw.get_daily(symbol, market, start=start, end=end)

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

    # Intraday snapshot
    if intraday:
        console.print(f"[bold]  Intraday ({intraday})...[/bold]")
        intra_df = gw.get_intraday(symbol, market, intraday)
        if intra_df is not None and not intra_df.empty:
            store_sym = dir_name
            gw._storage.merge_intraday(intra_df, "stock", market.value.lower(),
                                      store_sym, intraday)
            path = f"data/stock/{market.value.lower()}/{store_sym}/intraday_{intraday}.parquet"
            console.print(f"[dim]  {len(intra_df)} bars → {path}[/dim]")
        else:
            console.print("[yellow]  Intraday fetch failed[/yellow]")

