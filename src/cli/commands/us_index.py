from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.cache import DataCache
from src.data.storage import ParquetStorage

console = Console()

US_INDICES = {
    "SPX": "S&P 500",
    "NDX": "Nasdaq Composite",
    "DJI": "Dow Jones Industrial",
    "RUT": "Russell 2000",
    "VIX": "CBOE Volatility Index",
}


@click.command("us-index")
@click.argument("symbol", required=False)
@click.option("--start", default="2010-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
def us_index(symbol: str, start: str, end: str):
    """Fetch major US stock index daily data (S&P 500, Nasdaq, Dow, Russell, VIX)."""
    from src.data.providers.yfinance import YFinanceProvider

    end = end or date.today().strftime("%Y-%m-%d")
    cache = DataCache()
    storage = ParquetStorage()
    yf = YFinanceProvider(cache=cache, storage=storage)

    if symbol:
        symbols = [symbol.upper()]
    else:
        symbols = list(US_INDICES.keys())

    for sym in symbols:
        name = US_INDICES.get(sym, sym)
        console.print(f"[bold]Fetching {sym} ({name})[/bold]")

        try:
            df = yf.get_index_daily(sym, market="us", start=start, end=end)

            if df is None or df.empty:
                console.print(f"[yellow]  No data for {sym}[/yellow]")
                continue

            console.print(f"[green]  {len(df)} rows[/green]")

            table = Table(title=f"{sym} {name}")
            table.add_column("Date", style="cyan")
            table.add_column("Open", justify="right")
            table.add_column("High", justify="right")
            table.add_column("Low", justify="right")
            table.add_column("Close", justify="right")
            table.add_column("Volume", justify="right")

            for _, row in df.tail(10).iterrows():
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
            console.print(f"[red]  Error: {e}[/red]")
