"""Annual report text analysis — extract metrics, audit opinion, risk factors."""
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.report_text import (
    _find_latest_report, _extract_audit, _extract_metrics,
    _extract_risk_factors, _extract_outlook,
)
from src.utils.ticker import parse_ticker, stock_dir

console = Console()


@click.command("report-analyze")
@click.argument("ticker")
def report_analyze(ticker: str):
    """年报文本分析 — 提取审计意见、关键指标、风险因素、管理层展望.

    需要先下载年报: /fetch-stock <TICKER> reports
    """
    symbol, market = parse_ticker(ticker)
    if market.value != "cn":
        console.print("[yellow]目前仅支持 A 股年报分析[/yellow]")
        return

    dir_name = stock_dir(symbol)
    report_path = _find_latest_report(dir_name)
    if report_path is None:
        console.print("[red]未找到年报 MD 文件。请先运行: /fetch-stock <TICKER> reports[/red]")
        return

    console.print(f"[bold]年报文本分析: {dir_name}[/bold]")
    console.print(f"[dim]  文件: {report_path}[/dim]\n")

    try:
        text = report_path.read_text(encoding="utf-8")
    except Exception as e:
        console.print(f"[red]文件读取失败: {e}[/red]")
        return

    # 1. Audit opinion
    audit_signals = _extract_audit(text)
    if audit_signals:
        s = audit_signals[0]
        color = "green" if s.direction == "bullish" else "red"
        panel = Panel.fit(f"[{color}]审计意见: {s.description}[/]", border_style=color)
        console.print(panel)
    else:
        console.print("[yellow]未找到审计意见[/yellow]")

    # 2. Financial metrics
    metrics = _extract_metrics(text)
    if any(v is not None for v in metrics.values()):
        mt = Table(title="关键财务指标 (文本提取)")
        mt.add_column("指标", style="bold")
        mt.add_column("报告值", justify="right")
        for label, val in metrics.items():
            if val is not None:
                yi = val / 1e8
                if yi >= 1:
                    display = f"{yi:.2f} 亿"
                else:
                    display = f"{val:,.2f}"
            else:
                display = "[dim]未提取到[/dim]"
            mt.add_row(label, display)
        console.print(mt)
    else:
        console.print("[yellow]未提取到关键财务指标[/yellow]")

    # 3. Risk factors
    risk_signals = _extract_risk_factors(text)
    if risk_signals:
        console.print("\n[bold]风险因素:[/bold]")
        for s in risk_signals:
            c = "red" if s.direction == "bearish" else "dim"
            console.print(f"  [{c}]• {s.description}[/]")

    # 4. Management outlook
    outlook_signals = _extract_outlook(text)
    if outlook_signals:
        console.print("\n[bold]管理层展望:[/bold]")
        for s in outlook_signals:
            c = "green" if s.direction == "bullish" else "red"
            console.print(f"  [{c}]• {s.description}[/]")
