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
@click.option("--spot", is_flag=True, default=False, help="Also save a real-time spot snapshot")
def forex_data(pair: str, start: str, end: str, spot: bool):
    """外汇汇率日线 — 美元/人民币, 欧元/人民币, 日元/人民币等 9 对.

    不带参数：拉取全部 9 个汇率对。
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

            # Spot snapshot
            if spot:
                _save_spot_forex(cache, storage, p)

        except Exception as e:
            console.print(f"[red]  Error: {e}[/red]")


_FOREX_SPOT_KW = {
    "USDCNY": "美元/人民币", "EURCNY": "欧元/人民币", "JPYCNY": "日元/人民币",
    "EURUSD": "欧元/美元", "USDJPY": "美元/日元", "GBPUSD": "英镑/美元",
    "AUDUSD": "澳元/美元", "USDCAD": "美元/加元", "GBPCNY": "英镑/人民币",
}


def _save_spot_forex(cache, storage, pair: str):
    from src.data.providers.akshare import AKShareProvider
    try:
        ak = AKShareProvider(cache=cache)
        fx_df = ak.get_forex_spot()
        kw = _FOREX_SPOT_KW.get(pair, pair)
        row = fx_df[fx_df["名称"].str.contains(kw, na=False)]
        if not row.empty:
            storage.save(row.head(1), "forex", "global", pair, "spot")
            console.print(f"  [dim]Spot snapshot saved[/dim]")
        else:
            console.print(f"  [yellow]Spot data not found for {pair}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]  Spot fetch failed: {e}[/yellow]")
