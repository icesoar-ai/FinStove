"""Daily data update summary report — reads latest from all Parquet datasets."""
from datetime import date, datetime, timedelta
from pathlib import Path

import click
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.colors import load_scheme, ColorScheme
from src.data.gateway import DataGateway

console = Console()

# ── dataset registry: (asset_type, market, symbol, data_type, label) ──

INDEX_SETS = [
    # CN (AKShare)
    ("index", "cn", "000001", "daily", "上证指数"),
    ("index", "cn", "399001", "daily", "深证成指"),
    ("index", "cn", "000300", "daily", "沪深300"),
    ("index", "cn", "000016", "daily", "上证50"),
    ("index", "cn", "399006", "daily", "创业板指"),
    ("index", "cn", "000688", "daily", "科创50"),
    ("index", "cn", "000905", "daily", "中证500"),
    # Global (yfinance)
    ("index", "us", "SPX", "daily", "S&P 500"),
    ("index", "us", "NDX", "daily", "Nasdaq"),
    ("index", "us", "DJI", "daily", "Dow Jones"),
    ("index", "us", "RUT", "daily", "Russell 2000"),
    ("index", "us", "VIX", "daily", "VIX"),
    ("index", "hk", "HSI", "daily", "恒生指数"),
    ("index", "jp", "N225", "daily", "日经225"),
    ("index", "uk", "FTSE", "daily", "FTSE 100"),
    ("index", "de", "DAX", "daily", "DAX 40"),
    ("index", "fr", "CAC", "daily", "CAC 40"),
]

COMMODITY_SETS = [
    ("commodity", "global", "GC", "daily", "黄金"),
    ("commodity", "global", "SI", "daily", "白银"),
    ("commodity", "global", "CL", "daily", "WTI 原油"),
    ("commodity", "global", "BZ", "daily", "Brent 原油"),
    ("commodity", "global", "NG", "daily", "天然气"),
    ("commodity", "global", "HG", "daily", "铜"),
    ("commodity", "global", "ZC", "daily", "玉米"),
    ("commodity", "global", "ZS", "daily", "大豆"),
    ("commodity", "global", "PL", "daily", "铂"),
    ("commodity", "global", "PA", "daily", "钯"),
]

FOREX_SETS = [
    ("forex", "global", "USDCNY", "daily", "美元/人民币"),
    ("forex", "global", "EURCNY", "daily", "欧元/人民币"),
    ("forex", "global", "JPYCNY", "daily", "日元/人民币"),
    ("forex", "global", "EURUSD", "daily", "欧元/美元"),
    ("forex", "global", "USDJPY", "daily", "美元/日元"),
    ("forex", "global", "GBPUSD", "daily", "英镑/美元"),
    ("forex", "global", "AUDUSD", "daily", "澳元/美元"),
    ("forex", "global", "USDCAD", "daily", "美元/加元"),
    ("forex", "global", "GBPCNY", "daily", "英镑/人民币"),
]

CRYPTO_SETS = [
    ("crypto", "global", "BTC", "daily", "Bitcoin"),
    ("crypto", "global", "ETH", "daily", "Ethereum"),
]

TREASURY_SETS = [
    ("macro", "us", "treasury_30y", "daily", "30Y"),
    ("macro", "us", "treasury_10y", "daily", "10Y"),
    ("macro", "us", "treasury_5y", "daily", "5Y"),
    ("macro", "us", "treasury_2y", "daily", "2Y"),
    ("macro", "us", "treasury_1y", "daily", "1Y"),
    ("macro", "us", "treasury_3m", "daily", "3M"),
]

FLOW_SETS = [
    # (asset_type, market, symbol, data_type, label, is_flow)
    ("flow", "cn", "northbound", "daily", "北向资金", True),
    ("flow", "cn", "southbound", "daily", "南向资金", True),
]

THRESHOLD_PCT = 2.0  # alert for changes > this %
TODAY = date.today()
# Use last trading day as reference to avoid false stale on weekends
_REFERENCE_DATE = TODAY
if TODAY.weekday() == 5:  # Saturday → use Friday
    _REFERENCE_DATE = TODAY - timedelta(days=1)
elif TODAY.weekday() == 6:  # Sunday → use Friday
    _REFERENCE_DATE = TODAY - timedelta(days=2)


def _read_latest(gw: DataGateway, asset_type: str, market: str,
                 symbol: str, data_type: str) -> dict | None:
    """Read latest row from a Parquet dataset. Returns None if missing."""
    try:
        df = gw.read(asset_type, market, symbol, data_type)
        if df is None or df.empty:
            return None

        row = df.iloc[-1]
        val = None
        if "close" in df.columns:
            val = float(row["close"])
        elif "value" in df.columns:
            val = float(row["value"])
        elif "当日成交净买额" in df.columns:
            raw = row["当日成交净买额"]
            if pd.isna(raw):
                return None
            val = float(raw)

        dt = None
        if "date" in df.columns:
            raw = row["date"]
            if hasattr(raw, "strftime"):
                dt = raw.date() if hasattr(raw, "date") else raw
            elif isinstance(raw, str):
                dt = datetime.fromisoformat(raw).date()

        prev_val = None
        if val is not None and len(df) >= 2:
            prev_row = df.iloc[-2]
            if "close" in df.columns:
                prev_val = float(prev_row["close"])
            elif "value" in df.columns:
                prev_val = float(prev_row["value"])
            elif "当日成交净买额" in df.columns:
                raw = prev_row["当日成交净买额"]
                if pd.isna(raw):
                    prev_val = None
                else:
                    prev_val = float(raw)

        return {
            "date": dt,
            "value": val,
            "prev": prev_val,
            "rows": len(df),
        }
    except Exception:
        return None


def _fmt_val(val, is_pct: bool = False, is_forex: bool = False) -> str:
    if val is None:
        return "--"
    if is_pct:
        return f"{val:.2f}%"
    if is_forex:
        return f"{val:.4f}"
    if abs(val) >= 1000:
        return f"{val:,.0f}"
    if abs(val) >= 1:
        return f"{val:,.2f}"
    return f"{val:.4f}"


_C = load_scheme()

def _change_str(cur, prev) -> tuple[str, str]:
    """Return (change_string, color_name)."""
    if cur is None or prev is None or prev == 0:
        return "    --", "dim"
    pct = (cur - prev) / prev * 100
    if abs(pct) < 0.05:
        return "  0.0%", "dim"
    return f"{pct:+.1f}%", _C.chg_color(pct)


@click.command("summary")
@click.option("--alert", is_flag=True, default=False, help="只显示涨跌幅超过 2% 的品种")
def daily_summary(alert: bool):
    """每日数据更新汇总 — 全品种最新价/涨跌幅/数据新鲜度.

    只读不抓取，涵盖指数/商品/外汇/加密货币/美债。
    """
    gw = DataGateway()
    groups = [
        ("全球指数", INDEX_SETS, {"is_forex": False, "is_pct": False, "is_flow": False}),
        ("大宗商品", COMMODITY_SETS, {"is_forex": False, "is_pct": False, "is_flow": False}),
        ("外汇", FOREX_SETS, {"is_forex": True, "is_pct": False, "is_flow": False}),
        ("加密货币", CRYPTO_SETS, {"is_forex": False, "is_pct": False, "is_flow": False}),
        ("美债", TREASURY_SETS, {"is_forex": False, "is_pct": True, "is_flow": False}),
        ("资金流向", FLOW_SETS, {"is_forex": False, "is_pct": False, "is_flow": True}),
    ]

    total_ok = 0
    total_miss = 0
    total_stale = 0
    stale_list: list[str] = []
    alerts: list[str] = []

    # ── Header ──
    header = Panel(
        f"[bold]系统日期: {TODAY.strftime('%Y-%m-%d')}[/bold]",
        title="[bold cyan]每日数据更新报告[/bold cyan]",
        subtitle=f"Parquet @ {Path.cwd() / 'data'}",
    )
    console.print(header)

    for group_name, datasets, flags in groups:
        is_forex = flags["is_forex"]
        is_pct = flags["is_pct"]
        is_flow = flags["is_flow"]
        rows = []
        ok = miss = stale = 0
        for entry in datasets:
            if is_flow:
                asset_type, market, symbol, data_type, label, _ = entry
            else:
                asset_type, market, symbol, data_type, label = entry
            info = _read_latest(gw, asset_type, market, symbol, data_type)
            if info is None or info["value"] is None:
                miss += 1
                rows.append((label, "[red]缺数据[/red]", "[dim]--[/dim]", "[dim]--[/dim]", "dim"))
                continue

            ok += 1
            cur = info["value"]
            prev = info["prev"]
            dt = info["date"]

            # Freshness (relative to last trading day)
            if dt and dt < _REFERENCE_DATE:
                stale += 1
                stale_list.append(f"{label} (最新: {dt})")
                date_str = f"[yellow]{dt.strftime('%m-%d')}[/yellow]"
            else:
                date_str = dt.strftime("%m-%d") if dt else "--"

            # Value formatting
            val_str = _fmt_val(cur, is_pct, is_forex)

            # Change (skip for flow data — show raw delta instead)
            if is_flow:
                if prev is not None and prev != 0:
                    delta = cur - prev
                    chg_str = f"{delta:+.1f}亿"
                    color = _C.up if delta > 0 else _C.down
                else:
                    chg_str, color = "    --", "dim"
            else:
                chg_str, color = _change_str(cur, prev)

            # Alert check for large moves (skip flow — % meaningless)
            if not is_flow and prev and prev != 0:
                pct = (cur - prev) / prev * 100
                if abs(pct) >= THRESHOLD_PCT:
                    alerts.append((label, pct, color))

            rows.append((label, date_str, val_str, chg_str, color))

        # Build table
        table = Table(title=f"[bold]{group_name}[/bold]  ({ok} ok, {miss} miss, {stale} stale)")
        table.add_column("名称", style="cyan")
        table.add_column("日期", style="dim")
        table.add_column("最新值", justify="right")
        table.add_column("涨跌", justify="right")

        for label, dt_str, val_str, chg_str, color in rows:
            if not color or color == "dim":
                chg_style = f"[dim]{chg_str}[/dim]"
            else:
                chg_style = f"[{color}]{chg_str}[/{color}]"
            table.add_row(label, dt_str, val_str, chg_style)

        console.print(table)

        total_ok += ok
        total_miss += miss
        total_stale += stale

    # ── Alerts ──
    if alerts:
        console.print(f"\n[bold]⚡ 异动 (>±{THRESHOLD_PCT:.0f}%)[/bold]")
        for label, pct, color in alerts:
            console.print(f"  {label}: [{color}]{pct:+.1f}%[/{color}]")

    # ── Stale summary ──
    if stale_list:
        console.print(f"\n[bold yellow]⏳ 数据未及时更新 ({len(stale_list)} 项)[/bold yellow]")
        # Group by date
        from collections import defaultdict
        by_date: dict[str, list[str]] = defaultdict(list)
        for item in stale_list:
            # item format: "label (最新: date)"
            parts = item.rsplit(" (最新: ", 1)
            label = parts[0]
            d = parts[1].rstrip(")") if len(parts) > 1 else "?"
            by_date[d].append(label)
        for d in sorted(by_date.keys(), reverse=True):
            names = ", ".join(by_date[d])
            console.print(f"  [dim]{d}: {names}[/dim]")
    else:
        console.print(f"\n[bold green]✓ 所有数据均为当日更新[/bold green]")

    # ── Footer ──
    console.print(f"\n[dim]{total_ok} 正常, {total_stale} 未更新, {total_miss} 缺失  |  {TODAY}[/dim]")
