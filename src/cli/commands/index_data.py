"""Fetch stock index daily OHLCV data — CN + global markets."""
from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.cache import DataCache
from src.data.storage import ParquetStorage

console = Console()

CN_INDICES = {
    "000001": "上证指数", "399001": "深证成指", "000300": "沪深300",
    "000016": "上证50", "399006": "创业板指", "000688": "科创50", "000905": "中证500",
}

MARKET_MAP = {
    "us": {
        "indices": {"SPX": "S&P 500", "NDX": "Nasdaq Composite", "DJI": "Dow Jones Industrial",
                     "RUT": "Russell 2000", "VIX": "CBOE Volatility Index"},
        "label": "US",
    },
    "hk": {"indices": {"HSI": "Hang Seng Index"}, "label": "Hong Kong"},
    "jp": {"indices": {"N225": "Nikkei 225"}, "label": "Japan"},
    "uk": {"indices": {"FTSE": "FTSE 100"}, "label": "UK"},
    "de": {"indices": {"DAX": "DAX 40"}, "label": "Germany"},
    "fr": {"indices": {"CAC": "CAC 40"}, "label": "France"},
}


@click.command("index")
@click.argument("market", required=False)
@click.argument("symbol", required=False)
@click.option("--start", default="2010-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
def index_data(market: str, symbol: str, start: str, end: str):
    """Fetch stock index daily data — CN + global markets.

    \b
    Examples:
      index                  # Fetch ALL indices (CN + global)
      index cn               # All CN indices (via AKShare)
      index us               # All US indices (via Yahoo Finance)
      index cn 000300        # CSI 300 only
      index us SPX           # S&P 500 only
      index hk               # Hang Seng Index

    Valid markets: cn, us, hk, jp, uk, de, fr
    """
    end = end or date.today().strftime("%Y-%m-%d")
    cache = DataCache()
    storage = ParquetStorage()

    # Determine which markets to fetch
    if market:
        market = market.lower()
        if market == "all":
            markets_global = list(MARKET_MAP)
            markets_order = ["cn"] + markets_global
        elif market == "cn":
            markets_order = ["cn"]
        elif market in MARKET_MAP:
            markets_order = [market]
        else:
            valid = "cn, " + ", ".join(MARKET_MAP) + ", all"
            console.print(f"[red]Invalid market: {market}. Valid: {valid}[/red]")
            return
    else:
        markets_order = ["cn"] + list(MARKET_MAP)

    for mkt in markets_order:
        if mkt == "cn":
            _fetch_cn(cache, storage, symbol, start, end)
        else:
            _fetch_global(mkt, symbol, start, end, cache, storage)


def _fetch_cn(cache, storage, symbol: str, start: str, end: str):
    """Fetch CN indices via AKShare."""
    from src.data.providers.akshare import AKShareProvider

    ak = AKShareProvider(cache=cache, storage=storage)
    symbols = [symbol] if symbol else list(CN_INDICES.keys())

    for sym in symbols:
        name = CN_INDICES.get(sym, sym)
        console.print(f"[bold]Fetching {sym} ({name}) [CN][/bold]")

        try:
            start_fmt = start.replace("-", "") if "-" in start else start
            end_fmt = end.replace("-", "") if "-" in end else end
            df = ak.get_index_daily(sym, start_fmt, end_fmt)
            _display_table(df, f"{sym} ({name}) [CN]")
        except Exception as e:
            console.print(f"[red]  Error: {e}[/red]")


def _fetch_global(mkt: str, symbol: str, start: str, end: str, cache, storage):
    """Fetch global indices via Yahoo Finance."""
    from src.data.providers.yfinance import YFinanceProvider

    yf = YFinanceProvider(cache=cache, storage=storage)
    info = MARKET_MAP[mkt]

    if symbol:
        symbols = {symbol.upper(): info["indices"].get(symbol.upper(), symbol.upper())}
    else:
        symbols = info["indices"]

    for sym, name in symbols.items():
        console.print(f"[bold]Fetching {sym} ({name}) [{info['label']}][/bold]")

        try:
            df = yf.get_index_daily(sym, market=mkt, start=start, end=end)
            _display_table(df, f"{sym} ({name}) [{info['label']}]")
        except Exception as e:
            console.print(f"[red]  Error: {e}[/red]")


def _display_table(df, title: str):
    """Display OHLCV table."""
    if df is None or df.empty:
        console.print(f"[yellow]  No data[/yellow]")
        return

    console.print(f"[green]  {len(df)} rows[/green]")

    table = Table(title=title)
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
