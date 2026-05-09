"""Fetch cryptocurrency daily OHLCV data."""
from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.cache import DataCache
from src.data.storage import ParquetStorage

console = Console()

CRYPTOS = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "BNB": "BNB",
    "XRP": "XRP",
    "DOGE": "Dogecoin",
    "ADA": "Cardano",
    "LINK": "Chainlink",
    "DOT": "Polkadot",
}


@click.command("crypto")
@click.argument("symbol", required=False)
@click.option("--start", default="2015-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
@click.option("--source", default="yfinance", help="Data source: yfinance (default) | coingecko")
@click.option("--spot", is_flag=True, default=False, help="Also save a real-time spot snapshot")
def crypto_data(symbol: str, start: str, end: str, source: str, spot: bool):
    """加密货币日线 — BTC/ETH/SOL 等.

    默认数据源 yfinance，--source coingecko 可获取市值数据。
    不带参数：拉取 BTC + ETH。
    """
    from src.data.providers.yfinance import YFinanceProvider

    end = end or date.today().strftime("%Y-%m-%d")
    cache = DataCache()
    storage = ParquetStorage()

    if symbol:
        symbols = [symbol.upper()]
    else:
        symbols = ["BTC", "ETH"]

    for sym in symbols:
        name = CRYPTOS.get(sym, sym)
        console.print(f"[bold]Fetching {sym} ({name})[/bold]")

        try:
            if source == "coingecko":
                from src.data.providers.coingecko import CoinGeckoProvider
                cg = CoinGeckoProvider(cache=cache, storage=storage)
                df = cg.get_historical_ohlcv(sym)
            else:
                yf = YFinanceProvider(cache=cache, storage=storage)
                df = yf.get_crypto_daily(sym, start=start, end=end)

            if df is None or df.empty:
                console.print(f"[yellow]  No data for {sym}[/yellow]")
                continue

            console.print(f"[green]  {len(df)} rows[/green]")

            # Show latest price
            if "close" in df.columns:
                latest = df.iloc[-1]["close"]
                console.print(f"  Latest: [bold]${latest:,.2f}[/bold]")

            table = Table(title=f"{sym} ({name})")
            table.add_column("Date", style="cyan")
            table.add_column("Open", justify="right")
            table.add_column("High", justify="right")
            table.add_column("Low", justify="right")
            table.add_column("Close", justify="right")
            if "volume" in df.columns:
                table.add_column("Volume", justify="right")

            for _, row in df.tail(10).iterrows():
                cols = [
                    str(row.get("date", "")),
                    f"{row.get('open', 0):,.2f}",
                    f"{row.get('high', 0):,.2f}",
                    f"{row.get('low', 0):,.2f}",
                    f"{row.get('close', 0):,.2f}",
                ]
                if "volume" in df.columns:
                    cols.append(f"{row.get('volume', 0):,.0f}")
                table.add_row(*cols)

            console.print(table)

            # Spot snapshot
            if spot:
                _save_spot_crypto(cache, storage, sym)

        except Exception as e:
            console.print(f"[red]  Error: {e}[/red]")


def _save_spot_crypto(cache, storage, sym: str):
    import pandas as pd
    from src.data.providers.coingecko import CoinGeckoProvider
    try:
        cg = CoinGeckoProvider(cache=cache)
        md = cg.get_market_data(sym)
        if md:
            spot_df = pd.DataFrame([{
                "symbol": sym,
                "price": md.get("price"),
                "change_24h": md.get("change_24h"),
                "change_7d": md.get("change_7d"),
                "market_cap": md.get("market_cap"),
                "volume_24h": md.get("volume_24h"),
            }])
            storage.save(spot_df, "crypto", "global", sym, "spot")
            console.print(f"  [dim]Spot snapshot saved[/dim]")
        else:
            console.print(f"  [yellow]Spot data not found for {sym}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]  Spot fetch failed: {e}[/yellow]")
