import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.base import AnalysisContext
from src.analysis.correlation import CorrelationAnalyzer
from src.data.base import Market as MktEnum
from src.data.models import Ticker as TickerModel
from src.data.gateway import DataGateway

console = Console()


@click.command()
def correlation_check():
    """跨市场联动分析 — 黄金/DXY/VIX 信号判断 Risk-On/Risk-Off 体制."""
    console.print("[bold blue]Correlation Check: 跨市场联动[/bold blue]")

    macro_data = DataGateway().get_macro()
    if not macro_data:
        console.print("[red]No macro data available.[/red]")
        return

    tk = TickerModel(raw="CORRELATION", market=MktEnum.CN, symbol="CORRELATION")
    ctx = AnalysisContext(ticker=tk, macro_data=macro_data)
    analyzer = CorrelationAnalyzer()
    result = analyzer.analyze(ctx)

    regime = result.details.get("regime", "unknown")
    regime_color = "green" if regime == "Risk-On" else ("red" if regime == "Risk-Off" else "yellow")
    panel = Panel(
        f"[{regime_color}]跨市场体制：{regime}[/{regime_color}] | 评分：{result.score:+.1f} | 置信度：{result.confidence:.0%}",
        title="[bold]跨市场联动分析[/bold]",
        border_style=regime_color,
    )
    console.print(panel)
    console.print(f"[dim]{result.summary}[/dim]")

    if result.signals:
        table = Table(title="跨市场信号")
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
    if macro_data.get("gold"):
        console.print(f"  黄金: ${macro_data['gold']:,.1f}")
    if macro_data.get("dxy"):
        console.print(f"  DXY: {macro_data['dxy']:.1f}")
    if macro_data.get("vix"):
        console.print(f"  VIX: {macro_data['vix']:.1f}")

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]  ⚠ {w}[/yellow]")
