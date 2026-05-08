"""Intraday minute-level OHLCV — auto-switch AKShare/yfinance."""
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.data.cache import DataCache
from src.data.storage import ParquetStorage
from src.utils.ticker import parse_ticker, stock_dir

console = Console()


def _fmt_chg(val: float | None) -> str:
    if val is None or val != val:
        return "[dim]—[/dim]"
    sign = "+" if val > 0 else ""
    color = "green" if val > 0 else "red" if val < 0 else "dim"
    return f"[{color}]{sign}{val:.2f}%[/]"


@click.command("intraday")
@click.argument("ticker")
@click.option("--interval", "-i", default="5m", help="K线周期: 1m/5m/15m/30m/60m/1h")
@click.option("--period", "-p", default="5d", help="回溯: 1d/5d/1mo (yfinance仅控制时长)")
@click.option("--save", is_flag=True, default=False, help="持久化到 Parquet")
def intraday(ticker: str, interval: str, period: str, save: bool):
    """盘中分钟K线 — A股优先AKShare，限流自动降级yfinance.

    \b
    示例:
      intraday 600519 -i 5m        茅台 5分钟K线
      intraday AAPL -i 15m         Apple 15分钟K线
      intraday 600519 -i 1m --save 1分钟K线 + 持久化
    """
    symbol, market = parse_ticker(ticker)
    cache = DataCache()
    storage = ParquetStorage()

    console.print(f"[bold]盘中 {ticker} ({interval})[/bold]")

    df = None
    source = None

    if market == "CN":
        # Try AKShare first (better real-time for CN), fallback to yfinance
        from src.data.providers.akshare import AKShareProvider
        ak = AKShareProvider(cache=cache)
        try:
            ak_period = interval.replace("m", "").replace("h", "60")
            df = ak.get_intraday(symbol, period=ak_period, adjust="qfq")
            if not df.empty:
                source = "AKShare"
        except Exception:
            pass

        if df is None or df.empty:
            console.print("[dim]  AKShare 不可用，降级 yfinance...[/dim]")
            from src.data.providers.yfinance import YFinanceProvider
            yf = YFinanceProvider(cache=cache, storage=storage)
            try:
                df = yf.get_intraday(symbol, market="cn", interval=interval, period=period)
                if not df.empty:
                    source = "YFinance"
            except Exception:
                pass
    else:
        from src.data.providers.yfinance import YFinanceProvider
        yf = YFinanceProvider(cache=cache, storage=storage)
        try:
            df = yf.get_intraday(symbol, market=market.value.lower(),
                                 interval=interval, period=period)
            if not df.empty:
                source = "YFinance"
        except Exception:
            pass

    if df is None or df.empty:
        console.print("[red]无法获取盘中数据 (AKShare 限流 + yfinance 不可用)[/red]")
        return

    console.print(f"[dim]  数据源: {source}  |  {len(df)} 根 K 线[/dim]")

    # Summary
    if "close" in df.columns and "datetime" in df.columns:
        latest = df.iloc[-1]
        first = df.iloc[0]
        day_chg = None
        if "open" in df.columns:
            day_open = df[df["datetime"].dt.date == latest["datetime"].date()]
            if not day_open.empty:
                day_open_price = day_open.iloc[0]["open"]
                day_chg = (latest["close"] - day_open_price) / day_open_price * 100

        pnl = Panel.fit(
            f"最新 [{source}]  {latest['datetime']}  |  "
            f"close [bold]{latest['close']:,.2f}[/bold]  |  "
            f"日内 {_fmt_chg(day_chg) if day_chg else '[dim]—[/dim]'}",
            border_style="cyan")
        console.print(pnl)

    # Table — last 30 rows
    show_cols = [c for c in ["datetime", "open", "high", "low", "close", "volume"] if c in df.columns]
    tbl = Table(title=f"{ticker} ({interval})")
    for c in show_cols:
        justify = "right" if c != "datetime" else "left"
        style = "cyan" if c == "datetime" else None
        tbl.add_column(c, justify=justify, style=style)

    for _, row in df.tail(30).iterrows():
        vals = []
        for c in show_cols:
            v = row[c]
            if c == "datetime":
                vals.append(str(v))
            elif c == "volume":
                vals.append(f"{v:,.0f}" if v == v else "")
            else:
                vals.append(f"{v:,.2f}" if v == v else "")
        tbl.add_row(*vals)

    console.print(tbl)

    # Persist
    if save:
        store_sym = stock_dir(symbol) if market == "CN" else symbol
        storage.merge_intraday(df, "stock", market.value.lower(), store_sym, interval)
        path = f"data/stock/{market.value.lower()}/{store_sym}/intraday_{interval}.parquet"
        console.print(f"[dim]  Saved → {path}[/dim]")
