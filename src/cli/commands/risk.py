import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.base import AnalysisContext
from src.analysis.risk import RiskAnalyzer
from src.cli.colors import load_scheme as _load_cs
from src.data.gateway import DataGateway
from src.data.base import Market
from src.data.models import Ticker as TickerModel
from src.utils.ticker import parse_ticker

console = Console()

@click.command()
@click.argument("ticker")
@click.option("--start", default="2022-01-01", help="分析起始日期")
@click.option("--end", default="", help="分析截止日期")
@click.option("--market", default="auto", help="市场 (auto/cn/us/hk/jp/uk/de/fr)")
def risk_check(ticker: str, start: str, end: str, market: str):
    """风险评估 — VaR/CVaR/最大回撤/波动率/流动性风险.

    基于历史日线 OHLCV 数据，计算尾部风险、回撤深度、年化波动率、成交量流动性。
    """
    from datetime import date

    end = end or date.today().strftime("%Y-%m-%d")
    symbol, mkt = parse_ticker(ticker)

    gw = DataGateway()

    console.print(f"[bold blue]Risk Check: {symbol} (market={mkt.value})[/bold blue]")

    try:
        if mkt == Market.CN:
            start_fmt = gw._normalize_date(start)
            end_fmt = gw._normalize_date(end)
            df = gw.get_daily(symbol, mkt, start_fmt, end_fmt)
        else:
            df = gw.get_daily(symbol, mkt, start, end)

        if df is None or df.empty:
            console.print("[red]No price data available.[/red]")
            return
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        return

    tk = TickerModel(raw=ticker, market=mkt, symbol=symbol)
    ctx = AnalysisContext(ticker=tk, price_data=df)
    analyzer = RiskAnalyzer()
    result = analyzer.analyze(ctx)

    _cs = _load_cs()
    color = _cs.down if result.score < -0.4 else (_cs.warning if result.score < -0.2 else _cs.up)
    panel = Panel(
        f"[{color}]风险评分：{result.score:+.1f}[/{color}] | 置信度：{result.confidence:.0%}",
        title="[bold]风险评估[/bold]",
        border_style=color,
    )
    console.print(panel)
    console.print(f"[dim]{result.summary}[/dim]")

    if result.signals:
        table = Table(title="风险信号")
        table.add_column("信号")
        table.add_column("方向")
        table.add_column("强度")
        table.add_column("说明")
        for s in result.signals:
            emoji = "+" if s.direction == "bullish" else ("-" if s.direction == "bearish" else "0")
            table.add_row(s.name, emoji, f"{s.strength:.0%}", s.description)
        console.print(table)

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]  ⚠ {w}[/yellow]")
