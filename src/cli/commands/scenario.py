import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.base import AnalysisContext
from src.analysis.scenario import ScenarioAnalyzer
from src.data.cache import DataCache
from src.data.registry import ProviderRegistry
from src.data.base import Market
from src.data.models import Ticker as TickerModel
from src.utils.ticker import parse_ticker

console = Console()


@click.command()
@click.argument("ticker")
@click.option("--start", default="2022-01-01", help="分析起始日期")
@click.option("--end", default="", help="分析截止日期")
@click.option("--market", default="auto", help="市场 (auto/cn/us/hk/jp/uk/de/fr)")
def scenario(ticker: str, start: str, end: str, market: str):
    """情景分析 — 乐观/悲观/反转情景 + 波动率敏感性.

    基于 52 周高低点推演乐观/悲观情景，结合波动率做 1σ/2σ 敏感性区间。
    """
    from datetime import date

    end = end or date.today().strftime("%Y-%m-%d")
    symbol, mkt = parse_ticker(ticker)

    cache = DataCache()
    registry = ProviderRegistry(cache)

    console.print(f"[bold blue]Scenario Analysis: {symbol} (market={mkt.value})[/bold blue]")

    # Fetch price data
    try:
        if mkt == Market.CN:
            start_fmt = start.replace("-", "") if "-" in start else start
            end_fmt = end.replace("-", "") if "-" in end else end
            df = registry.akshare.get_daily(symbol, start_fmt, end_fmt)
        else:
            df = registry.yfinance.get_daily(symbol, mkt.value, start, end)

        if df is None or df.empty:
            console.print("[red]No price data available.[/red]")
            return
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        return

    tk = TickerModel(raw=ticker, market=mkt, symbol=symbol)
    ctx = AnalysisContext(ticker=tk, price_data=df)
    analyzer = ScenarioAnalyzer()
    result = analyzer.analyze(ctx)

    color = "green" if result.score > 0.2 else ("red" if result.score < -0.2 else "yellow")
    panel = Panel(
        f"[{color}]情景评分：{result.score:+.1f}[/{color}] | 置信度：{result.confidence:.0%}",
        title="[bold]情景分析[/bold]",
        border_style=color,
    )
    console.print(panel)
    console.print(f"[dim]{result.summary}[/dim]")

    if result.signals:
        table = Table(title="情景信号")
        table.add_column("信号")
        table.add_column("方向")
        table.add_column("强度")
        table.add_column("说明")
        for s in result.signals:
            emoji = "+" if s.direction == "bullish" else ("-" if s.direction == "bearish" else "0")
            table.add_row(s.name, emoji, f"{s.strength:.0%}", s.description)
        console.print(table)

    # Sensitivity details
    details = result.details
    if details:
        console.print("\n[bold]敏感性分析:[/bold]")
        current = details.get("current_price")
        if current:
            console.print(f"  当前价格: {current:,.2f}")
            sigma = details.get("daily_sigma", 0)
            console.print(f"  日波动率 (1σ): {sigma:.2%}")

            sensitivity_table = Table(title="价格区间推演")
            sensitivity_table.add_column("情景")
            sensitivity_table.add_column("价格")
            sensitivity_table.add_column("涨跌幅")
            for label, price in [
                ("+2σ (3月)", details.get("bull_2sigma_3m")),
                ("+1σ (1月)", details.get("bull_1sigma_1m")),
                ("当前", current),
                ("-1σ (1月)", details.get("bear_1sigma_1m")),
                ("-2σ (3月)", details.get("bear_2sigma_3m")),
            ]:
                if price and current:
                    chg = (price / current - 1)
                    chg_style = f"[green]{chg:+.1%}[/green]" if chg > 0 else f"[red]{chg:+.1%}[/red]"
                    sensitivity_table.add_row(label, f"{price:,.2f}", chg_style)
            console.print(sensitivity_table)

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]  ⚠ {w}[/yellow]")
