from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.base import Market
from src.data.cache import DataCache
from src.data.registry import ProviderRegistry
from src.data.storage import ParquetStorage
from src.utils.ticker import parse_ticker, stock_dir

console = Console()


@click.command("ohlcv")
@click.argument("ticker")
@click.option("--start", default="2010-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
@click.option("--intraday", "-i", default=None,
              help="Also fetch intraday bars: 1m/5m/15m/30m/60m/1h")
def ohlcv(ticker: str, start: str, end: str, intraday: str):
    """Fetch daily OHLCV bars for a ticker.

    Use --intraday to also fetch and persist intraday minute bars.
    """
    end = end or date.today().strftime("%Y-%m-%d")
    symbol, market = parse_ticker(ticker)
    cache = DataCache()
    storage = ParquetStorage()
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

    # Intraday snapshot
    if intraday:
        console.print(f"[bold]  Intraday ({intraday})...[/bold]")
        intra_df = _fetch_intraday(symbol, market, intraday, cache, storage)
        if intra_df is not None and not intra_df.empty:
            store_sym = dir_name
            storage.merge_intraday(intra_df, "stock", market.value.lower(),
                                   store_sym, intraday)
            path = f"data/stock/{market.value.lower()}/{store_sym}/intraday_{intraday}.parquet"
            console.print(f"[dim]  {len(intra_df)} bars → {path}[/dim]")
        else:
            console.print("[yellow]  Intraday fetch failed[/yellow]")


def _fetch_intraday(symbol: str, market: Market, interval: str, cache, storage):
    """Auto-switch: CN → AKShare first, fallback yfinance. Others → yfinance."""
    if market == Market.CN:
        from src.data.providers.akshare import AKShareProvider
        ak = AKShareProvider(cache=cache)
        try:
            ak_period = interval.replace("m", "").replace("h", "60")
            df = ak.get_intraday(symbol, period=ak_period, adjust="qfq")
            if not df.empty:
                return df
        except Exception:
            pass

    from src.data.providers.yfinance import YFinanceProvider
    yf = YFinanceProvider(cache=cache, storage=storage)
    try:
        return yf.get_intraday(symbol, market=market.value.lower(),
                               interval=interval, period="5d")
    except Exception:
        return None
