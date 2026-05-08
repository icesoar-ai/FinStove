from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.base import Market
from src.data.cache import DataCache
from src.data.registry import ProviderRegistry
from src.track import load_records, review_ticker, compute_stats
from src.utils.ticker import parse_ticker

console = Console()


@click.command()
@click.argument("ticker")
def review(ticker: str):
    """回顾历史判断 — 对比历史分析记录与实际走势，计算胜率与偏差度.

    每次 /full-report 自动保存判断记录，积累数据后回测更可靠。
    """
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
