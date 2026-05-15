"""Multi-market overview scan — trends across all asset classes from Parquet data."""
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from datetime import date, timedelta

from src.data.storage import ParquetStorage
from src.data.gateway import DataGateway

console = Console()

# Scan targets: (asset_type, market, symbol, label, group)
SCAN_TARGETS = [
    # Global indices
    ("index", "us", "SPX", "S&P 500", "美股"),
    ("index", "us", "NDX", "Nasdaq", "美股"),
    ("index", "us", "DJI", "Dow Jones", "美股"),
    ("index", "us", "RUT", "Russell 2000", "美股"),
    ("index", "hk", "HSI", "恒生指数", "港股"),
    ("index", "jp", "N225", "日经225", "亚太"),
    ("index", "de", "DAX", "DAX 40", "欧洲"),
    ("index", "uk", "FTSE", "FTSE 100", "欧洲"),
    ("index", "fr", "CAC", "CAC 40", "欧洲"),
    # Commodities
    ("commodity", "global", "GC", "黄金", "商品"),
    ("commodity", "global", "CL", "WTI原油", "商品"),
    ("commodity", "global", "BZ", "布伦特原油", "商品"),
    ("commodity", "global", "HG", "铜", "商品"),
    ("commodity", "global", "SI", "白银", "商品"),
    ("commodity", "global", "NG", "天然气", "商品"),
    # Forex
    ("forex", "global", "DXY", "美元指数", "外汇"),
    ("forex", "global", "USDCNY", "美元/人民币", "外汇"),
    ("forex", "global", "EURUSD", "欧元/美元", "外汇"),
    ("forex", "global", "USDJPY", "美元/日元", "外汇"),
    # Crypto
    ("crypto", "global", "BTC", "Bitcoin", "加密货币"),
    ("crypto", "global", "ETH", "Ethereum", "加密货币"),
]


def _get_performance(asset_type: str, market: str, symbol: str) -> dict | None:
    """Read latest prices and compute returns."""
    storage = ParquetStorage()
    try:
        df = storage.load(asset_type, market, symbol, "daily")
        if df is None or df.empty or "close" not in df.columns:
            return None

        close = df["close"].astype(float)
        latest = float(close.iloc[-1])
        ret = {}

        if len(close) >= 2:
            ret["1d"] = float(close.iloc[-1] / close.iloc[-2] - 1) * 100
        if len(close) >= 6:
            ret["5d"] = float(close.iloc[-1] / close.iloc[-6] - 1) * 100
        if len(close) >= 21:
            ret["1m"] = float(close.iloc[-1] / close.iloc[-21] - 1) * 100
        if len(close) >= 63:
            ret["3m"] = float(close.iloc[-1] / close.iloc[-63] - 1) * 100
        if len(close) >= 126:
            ret["6m"] = float(close.iloc[-1] / close.iloc[-126] - 1) * 100

        # Trend: above/below MA
        if len(close) >= 200:
            ma50 = float(close.tail(50).mean())
            ma200 = float(close.tail(200).mean())
            ret["trend"] = "↑" if close.iloc[-1] > ma200 else "↓"
            ret["ma_state"] = "强" if ma50 > ma200 else "弱"

        return {"price": latest, **ret}
    except Exception:
        return None


@click.command()
@click.option("--group", default=None, help="分组过滤: 美股/港股/亚太/欧洲/商品/外汇/加密货币")
def market_scan(group: str = None):
    """多市场概览扫描 — 各资产类别近期表现和趋势.

    读取已拉取的 Parquet 数据，展示涨跌幅和均线趋势。
    """
    console.print("[bold blue]Market Scan: 多市场概览[/bold blue]")
    console.print(f"[dim]数据截止: {date.today()}[/dim]\n")

    groups: dict[str, list] = {}
    for asset_type, market, symbol, label, grp in SCAN_TARGETS:
        if group and grp != group:
            continue
        perf = _get_performance(asset_type, market, symbol)
        if perf:
            groups.setdefault(grp, []).append((label, perf))

    if not groups:
        console.print("[yellow]无数据。请先运行 /fetch-all 拉取各品种日线。[/yellow]")
        return

    for grp, items in groups.items():
        table = Table(title=f"[bold]{grp}[/bold]")
        table.add_column("品种")
        table.add_column("价格")
        table.add_column("1日")
        table.add_column("5日")
        table.add_column("1月")
        table.add_column("3月")
        table.add_column("6月")
        table.add_column("趋势")

        for label, p in items:
            price_str = f"{p['price']:,.1f}" if label not in ("美元/日元", "美元/人民币") else f"{p['price']:,.4f}"

            def _color(v):
                if v is None:
                    return ("-", "white")
                s = f"{v:+.1f}%"
                c = "green" if v > 0 else "red"
                return (s, c)

            d1, d1c = _color(p.get("1d"))
            d5, d5c = _color(p.get("5d"))
            d1m, d1mc = _color(p.get("1m"))
            d3m, d3mc = _color(p.get("3m"))
            d6m, d6mc = _color(p.get("6m"))
            trend = p.get("trend", "-")
            trend_c = "green" if trend == "↑" else "red" if trend == "↓" else "white"

            table.add_row(
                label, price_str,
                f"[{d1c}]{d1}[/{d1c}]",
                f"[{d5c}]{d5}[/{d5c}]",
                f"[{d1mc}]{d1m}[/{d1mc}]",
                f"[{d3mc}]{d3m}[/{d3mc}]",
                f"[{d6mc}]{d6m}[/{d6mc}]",
                f"[{trend_c}]{trend}[/{trend_c}]",
            )
        console.print(table)
        console.print()

    # CN indices summary (from AKShare if available)
    console.print("[bold]A股指数[/bold]")
    try:
        cn_indexes = [
            ("000001", "上证指数"), ("399001", "深证成指"), ("000300", "沪深300"),
            ("399006", "创业板指"), ("000688", "科创50"), ("000016", "上证50"),
        ]
        gw = DataGateway()
        from src.data.base import Market
        for code, name in cn_indexes:
            df = gw.get_index(Market.CN, code)
            if df is not None and not df.empty and "close" in df.columns:
                close = df["close"].astype(float)
                latest = float(close.iloc[-1])
                chg_pct = close.pct_change().iloc[-1] * 100 if len(close) >= 2 else 0
                chg_c = "green" if chg_pct > 0 else "red"
                trend = "↑" if len(close) >= 50 and close.iloc[-1] > close.tail(50).mean() else "↓"
                console.print(f"  {name:8s}  {latest:>10,.1f}  [{chg_c}]{chg_pct:+.1f}%[/{chg_c}]  [{trend}]")
    except Exception:
        pass

    console.print("\n[dim]提示: 数据来自已拉取的 Parquet 文件，先运行 /fetch-all 更新。[/dim]")
