from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.base import Market
from src.data.cache import DataCache
from src.data.registry import ProviderRegistry
from src.utils.ticker import parse_ticker
from src.cli.commands.stock import analyze_stock
from src.cli.commands.macro import macro_check
from src.cli.commands.financials import financials
from src.cli.commands.valuation import valuation

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """金融分析助手 CLI."""


@cli.command("ohlcv")
@click.argument("ticker")
@click.option("--start", default="2010-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
def ohlcv(ticker: str, start: str, end: str):
    """Fetch daily OHLCV bars for a ticker."""
    end = end or date.today().strftime("%Y-%m-%d")
    symbol, market = parse_ticker(ticker)
    cache = DataCache()
    registry = ProviderRegistry(cache)
    from src.utils.ticker import stock_dir
    dir_name = stock_dir(symbol) if market == Market.CN else symbol

    console.print(f"[bold]Fetching {dir_name} (market={market.value})[/bold]")

    try:
        if market == Market.CN:
            start_fmt = start.replace("-", "") if "-" in start else start
            end_fmt = end.replace("-", "") if "-" in end else end
            df = registry.akshare.get_daily(symbol, start_fmt, end_fmt, dir_name=dir_name)
        else:
            df = registry.yfinance.get_daily(symbol, market.value, start, end)

        if df is None or df.empty:
            console.print("[red]No data returned.[/red]")
            raise SystemExit(1)

        console.print(f"[green]{len(df)} rows[/green]")

        table = Table(title=f"{dir_name} OHLCV")
        table.add_column("Date", style="cyan")
        table.add_column("Open", justify="right")
        table.add_column("High", justify="right")
        table.add_column("Low", justify="right")
        table.add_column("Close", justify="right")
        table.add_column("Volume", justify="right")

        for _, row in df.tail(20).iterrows():
            table.add_row(
                str(row.get("date", "")),
                f"{row.get('open', 0):.2f}",
                f"{row.get('high', 0):.2f}",
                f"{row.get('low', 0):.2f}",
                f"{row.get('close', 0):.2f}",
                f"{row.get('volume', 0):,}",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@cli.command()
@click.argument("ticker")
@click.option("--context", default="long_term", help="Analysis context: long_term, short_term")
@click.option("--format", default="standard", help="Report format: brief, standard, full")
def full_report(ticker: str, context: str, format: str):
    """Comprehensive multi-dimension analysis report."""
    from datetime import datetime
    from rich.panel import Panel
    from src.analysis.base import AnalysisContext
    from src.analysis.technical import TechnicalAnalyzer
    from src.analysis.macro import MacroAnalyzer
    from src.analysis.sentiment import SentimentAnalyzer
    from src.analysis.risk import RiskAnalyzer
    from src.analysis.benchmark import BenchmarkAnalyzer
    from src.analysis.scenario import ScenarioAnalyzer
    from src.analysis.capital_flow import CapitalFlowAnalyzer
    from src.analysis.correlation import CorrelationAnalyzer
    from src.analysis.policy import PolicyAnalyzer
    from src.data.models import Ticker as TickerModel
    from src.integration.scorer import WeightedScorer
    from src.integration.aggregator import Aggregator
    from src.integration.report import ReportBuilder
    from src.track import save_record, TrackRecord

    symbol, market = parse_ticker(ticker)
    cache = DataCache()
    registry = ProviderRegistry(cache)
    from src.utils.ticker import stock_dir
    dir_name = stock_dir(symbol) if market == Market.CN else symbol

    console.print(f"[bold blue]Full Report: {symbol} (market={market.value}, context={context})[/bold blue]")

    # Fetch price data
    end = date.today().strftime("%Y-%m-%d")
    try:
        if market == Market.CN:
            df = registry.akshare.get_daily(symbol, "20200101", end.replace("-", ""), dir_name=dir_name)
        else:
            df = registry.yfinance.get_daily(symbol, market.value, "2020-01-01", end)
        if df is None or df.empty:
            console.print("[red]No price data.[/red]")
            return
        console.print(f"[dim]{len(df)} bars loaded[/dim]")
    except Exception as e:
        console.print(f"[red]Price data error: {e}[/red]")
        return

    # Fetch macro data for CN
    macro_data = {}
    try:
        cpi_df = registry.akshare.get_cpi()
        if not cpi_df.empty and "今值" in cpi_df.columns:
            macro_data.setdefault("cpi_yoy", {})["CN"] = float(cpi_df["今值"].dropna().iloc[-1])
        pmi_df = registry.akshare.get_pmi()
        if not pmi_df.empty and "今值" in pmi_df.columns:
            macro_data.setdefault("pmi", {})["CN"] = float(pmi_df["今值"].dropna().iloc[-1])
    except Exception:
        pass

    # Fetch financial data
    financials = {}
    try:
        financials = registry.akshare.get_financials(symbol, dir_name=dir_name)
    except Exception:
        pass

    tk = TickerModel(raw=ticker, market=market, symbol=symbol)
    ctx = AnalysisContext(ticker=tk, price_data=df, macro_data=macro_data, financials=financials)

    # Run all analyzers
    analyzers = [
        TechnicalAnalyzer(), MacroAnalyzer(), SentimentAnalyzer(),
        CapitalFlowAnalyzer(), CorrelationAnalyzer(), PolicyAnalyzer(),
        RiskAnalyzer(), BenchmarkAnalyzer(), ScenarioAnalyzer(),
    ]

    results = []
    for analyzer in analyzers:
        try:
            result = analyzer.analyze(ctx)
            if result.signals:
                results.append(result)
        except Exception as e:
            console.print(f"[yellow]{analyzer.dimension.value} error: {e}[/yellow]")

    if not results:
        console.print("[red]No analysis could be completed.[/red]")
        return

    # Score and aggregate
    scorer = WeightedScorer(context)
    score_result = scorer.score(results)
    aggregator = Aggregator()
    judgment = aggregator.aggregate(symbol, score_result, results)

    # Build report
    report = ReportBuilder().build(judgment, format)
    console.print(Panel(report, title=f"[bold]{symbol} 综合分析[/bold]", border_style="blue"))

    # Save tracking record
    try:
        current_price = float(df["close"].iloc[-1])
        rec = TrackRecord(
            id=f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            ticker=symbol,
            timestamp=datetime.now(),
            composite_score=judgment.composite_score,
            tier=judgment.tier,
            dimension_scores=judgment.dimension_scores,
            current_price=current_price,
        )
        save_record(rec)
        console.print("[dim]分析结果已保存[/dim]")
    except Exception:
        pass


@cli.command()
@click.argument("ticker")
def review(ticker: str):
    """Review historical predictions for a ticker."""
    from rich.table import Table
    from src.track import load_records, review_ticker, compute_stats

    symbol, market = parse_ticker(ticker)
    records = load_records(symbol)

    if not records:
        console.print(f"[yellow]No records found for {symbol}[/yellow]")
        return

    # Fetch current price
    cache = DataCache()
    registry = ProviderRegistry(cache)
    current_price = 0.0
    try:
        if market == Market.CN:
            df = registry.akshare.get_daily(symbol, "20250101", date.today().strftime("%Y%m%d"))
        else:
            df = registry.yfinance.get_daily(symbol, market.value, "2025-01-01")
        if df is not None and not df.empty:
            current_price = float(df["close"].iloc[-1])
    except Exception:
        pass

    reviews = review_ticker(symbol, current_price, min_days=7)
    stats = compute_stats(records, reviews)

    console.print(f"[bold]{symbol} 预测回顾[/bold]")
    console.print(f"当前价格: {current_price:.2f} | 预测总数: {stats['total_predictions']} | 已回测: {stats['reviewed']}")
    if stats["reviewed"] > 0:
        console.print(f"准确率: {stats['accuracy']:.0%} | 平均收益: {stats['avg_return']:+.2%}")

    if reviews:
        table = Table(title="历史预测 vs 实际")
        table.add_column("日期")
        table.add_column("评分")
        table.add_column("判断")
        table.add_column("当时价格")
        table.add_column("收益")
        table.add_column("正确?")

        for r in reviews[-10:]:
            rec = r.record
            correct_icon = "✓" if r.was_correct else ("✗" if r.was_correct is not None else "?")
            table.add_row(
                rec.timestamp.strftime("%Y-%m-%d"),
                f"{rec.composite_score:+.1f}",
                rec.tier,
                f"{rec.current_price:.2f}" if rec.current_price else "N/A",
                f"{r.price_return:+.2%}",
                correct_icon,
            )
        console.print(table)


@cli.command()
@click.argument("ticker")
@click.option("--years", default="", help="Comma-separated years, e.g. 2021,2022,2023 (default: all available)")
def reports(ticker: str, years: str):
    """Download annual reports (PDF + Markdown) from CNINFO."""
    from rich.table import Table
    from src.data.providers.cninfo import CNINFOProvider

    symbol, market = parse_ticker(ticker)
    if market.value != "cn":
        console.print("[red]年报下载仅支持A股[/red]")
        return

    year_list = None
    if years:
        year_list = [int(y.strip()) for y in years.split(",") if y.strip()]

    provider = CNINFOProvider()
    scope = f"({years})" if year_list else "(全部可用)"
    console.print(f"[bold]Fetching annual reports for {symbol} {scope}...[/bold]")

    results = provider.download_reports(symbol, years=year_list)

    if not results:
        console.print("[yellow]未找到年报[/yellow]")
        return

    table = Table(title=f"{symbol} 年报")
    table.add_column("年份")
    table.add_column("类型")
    table.add_column("标题")
    table.add_column("发布日期")
    table.add_column("PDF")
    table.add_column("MD")

    for r in results:
        pdf_icon = "[green]✓[/green]" if r["downloaded"] else "[red]✗[/red]"
        md_ok = bool(r.get("md_path"))
        md_icon = "[green]✓[/green]" if md_ok else "[dim]-[/dim]"
        kind = "摘要" if r["kind"] == "summary" else "年报"
        table.add_row(str(r["year"]), kind, r["title"][:50], r["publish_date"], pdf_icon, md_icon)

    console.print(table)

    md_count = sum(1 for r in results if r.get("md_path"))
    if md_count > 0:
        from src.utils.ticker import stock_dir
        console.print(f"\n[dim]PDF + Markdown 存储于 data/stock/cn/{stock_dir(symbol)}/reports/[/dim]")


cli.add_command(analyze_stock)
cli.add_command(macro_check)
cli.add_command(financials)
cli.add_command(valuation)


if __name__ == "__main__":
    cli()
