"""News sentiment analysis — NLP scoring + visualization."""
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.sentiment import _compute_sentiment
from src.utils.ticker import parse_ticker

console = Console()


def _color_score(s: float) -> str:
    if s > 0.2:
        return "green"
    elif s < -0.2:
        return "red"
    return "yellow"


@click.command("sentiment")
@click.argument("ticker")
@click.option("--days", "-d", default=7, help="回溯天数 (默认7)")
def sentiment(ticker: str, days: int):
    """新闻情绪分析 — NLP情感打分.

    抓取个股新闻 + 宏观政策新闻，jieba分词 + 金融情感词典打分。
    """
    symbol, market = parse_ticker(ticker)
    gw = DataGateway()

    console.print(f"[bold]新闻情绪分析: {ticker} (近 {days} 天)[/bold]\n")

    news_items = gw.get_news(symbol, days=days)
    if not news_items:
        console.print("[yellow]未获取到新闻数据[/yellow]")
        return

    # Compute sentiment
    for n in news_items:
        text = f"{n.title} {n.summary}"
        n.sentiment_score = _compute_sentiment(text)

    scores = [n.sentiment_score for n in news_items if n.sentiment_score is not None]
    if not scores:
        console.print("[yellow]无有效情感数据[/yellow]")
        return

    avg = sum(scores) / len(scores)
    pos_count = sum(1 for s in scores if s > 0.1)
    neg_count = sum(1 for s in scores if s < -0.1)
    neutral_count = len(scores) - pos_count - neg_count

    mood = "乐观" if avg > 0.3 else ("悲观" if avg < -0.3 else "中性")
    panel = Panel.fit(
        f"综合情绪: [{_color_score(avg)}]{avg:+.2f}[/] ({mood})  |  "
        f"[green]正面 {pos_count}[/] / [dim]中性 {neutral_count}[/] / [red]负面 {neg_count}[/]  |  "
        f"共 {len(scores)} 条新闻",
        border_style=_color_score(avg))
    console.print(panel)

    # News table
    tbl = Table(title=f"{ticker} 新闻 ({days}天)")
    tbl.add_column("时间", style="cyan")
    tbl.add_column("标题", style="bold", max_width=50)
    tbl.add_column("情绪", justify="right")
    tbl.add_column("来源", style="dim")

    for n in sorted(news_items, key=lambda x: x.date, reverse=True):
        if n.sentiment_score is None:
            continue
        s = n.sentiment_score
        lbl = f"[{_color_score(s)}]{s:+.2f}[/]"
        date_str = n.date.strftime("%m-%d %H:%M") if n.date else ""
        tbl.add_row(date_str, n.title[:50], lbl, n.source)

    console.print(tbl)
