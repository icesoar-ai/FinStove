import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.base import AnalysisContext
from src.analysis.technical import TechnicalAnalyzer
from src.data.gateway import DataGateway
from src.data.base import Market
from src.data.models import Ticker as TickerModel
from src.utils.ticker import parse_ticker

console = Console()

@click.command()
@click.argument("ticker")
@click.option("--start", default="2020-01-01", help="分析起始日期")
@click.option("--end", default="", help="分析截止日期 (默认: 今日)")
@click.option("--market", default="auto", help="市场 (auto 自动识别 / cn / us / hk / jp / uk / de / fr)")
def analyze_stock(ticker: str, start: str, end: str, market: str):
    """个股技术分析 — 趋势/动量/成交量/支撑阻力/形态识别.

    基于日线 OHLCV 数据，产出多维技术信号和综合评分 (-2 ~ +2)。
    """
    from datetime import date

    end = end or date.today().strftime("%Y-%m-%d")
    symbol, mkt = parse_ticker(ticker)

    gw = DataGateway()

    console.print(f"[bold blue]Analyzing {symbol} (market={mkt.value})[/bold blue]")

    # Fetch price data
    try:
        if mkt == Market.CN:
            start_fmt = gw._normalize_date(start) if "-" in start else start
            end_fmt = gw._normalize_date(end) if "-" in end else end
            df = gw.get_daily(symbol, mkt, start_fmt, end_fmt)
        else:
            df = gw.get_daily(symbol, mkt.value, start, end)

        if df is None or df.empty:
            console.print("[red]No price data available.[/red]")
            return
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        return

    console.print(f"[dim]{len(df)} bars loaded[/dim]")

    # Build context
    tk = TickerModel(raw=ticker, market=mkt, symbol=symbol)
    ctx = AnalysisContext(ticker=tk, price_data=df, lookback_days=min(250, len(df)))

    # Run technical analysis
    tech = TechnicalAnalyzer()
    result = tech.analyze(ctx)

    # Display
    _display_result(result, symbol)

def _display_result(result, symbol: str):
    color = "green" if result.score > 0.3 else ("red" if result.score < -0.3 else "yellow")
    panel = Panel(
        f"[{color}]综合评分: {result.score:+.1f}[/{color}] | 置信度: {result.confidence:.0%}",
        title=f"[bold]{symbol} 技术分析[/bold]",
        border_style=color,
    )
    console.print(panel)
    console.print(f"[dim]{result.summary}[/dim]")
    console.print()

    if result.signals:
        table = Table(title="信号明细")
        table.add_column("信号", style="cyan")
        table.add_column("方向")
        table.add_column("强度")
        table.add_column("说明")

        for s in result.signals:
            dir_emoji = "🟢" if s.direction == "bullish" else ("🔴" if s.direction == "bearish" else "⚪")
            table.add_row(s.name, dir_emoji, f"{s.strength:.0%}", s.description)

        console.print(table)

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]⚠ {w}[/yellow]")
