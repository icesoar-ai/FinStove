import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.base import AnalysisContext
from src.analysis.macro import MacroAnalyzer
from src.data.base import Market as MktEnum
from src.data.cache import DataCache
from src.data.models import Ticker as TickerModel
from src.data.registry import ProviderRegistry

console = Console()


@click.command()
@click.option("--country", default="cn,us", help="Countries to check (comma-separated)")
def macro_check(country: str):
    """Macro environment assessment."""
    countries = [c.strip().upper() for c in country.split(",")]
    console.print(f"[bold blue]Macro Check: {', '.join(countries)}[/bold blue]")

    cache = DataCache()
    registry = ProviderRegistry(cache)
    macro_data: dict = {}

    for c in countries:
        try:
            if c == "CN":
                cpi_df = registry.akshare.get_cpi()
                if not cpi_df.empty and "今值" in cpi_df.columns:
                    last_val = cpi_df["今值"].dropna().iloc[-1]
                    macro_data.setdefault("cpi_yoy", {})["CN"] = float(last_val)

                pmi_df = registry.akshare.get_pmi()
                if not pmi_df.empty and "今值" in pmi_df.columns:
                    last_val = pmi_df["今值"].dropna().iloc[-1]
                    macro_data.setdefault("pmi", {})["CN"] = float(last_val)

                shibor_df = registry.akshare.get_shibor()
                if not shibor_df.empty and "今值" in shibor_df.columns:
                    on_val = shibor_df.iloc[0]["今值"]
                    macro_data.setdefault("shibor", {})["ON"] = float(on_val)

        except Exception as e:
            console.print(f"[yellow]Warning: {c} macro data fetch error: {e}[/yellow]")

    if not macro_data:
        console.print("[red]No macro data available.[/red]")
        return

    tk = TickerModel(raw="MACRO", market=MktEnum.CN, symbol="MACRO")
    ctx = AnalysisContext(ticker=tk, macro_data=macro_data)
    analyzer = MacroAnalyzer()
    result = analyzer.analyze(ctx)

    color = "green" if result.score > 0.3 else ("red" if result.score < -0.3 else "yellow")
    panel = Panel(
        f"[{color}]综合评分: {result.score:+.1f}[/{color}] | 置信度: {result.confidence:.0%}",
        title="[bold]宏观环境评估[/bold]",
        border_style=color,
    )
    console.print(panel)
    console.print(f"[dim]{result.summary}[/dim]")

    if result.signals:
        table = Table(title="宏观信号")
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
            console.print(f"[yellow]Warning: {w}[/yellow]")
