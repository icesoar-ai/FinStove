"""Fetch forex pair daily OHLCV data."""
from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.cache import DataCache
from src.data.storage import ParquetStorage

console = Console()

FOREX_PAIRS = {
    "USDCNY": "USD/CNY",
    "EURCNY": "EUR/CNY",
    "JPYCNY": "JPY/CNY",
    "EURUSD": "EUR/USD",
    "USDJPY": "USD/JPY",
    "GBPUSD": "GBP/USD",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "GBPCNY": "GBP/CNY",
}


@click.command("forex")
@click.argument("pair", required=False)
@click.option("--start", default="2010-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
def forex_data(pair: str, start: str, end: str):
    """Fetch forex pair daily rates (USD/CNY, EUR/CNY, JPY/CNY, etc.).

    No pair: fetches all 9 forex pairs.
    """
    from src.data.providers.yfinance import YFinanceProvider

    end = end or date.today().strftime("%Y-%m-%d")
    cache = DataCache()
    storage = ParquetStorage()
    yf = YFinanceProvider(cache=cache, storage=storage)

    if pair:
        pairs = [pair.upper()]
    else:
        pairs = list(FOREX_PAIRS.keys())

    for p in pairs:
        name = FOREX_PAIRS.get(p, p)
        console.print(f"[bold]Fetching {p} ({name})[/bold]")

        try:
            df = yf.get_forex_daily(p, start=start, end=end)

            if df is None or df.empty:
                console.print(f"[yellow]  No data for {p}[/yellow]")
                continue

            console.print(f"[green]  {len(df)} rows[/green]")

            # Show latest rate
            if "close" in df.columns:
                latest = df.iloc[-1]["close"]
                console.print(f"  Latest: [bold]{latest:.4f}[/bold]")

            table = Table(title=f"{p} ({name})")
            table.add_column("Date", style="cyan")
            table.add_column("Open", justify="right")
            table.add_column("High", justify="right")
            table.add_column("Low", justify="right")
            table.add_column("Close", justify="right")

            for _, row in df.tail(10).iterrows():
                table.add_row(
                    str(row.get("date", "")),
                    f"{row.get('open', 0):.4f}",
                    f"{row.get('high', 0):.4f}",
                    f"{row.get('low', 0):.4f}",
                    f"{row.get('close', 0):.4f}",
                )

            console.print(table)

        except Exception as e:
            console.print(f"[red]  Error: {e}[/red]")
