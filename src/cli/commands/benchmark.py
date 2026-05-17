import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.base import AnalysisContext
from src.analysis.benchmark import BenchmarkAnalyzer
from src.data.gateway import DataGateway
from src.data.base import Market
from src.data.models import Ticker as TickerModel

from src.utils.ticker import parse_ticker

console = Console()

# Market -> benchmark index
BENCHMARK_MAP = {
    Market.CN: ("cn", "000300", "沪深300"),
    Market.US: ("us", "SPX", "S&P 500"),
    Market.HK: ("hk", "HSI", "恒生指数"),
    Market.JP: ("jp", "N225", "日经225"),
    Market.UK: ("uk", "FTSE", "FTSE 100"),
    Market.DE: ("de", "DAX", "DAX 40"),
    Market.FR: ("fr", "CAC", "CAC 40"),
}

def _get_benchmark_return(gw: DataGateway, mkt: Market) -> float | None:
    """Get 1-year benchmark index return from Parquet storage."""
    bench = BENCHMARK_MAP.get(mkt)
    if not bench:
        return None
    mkt_str, code, _ = bench
    try:
        df = gw.read("index", mkt_str, code, "daily")
        if df is not None and not df.empty and "close" in df.columns:
            close = df["close"].astype(float)
            if len(close) >= 252:
                return float(close.iloc[-1] / close.iloc[-252] - 1)
            elif len(close) > 1:
                return float(close.iloc[-1] / close.iloc[0] - 1)
    except Exception:
        pass
    return None

@click.command()
@click.argument("ticker")
@click.option("--start", default="2022-01-01", help="分析起始日期")
@click.option("--end", default="", help="分析截止日期")
@click.option("--market", default="auto", help="市场 (auto/cn/us/hk/jp/uk/de/fr)")
def benchmark(ticker: str, start: str, end: str, market: str):
    """基准对比 — 相对指数表现 + 股债性价比.

    对比个股 vs 基准指数（沪深300/标普500/恒生指数等），
    结合国债收益率评估股债相对吸引力。
    """
    from datetime import date

    end = end or date.today().strftime("%Y-%m-%d")
    symbol, mkt = parse_ticker(ticker)

    gw = DataGateway()

    bench_info = BENCHMARK_MAP.get(mkt, (None, None, "未知"))
    bench_name = bench_info[2]
    console.print(f"[bold blue]Benchmark: {symbol} vs {bench_name} (market={mkt.value})[/bold blue]")

    # Fetch stock price data
    try:
        if mkt == Market.CN:
            start_fmt = gw._normalize_date(start) if "-" in start else start
            end_fmt = gw._normalize_date(end) if "-" in end else end
            df = gw.get_daily(symbol, start_fmt, end_fmt)
        else:
            df = gw.get_daily(symbol, mkt.value, start, end)

        if df is None or df.empty:
            console.print("[red]No price data available.[/red]")
            return
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        return

    # Get benchmark return
    bench_return = _get_benchmark_return(gw, mkt)

    # Get macro data for risk-free rate
    macro_data = DataGateway().get_macro()
    if bench_return is not None:
        macro_data["benchmark_returns"] = bench_return

    tk = TickerModel(raw=ticker, market=mkt, symbol=symbol)
    ctx = AnalysisContext(ticker=tk, price_data=df, macro_data=macro_data)
    analyzer = BenchmarkAnalyzer()
    result = analyzer.analyze(ctx)

    color = "green" if result.score > 0.2 else ("red" if result.score < -0.2 else "yellow")
    panel = Panel(
        f"[{color}]基准评分：{result.score:+.1f}[/{color}] | 置信度：{result.confidence:.0%}",
        title=f"[bold]基准对比 — vs {bench_name}[/bold]",
        border_style=color,
    )
    console.print(panel)
    console.print(f"[dim]{result.summary}[/dim]")

    if result.signals:
        table = Table(title="基准信号")
        table.add_column("信号")
        table.add_column("方向")
        table.add_column("强度")
        table.add_column("说明")
        for s in result.signals:
            emoji = "+" if s.direction == "bullish" else ("-" if s.direction == "bearish" else "0")
            table.add_row(s.name, emoji, f"{s.strength:.0%}", s.description)
        console.print(table)

    # Data summary
    console.print("\n[bold]关键数据:[/bold]")
    if bench_return is not None:
        console.print(f"  {bench_name} 年回报: {bench_return:+.1%}")
    if df is not None and not df.empty:
        stock_ret = df["close"].astype(float).pct_change().dropna().tail(252).sum()
        console.print(f"  {symbol} 年回报: {stock_ret:+.1%}")
        if bench_return is not None:
            console.print(f"  超额收益: {stock_ret - bench_return:+.1%}")

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]  ⚠ {w}[/yellow]")
