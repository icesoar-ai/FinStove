from datetime import date, datetime

import click
from rich.console import Console
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
from src.data.base import Market
from src.data.cache import DataCache
from src.data.models import Ticker as TickerModel
from src.data.registry import ProviderRegistry
from src.integration.scorer import WeightedScorer
from src.integration.aggregator import Aggregator
from src.integration.report import ReportBuilder
from src.track import save_record, TrackRecord
from src.utils.ticker import parse_ticker, stock_dir

console = Console()


@click.command()
@click.argument("ticker")
@click.option("--context", default="long_term", help="Analysis context: long_term, short_term")
@click.option("--format", default="standard", help="Report format: brief, standard, full")
@click.option("--context", default="long_term", help="分析场景: long_term (长期投资) / short_term (短期交易)")
@click.option("--format", default="standard", help="报告格式: brief (简要) / standard (标准) / full (完整)")
def full_report(ticker: str, context: str, format: str):
    """综合多维分析报告 — 10 维度加权评分 + 目标价 + 风险 + 情景.

    整合技术面/宏观/情绪/资金流/政策/估值/风险/基准/情景/年报文本分析。
    """
    symbol, market = parse_ticker(ticker)
    cache = DataCache()
    registry = ProviderRegistry(cache)
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

    # Fetch news for sentiment analysis
    news_data = []
    try:
        from src.data.providers.news import NewsProvider
        np_ = NewsProvider(cache=cache)
        news_data = np_.get_all_news(symbol, days=7)
        console.print(f"[dim]{len(news_data)} news items loaded[/dim]")
    except Exception:
        pass

    tk = TickerModel(raw=ticker, market=market, symbol=symbol)
    ctx = AnalysisContext(ticker=tk, price_data=df, macro_data=macro_data,
                          financials=financials, news_data=news_data)

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

    # Run report text analysis for CN stocks
    if market == Market.CN:
        try:
            from src.analysis.report_text import ReportTextAnalyzer
            rt_result = ReportTextAnalyzer().analyze(ctx)
            if rt_result.signals:
                results.append(rt_result)
        except Exception:
            pass

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
