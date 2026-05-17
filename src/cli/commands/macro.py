import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.base import AnalysisContext
from src.analysis.macro import MacroAnalyzer
from src.cli.colors import load_scheme as _load_cs
from src.data.base import Market as MktEnum
from src.data.models import Ticker as TickerModel
from src.data.gateway import DataGateway

console = Console()


@click.command()
@click.option("--country", default="cn,us", help="评估市场: cn,us (逗号分隔)")
def macro_check(country: str):
    """宏观环境评估 — 利率/通胀/GDP/PMI/收益率曲线/汇率/商品.

    整合 CN (AKShare) + US (FRED) 宏观数据，产出综合宏观评分。
    CN 覆盖: CPI, PPI, PMI(官方/财新/非制造业), GDP, SHIBOR, LPR, M1/M2,
             社会融资, 外汇储备, 进出口, 工业增加值, 社消零售, 失业率, 国债收益率曲线.
    """
    countries = [c.strip().upper() for c in country.split(",")]
    console.print(f"[bold blue]Macro Check: {', '.join(countries)}[/bold blue]")

    # Fetch all macro data from CN + US sources
    macro_data = DataGateway().get_macro()

    if not macro_data or all(not v for v in macro_data.values()):
        console.print("[red]No macro data available.[/red]")
        console.print("[yellow]Hint: Set FRED_API_KEY env var for US data (https://fred.stlouisfed.org/docs/api/api_key.html)[/yellow]")
        return

    tk = TickerModel(raw="MACRO", market=MktEnum.CN, symbol="MACRO")
    ctx = AnalysisContext(ticker=tk, macro_data=macro_data)
    analyzer = MacroAnalyzer()
    result = analyzer.analyze(ctx)

    color = _load_cs().score_color(result.score, 0.3)
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
    _print_data_summary(macro_data)


def _print_data_summary(md: dict):
    console.print("\n[bold]数据摘要:[/bold]")
    # --- 价格 ---
    if md.get("cpi_yoy"):
        for c, v in md["cpi_yoy"].items():
            console.print(f"  {c} CPI 同比：{v:.1f}%")
    if md.get("ppi_yoy"):
        for c, v in md["ppi_yoy"].items():
            console.print(f"  {c} PPI 同比：{v:.1f}%")
    # --- 增长 ---
    if md.get("gdp_growth"):
        for c, v in md["gdp_growth"].items():
            console.print(f"  {c} GDP 增速：{v:.1f}%")
    if md.get("industrial_production"):
        console.print(f"  CN 工业增加值同比：{md['industrial_production']:.1f}%")
    if md.get("retail_sales_growth"):
        console.print(f"  CN 社消零售同比：{md['retail_sales_growth']:.1f}%")
    # --- 利率 ---
    if md.get("policy_rate"):
        for c, v in md["policy_rate"].items():
            console.print(f"  {c} 政策利率：{v:.2f}%")
    if md.get("lpr"):
        lpr = md["lpr"]
        console.print(f"  CN LPR：1Y={lpr.get('1Y', 'N/A'):.2f}%, 5Y={lpr.get('5Y', 'N/A'):.2f}%")
    if md.get("shibor"):
        shibor = md["shibor"]
        console.print(f"  CN SHIBOR: ON={shibor.get('ON', 'N/A'):.2f}%, 1Y={shibor.get('1Y', 'N/A'):.2f}%")
    # --- 景气 ---
    if md.get("pmi") is not None:
        if isinstance(md["pmi"], dict):
            if "CN" in md["pmi"]:
                console.print(f"  CN PMI: {md['pmi']['CN']:.1f}")
            if "US" in md["pmi"]:
                console.print(f"  US PMI: {md['pmi']['US']:.1f}")
    if md.get("caixin_pmi") is not None:
        console.print(f"  CN 财新制造业PMI: {md['caixin_pmi']:.1f}")
    if md.get("non_man_pmi") is not None:
        console.print(f"  CN 非制造业PMI: {md['non_man_pmi']:.1f}")
    # --- 货币信贷 ---
    if md.get("m2_growth"):
        console.print(f"  CN M2 同比：{md['m2_growth']:.1f}%")
    if md.get("m1_growth"):
        console.print(f"  CN M1 同比：{md['m1_growth']:.1f}%")
    if md.get("social_financing"):
        console.print(f"  CN 社会融资增量：{md['social_financing']:.0f}亿")
    # --- 外贸 ---
    if md.get("exports_yoy"):
        console.print(f"  CN 出口同比：{md['exports_yoy']:+.1f}%")
    if md.get("imports_yoy"):
        console.print(f"  CN 进口同比：{md['imports_yoy']:+.1f}%")
    if md.get("fx_reserves"):
        console.print(f"  CN 外汇储备：${md['fx_reserves']:,.1f}亿")
    # --- 就业 ---
    if md.get("unemployment"):
        for c, v in md["unemployment"].items():
            console.print(f"  {c} 失业率：{v:.1f}%")
    # --- 收益率曲线 ---
    if md.get("yield_curve"):
        for c, curve in md["yield_curve"].items():
            if not curve or not isinstance(curve, dict):
                continue
            # Try to find long/short keys in both US (10Y/2Y) and CN (10年/1年) format
            keys = list(curve.keys())
            if len(keys) >= 2:
                # US format
                s10y = curve.get("10Y")
                s2y = curve.get("2Y")
                # CN format
                s10y_cn = curve.get("10年")
                s1y_cn = curve.get("1年")
                if s10y is not None and s2y is not None:
                    spread = float(s10y) - float(s2y)
                    console.print(f"  {c} 收益率曲线：10Y={s10y:.2f}%, 2Y={s2y:.2f}%, 利差={spread:+.2f}%")
                elif s10y_cn is not None and s1y_cn is not None:
                    spread = float(s10y_cn) - float(s1y_cn)
                    console.print(f"  {c} 收益率曲线：10Y={s10y_cn:.2f}%, 1Y={s1y_cn:.2f}%, 利差={spread:+.2f}%")
                else:
                    # Just show what we have
                    items = ", ".join(f"{k}={v:.2f}%" for k, v in curve.items())
                    console.print(f"  {c} 收益率曲线：{items}")
    # --- DXY ---
    if md.get("dxy"):
        console.print(f"  美元指数 (DXY): {md['dxy']:.1f}")
    # --- Crypto ---
    if md.get("crypto"):
        for coin, data in md["crypto"].items():
            if data.get("price"):
                chg = data.get("change_24h")
                chg_str = f"{chg:+.1f}%" if chg else "N/A"
                console.print(f"  {coin.upper()}: ${data['price']:,.0f} (24h {chg_str})")
    # --- Commodities ---
    if md.get("gold"):
        console.print(f"  黄金 (COMEX): ${md['gold']:,.1f}")
    if md.get("oil_wti") or md.get("oil_brent"):
        parts = []
        if md.get("oil_wti"):
            parts.append(f"WTI ${md['oil_wti']:,.1f}")
        if md.get("oil_brent"):
            parts.append(f"Brent ${md['oil_brent']:,.1f}")
        console.print(f"  原油: {' | '.join(parts)}")
    # --- Forex ---
    if md.get("forex"):
        forex_names = {"USDCNY": "美元/人民币", "EURCNY": "欧元/人民币", "JPYCNY": "日元/人民币"}
        for pair, rate in md["forex"].items():
            label = forex_names.get(pair, pair)
            console.print(f"  {label}: {rate:.4f}")
    # --- Global Indices ---
    if md.get("global_indices"):
        index_names = {
            "us_SPX": "S&P 500", "us_NDX": "Nasdaq", "hk_HSI": "恒生指数",
            "jp_N225": "日经225", "de_DAX": "DAX 40", "uk_FTSE": "FTSE 100", "fr_CAC": "CAC 40",
        }
        console.print("  全球指数:")
        for key, val in md["global_indices"].items():
            label = index_names.get(key, key)
            console.print(f"    {label}: {val:,.0f}")
