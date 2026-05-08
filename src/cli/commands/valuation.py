import re

import click
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.data.storage import ParquetStorage
from src.data.base import Market
from src.utils.ticker import parse_ticker, stock_dir
from src.analysis.fundamental.aggregator import ValuationAggregator
from src.analysis.fundamental.base import ValuationResult

console = Console()


def _augment_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Derive balance sheet items so more valuation methods work.

    Summary has: 净利润, 基本每股收益, 每股净资产, 资产负债率, 营业总收入, etc.
    Derives:    总股本, 所有者权益, 总资产, 负债合计, 流动资产(est), etc.

    Derived columns are inserted at the front so methods that scan for keyword
    matches find the absolute values before per-share variants (e.g. 所有者权益
    before 每股净资产 which also contains '净资产').
    """
    df = df.copy()
    dn = {}  # derived columns, inserted later

    # 总股本 = 净利润 / 基本每股收益
    if "净利润" in df.columns and "基本每股收益" in df.columns:
        shares = []
        for ni, eps in zip(df["净利润"].values, df["基本每股收益"].values):
            if ni and eps and eps > 0:
                shares.append(ni / eps)
            elif shares:
                shares.append(shares[-1])
            else:
                shares.append(None)
        dn["总股本"] = shares

    # 所有者权益 = 每股净资产 × 总股本
    if "每股净资产" in df.columns and "总股本" in dn:
        dn["所有者权益"] = [
            bvps * s if bvps and s else None
            for bvps, s in zip(df["每股净资产"].values, dn["总股本"])
        ]

    # 总资产 = 所有者权益 / (1 - 资产负债率)
    if "所有者权益" in dn and "资产负债率" in df.columns:
        dn["总资产"] = [
            eq / (1 - dr) if eq and dr and dr < 1 else None
            for eq, dr in zip(dn["所有者权益"], df["资产负债率"].values)
        ]

    # 负债合计 = 总资产 - 所有者权益
    if "总资产" in dn and "所有者权益" in dn:
        dn["负债合计"] = [
            ta - eq if ta and eq else None
            for ta, eq in zip(dn["总资产"], dn["所有者权益"])
        ]

    # 流动资产 ≈ 流动比率 × 流动负债
    # 流动比率 = 流动资产/流动负债. 保守估计: 流动负债 ≈ 负债合计
    if "流动比率" in df.columns and "负债合计" in dn:
        dn["流动资产"] = [
            cr * tl if cr and tl else None
            for cr, tl in zip(df["流动比率"].values, dn["负债合计"])
        ]

    # 营业利润 ≈ 营业总收入 × 销售毛利率 (conservative: use 毛利率 not 净利率)
    if "销售毛利率" in df.columns and "营业总收入" in df.columns:
        dn["营业利润"] = [
            rev * gm if rev and gm else None
            for rev, gm in zip(df["营业总收入"].values, df["销售毛利率"].values)
        ]

    # Insert derived columns at front so they're matched before per-share originals
    for key, values in dn.items():
        df.insert(0, key, values)

    return df


def _normalize_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Convert formatted strings ('2.44亿', '60.42%', '-19.26%') to floats."""
    df = df.copy()

    # Columns that are not financial metrics
    skip_cols = {"报告期", "report_date", "date", "日期"}

    for col in df.columns:
        if col in skip_cols:
            continue
        sample = df[col].dropna()
        if sample.empty:
            continue
        first = sample.iloc[0]
        if not isinstance(first, str):
            continue

        def _parse(v):
            if not isinstance(v, str):
                return v
            v = v.strip()
            if v in ("", "-", "--", "N/A", "None"):
                return None
            if v.endswith("万亿"):
                return float(v[:-2]) * 1e12
            if v.endswith("亿"):
                return float(v[:-1]) * 1e8
            if v.endswith("万"):
                return float(v[:-1]) * 1e4
            if v.endswith("%"):
                return float(v[:-1]) / 100.0
            try:
                return float(v)
            except ValueError:
                return None

        df[col] = df[col].apply(_parse)
    return df


@click.command()
@click.argument("ticker")
@click.option("--format", default="standard", help="报告格式: brief (简要) / standard (标准) / full (完整)")
def valuation(ticker: str, format: str):
    """基本面估值分析 — 10 种方法综合估值.

    FCFF / FCFE / DDM / Graham / EPV / NCAV / 剩余收益 / 倍数法 / FCF质量 / 财务健康。
    需先拉取数据: /fetch-stock <TICKER> financials
    """
    symbol, market = parse_ticker(ticker)

    if market != Market.CN:
        console.print("[red]估值分析目前仅支持A股[/red]")
        return

    dir_name = stock_dir(symbol)
    storage = ParquetStorage()

    console.print(f"[bold blue]Valuation: {dir_name}[/bold blue]")

    # Load stored data (normalize all — detailed statements may have
    # formatted strings like '250.22亿' that methods can't parse.)
    financials = {}
    for dtype in ["balance_sheet", "income", "cashflow"]:
        df = storage.load("stock", "cn", dir_name, dtype)
        if not df.empty:
            df = _normalize_summary(df)
            # Drop columns that are entirely NaN after normalization
            # (e.g. THS '六、每股收益' is a section header with no values)
            df = df.dropna(axis=1, how="all")
            financials[dtype] = df

    summary = storage.load("stock", "cn", dir_name, "financials")
    if not summary.empty:
        summary = _normalize_summary(summary)
        summary = _augment_summary(summary)
        financials["summary"] = summary

    # Load dividend history
    dividends = storage.load("stock", "cn", dir_name, "dividends")
    if not dividends.empty:
        financials["dividends"] = dividends

    # Use summary as income / balance_sheet fallback if detailed statements absent
    has_income = "income" in financials
    has_bs = "balance_sheet" in financials
    has_cf = "cashflow" in financials
    has_dividends = "dividends" in financials

    if "summary" in financials:
        if not has_income:
            financials["income"] = summary
        if not has_bs:
            financials["balance_sheet"] = summary

    # Patch: if balance_sheet 股本 is 0/NaN, use summary's derived 总股本
    if has_bs and "summary" in financials and "总股本" in summary.columns:
        bs = financials["balance_sheet"]
        shares_valid = False
        for col in bs.columns:
            col_l = str(col).lower()
            if "股本" in col_l or "share" in col_l:
                val = bs[col].iloc[-1] if len(bs) > 0 else 0
                if val is not None and val > 0:
                    shares_valid = True
                break
        if not shares_valid:
            derived = summary["总股本"].dropna()
            if len(derived) > 0:
                bs["总股本(推算)"] = float(derived.iloc[-1])

    if not financials or (not has_income and not has_bs and "summary" not in financials):
        console.print(f"[red]缺少财务数据[/red]")
        console.print(f"[dim]请先运行 /fetch-stock {ticker} 获取数据[/dim]")
        return

    available = []
    for k, label in [("balance_sheet", "资产负债表"), ("income", "利润表"), ("cashflow", "现金流量表")]:
        if k in financials:
            available.append(label)
    if "summary" in financials:
        available[-1] += f" ({len(financials['summary'])}期摘要)"
    if has_dividends:
        latest_div = dividends.iloc[-1]
        available.append(f"分红({len(dividends)}次, 最新{latest_div['派息']}元/股)")
    console.print(f"[dim]可用数据: {', '.join(available)}[/dim]")

    if not has_cf:
        console.print("[dim]缺少现金流量表，FCFF/FCFE/FCF质量方法将跳过[/dim]")

    # Load price data
    market_data = storage.load("stock", "cn", dir_name, "daily")
    if market_data.empty:
        console.print("[dim]无日线数据，相对估值缺少当前价格参考[/dim]")

    # Run all valuation methods
    financials["market"] = market
    agg = ValuationAggregator()
    results = agg.evaluate_all(financials, market_data if not market_data.empty else None)
    summary_result = agg.aggregate(results)

    _display(results, summary_result, dir_name, format)


def _display(results: list[ValuationResult], agg: dict, name: str, fmt: str):
    median = agg.get("fair_value_median")
    rng = agg.get("fair_value_range", (None, None))
    agreement = agg.get("agreement", "low")
    agreement_label = {
        "high": "高 (方法间分歧小)",
        "medium": "中",
        "low": "低 (方法间分歧大)",
    }.get(agreement, agreement)

    color = "green" if agreement == "high" else ("yellow" if agreement == "medium" else "red")

    lines = []
    if median:
        lines.append(f"合理价值中位数: [bold]{median:.2f} 元/股[/bold]")
        lines.append(f"价值区间 (25-75%分位): [{rng[0]:.2f} - {rng[1]:.2f}]")
    else:
        lines.append("[yellow]未能产生有效估值[/yellow]")
    lines.append(f"方法一致性: [{color}]{agreement_label}[/{color}]")
    lines.append(f"有效方法: {agg['methods_with_value']}/{agg['method_count']}")

    console.print(Panel("\n".join(lines), title=f"[bold]{name} 估值分析[/bold]", border_style="blue"))

    if fmt != "brief":
        table = Table(title="估值方法明细")
        table.add_column("方法", style="cyan")
        table.add_column("合理价值", justify="right")
        table.add_column("悲观", justify="right")
        table.add_column("乐观", justify="right")
        table.add_column("置信度", justify="right")
        table.add_column("假设 / 问题")

        for r in results:
            fv = f"{r.fair_value:.2f}" if r.fair_value > 0 else "—"
            vl = f"{r.value_low:.2f}" if r.value_low > 0 else "—"
            vh = f"{r.value_high:.2f}" if r.value_high > 0 else "—"
            conf = f"{r.confidence:.0%}"

            # Build note: show reason if no value, otherwise show assumptions
            if r.fair_value <= 0:
                parts = []
                if r.reason:
                    parts.append(f"[yellow]{r.reason}[/yellow]")
                if r.warnings:
                    parts.extend(r.warnings[:2])
                elif r.assumptions:
                    parts.append(", ".join(f"{k}={v}" for k, v in list(r.assumptions.items())[:3]))
                note = "; ".join(parts) if parts else ""
            else:
                if r.warnings:
                    note = "; ".join(r.warnings[:2])
                elif r.assumptions:
                    note = ", ".join(f"{k}={v}" for k, v in list(r.assumptions.items())[:4])
                else:
                    note = ""
            table.add_row(r.method, fv, vl, vh, conf, note[:70])

        console.print(table)

    if agg.get("warnings"):
        console.print()
        for w in agg["warnings"]:
            console.print(f"[yellow]⚠ {w}[/yellow]")
