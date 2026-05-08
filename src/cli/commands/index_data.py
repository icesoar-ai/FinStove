from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.cache import DataCache
from src.data.storage import ParquetStorage

console = Console()

INDEX_MAP = {
    "000001": "上证指数",
    "399001": "深证成指",
    "000300": "沪深300",
    "000016": "上证50",
    "399006": "创业板指",
    "000688": "科创50",
    "000905": "中证500",
}


@click.command("index")
@click.argument("symbol", required=False)
@click.option("--start", default="2010-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
def index_data(symbol: str, start: str, end: str):
    """Fetch major Chinese stock index daily data."""
    from src.data.providers.akshare import AKShareProvider

    end = end or date.today().strftime("%Y-%m-%d")
    cache = DataCache()
    storage = ParquetStorage()
    ak = AKShareProvider(cache=cache, storage=storage)

    if symbol:
        symbols = [symbol]
    else:
        symbols = list(INDEX_MAP.keys())

    for sym in symbols:
        name = INDEX_MAP.get(sym, sym)
        console.print(f"[bold]Fetching {sym} ({name})[/bold]")

        try:
            start_fmt = start.replace("-", "") if "-" in start else start
            end_fmt = end.replace("-", "") if "-" in end else end
            df = ak.get_index_daily(sym, start_fmt, end_fmt)

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
