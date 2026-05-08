import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.base import AnalysisContext
from src.analysis.macro import MacroAnalyzer
from src.data.base import Market as MktEnum
from src.data.cache import DataCache
from src.data.models import Ticker as TickerModel
from src.data.macro_data import get_all_macro_data

console = Console()


@click.command()
@click.option("--country", default="cn,us", help="Countries to check (comma-separated)")
def macro_check(country: str):
    """Macro environment assessment."""
    countries = [c.strip().upper() for c in country.split(",")]
    console.print(f"[bold blue]Macro Check: {', '.join(countries)}[/bold blue]")

    # Fetch all macro data from CN + US sources
    macro_data = get_all_macro_data()

    if not macro_data or all(not v for v in macro_data.values()):
        console.print("[red]No macro data available.[/red]")
        console.print("[yellow]Hint: Set FRED_API_KEY env var for US data (https://fred.stlouisfed.org/docs/api/api_key.html)[/yellow]")
        return

    tk = TickerModel(raw="MACRO", market=MktEnum.CN, symbol="MACRO")
    ctx = AnalysisContext(ticker=tk, macro_data=macro_data)
    analyzer = MacroAnalyzer()
    result = analyzer.analyze(ctx)

    color = "green" if result.score > 0.3 else ("red" if result.score < -0.3 else "yellow")
    panel = Panel(
        f"[{color}]综合评分：{result.score:+.1f}[/{color}] | 置信度：{result.confidence:.0%}",
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

    # Display raw data summary
    console.print("\n[bold]数据摘要:[/bold]")
    if macro_data.get("policy_rate"):
        for c, v in macro_data["policy_rate"].items():
            console.print(f"  {c} 政策利率：{v:.2f}%")
    if macro_data.get("cpi_yoy"):
        for c, v in macro_data["cpi_yoy"].items():
            console.print(f"  {c} CPI 同比：{v:.1f}%")
    if macro_data.get("gdp_growth"):
        for c, v in macro_data["gdp_growth"].items():
            console.print(f"  {c} GDP 增速：{v:.1f}%")
    if macro_data.get("pmi"):
        for c, v in macro_data["pmi"].items():
            console.print(f"  {c} PMI: {v:.1f}")
    if macro_data.get("yield_curve"):
        for c, curve in macro_data["yield_curve"].items():
            if curve:
                s10y = curve.get("10Y", "N/A")
                s2y = curve.get("2Y", "N/A")
                if s10y and s2y:
                    spread = float(s10y) - float(s2y)
                    console.print(f"  {c} 收益率曲线：10Y={s10y:.2f}%, 2Y={s2y:.2f}%, 利差={spread:+.2f}%")
    if macro_data.get("dxy"):
        console.print(f"  美元指数 (DXY): {macro_data['dxy']:.1f}")
    if macro_data.get("crypto"):
        for coin, data in macro_data["crypto"].items():
            if data.get("price"):
                chg = data.get("change_24h")
                chg_str = f"{chg:+.1f}%" if chg else "N/A"
                console.print(f"  {coin.upper()}: ${data['price']:,.0f} (24h {chg_str})")

    # ---- Commodities ----
    if macro_data.get("gold"):
        console.print(f"  黄金 (COMEX): ${macro_data['gold']:,.1f}")
    if macro_data.get("oil_wti") or macro_data.get("oil_brent"):
        parts = []
        if macro_data.get("oil_wti"):
            parts.append(f"WTI ${macro_data['oil_wti']:,.1f}")
        if macro_data.get("oil_brent"):
            parts.append(f"Brent ${macro_data['oil_brent']:,.1f}")
        console.print(f"  原油: {' | '.join(parts)}")

    # ---- Forex snapshot ----
    if macro_data.get("forex"):
        forex_names = {"USDCNY": "美元/人民币", "EURCNY": "欧元/人民币", "JPYCNY": "日元/人民币"}
        for pair, rate in macro_data["forex"].items():
            label = forex_names.get(pair, pair)
            console.print(f"  {label}: {rate:.4f}")

    # ---- Global indices ----
    if macro_data.get("global_indices"):
        index_names = {
            "us_SPX": "S&P 500", "us_NDX": "Nasdaq", "hk_HSI": "恒生指数",
            "jp_N225": "日经225", "de_DAX": "DAX 40", "uk_FTSE": "FTSE 100", "fr_CAC": "CAC 40",
        }
        console.print("  全球指数:")
        for key, val in macro_data["global_indices"].items():
            label = index_names.get(key, key)
            console.print(f"    {label}: {val:,.0f}")
