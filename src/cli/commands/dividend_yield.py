from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import click
import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

from src.analysis.dividend_yield import (
    DividendYieldSummary,
    validate_daily,
    validate_dividends,
    recover_raw_prices,
    compute_dividend_yield,
    summarize,
)
from src.data.base import Market
from src.utils.ticker import parse_ticker, stock_dir

console = Console()

DATA_DIR = Path("data/stock/cn")


def _load_data(dir_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_path = DATA_DIR / dir_name / "daily.parquet"
    div_path = DATA_DIR / dir_name / "dividends.parquet"

    missing = []
    if not daily_path.exists():
        missing.append(str(daily_path))
    if not div_path.exists():
        missing.append(str(div_path))
    if missing:
        console.print("[red]缺少数据文件:[/red]")
        for m in missing:
            console.print(f"  {m}")
        console.print("[dim]请先运行 /fetch-stock <TICKER> 获取全部数据[/dim]")
        sys.exit(1)

    return pd.read_parquet(daily_path), pd.read_parquet(div_path)


def _run_validation(daily: pd.DataFrame, divs: pd.DataFrame):
    issues = validate_daily(daily)
    issues += validate_dividends(divs, pd.Timestamp(daily["date"].iloc[-1]))

    if not issues:
        return

    fatal = [i for i in issues if i.level == "fatal"]
    warns = [i for i in issues if i.level == "warn"]

    console.print()
    if fatal:
        console.print("[bold red]数据校验失败[/bold red]")
    for w in warns:
        console.print(f"  [yellow][警告][/yellow] {w.file}: {w.message}")
    for f in fatal:
        console.print(f"  [red][致命][/red] {f.file}: {f.message}")

    if fatal:
        console.print()
        console.print("[dim]建议重新抓取数据: /fetch-stock <TICKER>[/dim]")
        sys.exit(1)


def _filter_dates(daily: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date")

    if start:
        daily = daily[daily["date"] >= pd.Timestamp(start)]
    if end:
        daily = daily[daily["date"] <= pd.Timestamp(end)]

    if len(daily) == 0:
        console.print("[red]指定日期范围内无数据[/red]")
        sys.exit(1)

    return daily.reset_index(drop=True)


def _output_summary(s: DividendYieldSummary):
    table = Table(title="股息率统计摘要 (TTM)")
    table.add_column("指标", style="cyan")
    table.add_column("值", justify="right")

    table.add_row("当前股息率", f"{s.current:.2f}%")
    table.add_row("历史最高", f"{s.max_val:.2f}% ({s.max_date[:10]})")
    table.add_row("历史最低", f"{s.min_val:.2f}% ({s.min_date[:10]})")
    table.add_row("均值", f"{s.mean:.2f}%")
    table.add_row("中位数", f"{s.median:.2f}%")
    table.add_row("当前分位", f"{s.percentile:.1f}%")

    console.print(table)


def _output_list(
    dates: np.ndarray, close: np.ndarray, ttm_dps: np.ndarray,
    yield_pct: np.ndarray, fmt: str, out_dir: Path, ts: str,
):
    rows = []
    for i in range(len(dates)):
        rows.append({
            "date": str(dates[i])[:10],
            "close": round(float(close[i]), 4),
            "ttm_dividend": round(float(ttm_dps[i]), 4),
            "yield_pct": round(float(yield_pct[i]), 4),
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"dividend_yield_{ts}.{fmt}"
    if fmt == "json":
        import json
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        pd.DataFrame(rows).to_csv(path, index=False)
    console.print(f"[green]列表已导出: {path}[/green]")


def _output_chart(
    dates: np.ndarray,
    yield_pct: np.ndarray,
    ticker: str,
    fmt: str,
    out_dir: Path,
    ts: str,
):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        console.print("[red]需要 matplotlib 库生成图表[/red]")
        return

    plt.rcParams["font.family"] = ["Heiti TC", "Arial Unicode MS", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(14, 5))

    dts = [pd.Timestamp(d) for d in dates]
    ax.fill_between(dts, yield_pct, alpha=0.12, color="#c0392b")
    ax.plot(dts, yield_pct, linewidth=0.7, color="#c0392b")

    latest_d = dts[-1]
    latest_y = yield_pct[-1]
    ax.annotate(
        f"{latest_y:.2f}%", xy=(latest_d, latest_y),
        xytext=(15, 10), textcoords="offset points",
        fontsize=10, fontweight="bold", color="#c0392b",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85),
    )

    ax.set_title(f"{ticker} 股息率 TTM", fontsize=13, fontweight="bold")
    ax.set_ylabel("股息率 (%)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"dividend_yield_{ts}.{fmt}"
    if fmt == "pdf":
        plt.savefig(path)
    elif fmt == "svg":
        plt.savefig(path)
    else:
        plt.savefig(path, dpi=150)

    plt.close()
    console.print(f"[green]图表已保存: {path}[/green]")


@click.command()
@click.argument("ticker")
@click.option("--start", default=None, help="起始日期 YYYY-MM-DD")
@click.option("--end", default=None, help="结束日期 YYYY-MM-DD")
@click.option(
    "--output", "-o",
    type=click.Choice(["summary", "list", "chart", "all"]),
    default="all",
    help="输出模式 (默认 all)",
)
@click.option(
    "--format", "-f",
    type=click.Choice(["csv", "json", "svg", "png", "pdf"]),
    default="png",
    help="文件格式 (list: csv/json, chart: svg/png/pdf, 默认 png)",
)
@click.option(
    "--output-path", "-p",
    default=None,
    help="输出目录 (默认: data/stock/cn/<TICKER>/out/)",
)
def dividend_yield(
    ticker: str, start: str | None, end: str | None,
    output: str, format: str, output_path: str | None,
):
    """股息率曲线分析 — TTM 股息率时间序列、统计摘要与可视化.

    需先拉取数据: /fetch-stock <TICKER>
    """
    symbol, market = parse_ticker(ticker)
    if market != Market.CN:
        console.print("[red]股息率分析目前仅支持A股[/red]")
        return

    dir_name = stock_dir(symbol)
    console.print(f"[bold blue]股息率分析: {dir_name}[/bold blue]")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if output_path:
        out_dir = Path(output_path)
    else:
        out_dir = DATA_DIR / dir_name / "out"

    # ——— 加载 ———
    daily, divs = _load_data(dir_name)

    # ——— 校验 ———
    _run_validation(daily, divs)

    # ——— 过滤日期 ———
    daily = _filter_dates(daily, start, end)

    # ——— 反推价格 ———
    raw_prices, scale_factors = recover_raw_prices(daily, divs)

    if (raw_prices < 0).any():
        n_neg = (raw_prices < 0).sum()
        neg_dates = daily["date"].values[raw_prices < 0]
        console.print(f"[red]反推后 {n_neg} 个价格为负 ({neg_dates[0]} ~ {neg_dates[-1]}), 分红数据可能不完整[/red]")
        console.print("[dim]请重新拉取分红数据: /fetch-stock <TICKER>[/dim]")
        sys.exit(1)

    # ——— 计算 ———
    yield_pct, ttm_dps = compute_dividend_yield(daily, divs, raw_prices, scale_factors)

    dates = daily["date"].values
    close = raw_prices

    # ——— 输出 ———
    s = summarize(dates, yield_pct, ttm_dps, raw_prices)

    if output in ("summary", "all"):
        console.print()
        _output_summary(s)

    if output in ("list", "all"):
        console.print()
        list_fmt = format if format in ("csv", "json") else "csv"
        _output_list(dates, close, ttm_dps, yield_pct, list_fmt, out_dir, ts)

    if output in ("chart", "all"):
        console.print()
        chart_fmt = format if format in ("svg", "png", "pdf") else "png"
        _output_chart(dates, yield_pct, ticker, chart_fmt, out_dir, ts)

    console.print()
    console.print(f"[dim]TTM 股息率: {s.current:.2f}%  分位: {s.percentile:.1f}%[/dim]")
