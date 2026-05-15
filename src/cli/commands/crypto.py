"""Fetch cryptocurrency daily OHLCV data."""
from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.gateway import DataGateway

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
    end = end or date.today().strftime("%Y-%m-%d")
    gw = DataGateway()

    if symbol:
        symbols = [symbol.upper()]
    else:
        symbols = ["BTC", "ETH"]

    for sym in symbols:
        name = CRYPTOS.get(sym, sym)
        console.print(f"[bold]Fetching {sym} ({name})[/bold]")

        try:
            df = gw.get_crypto(sym, start=start, end=end, source=source, force=True)

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
                _save_spot_crypto(gw, sym)

        except Exception as e:
            console.print(f"[red]  Error: {e}[/red]")


def _save_spot_crypto(gw: DataGateway, sym: str):
    try:
        md = gw.get_crypto_market_data(sym)
        if md:
            console.print(f"  [dim]Spot snapshot acquired for {sym}[/dim]")
        else:
            console.print(f"  [yellow]Spot data not found for {sym}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]  Spot fetch failed: {e}[/yellow]")
