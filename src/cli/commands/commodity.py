"""Fetch commodity futures daily OHLCV data."""
from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.cache import DataCache
from src.data.storage import ParquetStorage

console = Console()

COMMODITIES = {
    "GC": "COMEX Gold",
    "SI": "COMEX Silver",
    "CL": "WTI Crude Oil",
    "BZ": "Brent Crude Oil",
    "NG": "Natural Gas",
    "HG": "COMEX Copper",
    "ZC": "CBOT Corn",
    "ZS": "CBOT Soybean",
    "PL": "NYMEX Platinum",
    "PA": "NYMEX Palladium",
}


@click.command("commodity")
@click.argument("symbol", required=False)
@click.option("--start", default="2010-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
@click.option("--spot", is_flag=True, default=False, help="Also save a real-time spot snapshot")
def commodity_data(symbol: str, start: str, end: str, spot: bool):
    """Fetch commodity futures daily OHLCV (Gold, Oil, Copper, Natural Gas, etc.).

    No symbol: fetches all commodities.
    """
    from src.data.providers.yfinance import YFinanceProvider

    end = end or date.today().strftime("%Y-%m-%d")
    cache = DataCache()
    storage = ParquetStorage()
    yf = YFinanceProvider(cache=cache, storage=storage)

    if symbol:
        symbols = [symbol.upper()]
    else:
        symbols = list(COMMODITIES.keys())

    for sym in symbols:
        name = COMMODITIES.get(sym, sym)
        console.print(f"[bold]Fetching {sym} ({name})[/bold]")

        try:
            df = yf.get_commodity_daily(sym, start=start, end=end)

            if df is None or df.empty:
                console.print(f"[yellow]  No data for {sym}[/yellow]")
                continue

            console.print(f"[green]  {len(df)} rows[/green]")

            table = Table(title=f"{sym} ({name})")
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

            # Spot snapshot
            if spot:
                _save_spot_commodity(cache, storage, sym)

        except Exception as e:
            console.print(f"[red]  Error: {e}[/red]")


# Keyword map for matching commodity spot names
_COMMODITY_SPOT_KW = {
    "GC": "黄金", "SI": "白银", "CL": "美原油", "BZ": "布伦特",
    "NG": "天然气", "HG": "铜", "ZC": "玉米", "ZS": "大豆",
    "PL": "铂", "PA": "钯",
}


def _save_spot_commodity(cache, storage, sym: str):
    from src.data.providers.akshare import AKShareProvider
    try:
        ak = AKShareProvider(cache=cache)
        fut_df = ak.get_futures_spot()
        kw = _COMMODITY_SPOT_KW.get(sym, sym)
        row = fut_df[fut_df["名称"].str.contains(kw, na=False)]
        if not row.empty:
            storage.save(row.head(1), "commodity", "global", sym, "spot")
            console.print(f"  [dim]Spot snapshot saved[/dim]")
        else:
            console.print(f"  [yellow]Spot data not found for {sym}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]  Spot fetch failed: {e}[/yellow]")
