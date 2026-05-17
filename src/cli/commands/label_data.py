"""Walk data/ tree and create __{name}.name.txt marker files for human readability."""
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from src.data.gateway import DataGateway

console = Console()

DATA_DIR = Path("data")

# ── Hardcoded name mappings (Chinese preferred) ──────────────────────────

CN_INDEX_NAMES = {
    "000001": "上证指数", "399001": "深证成指", "000300": "沪深300",
    "000016": "上证50", "399006": "创业板指", "000688": "科创50", "000905": "中证500",
}

GLOBAL_INDEX_NAMES = {
    "SPX": "标普500", "NDX": "纳斯达克综合", "DJI": "道琼斯工业",
    "RUT": "罗素2000", "VIX": "恐慌指数",
    "HSI": "恒生指数", "N225": "日经225", "FTSE": "英国富时100",
    "DAX": "德国DAX40", "CAC": "法国CAC40",
}

COMMODITY_NAMES = {
    "GC": "黄金", "SI": "白银", "CL": "WTI原油", "BZ": "布伦特原油",
    "NG": "天然气", "HG": "铜", "ZC": "玉米", "ZS": "大豆",
    "PL": "铂金", "PA": "钯金",
}

FOREX_NAMES = {
    "USDCNY": "美元/人民币", "EURCNY": "欧元/人民币", "JPYCNY": "日元/人民币",
    "EURUSD": "欧元/美元", "USDJPY": "美元/日元", "GBPUSD": "英镑/美元",
    "AUDUSD": "澳元/美元", "USDCAD": "美元/加元", "GBPCNY": "英镑/人民币",
    "DXY": "美元指数",
}

CRYPTO_NAMES = {
    "BTC": "比特币", "ETH": "以太坊", "SOL": "Solana", "BNB": "BNB",
    "XRP": "XRP", "DOGE": "狗狗币", "ADA": "Cardano", "LINK": "Chainlink", "DOT": "Polkadot",
}

MACRO_US_NAMES = {
    "gdp": "GDP", "cpi": "CPI", "fed_funds_rate": "联邦基金利率",
    "unemployment": "失业率",
    "treasury_30y": "30年期美债", "treasury_10y": "10年期美债",
    "treasury_5y": "5年期美债", "treasury_2y": "2年期美债",
    "treasury_1y": "1年期美债", "treasury_3m": "3月期美债",
}

MACRO_CN_NAMES = {
    "gdp": "GDP", "cpi": "CPI", "ppi": "PPI",
    "pmi": "制造业PMI", "caixin_pmi": "财新PMI", "non_man_pmi": "非制造业PMI",
    "money_supply": "M2货币供应", "bond_yield": "国债收益率",
    "industrial_production": "工业增加值", "retail_sales": "社会消费品零售",
    "exports_yoy": "出口同比", "imports_yoy": "进口同比",
    "shibor": "Shibor", "fx_reserves": "外汇储备", "lpr": "LPR",
}

FLOW_NAMES = {
    "northbound": "北向资金", "southbound": "南向资金",
}


def _resolve_name(gw: DataGateway, asset_type: str, market: str, code: str, refresh: bool) -> Optional[str]:
    """Resolve a human-readable name for an asset directory."""

    # ── Dynamic name lookup via Gateway ──
    if asset_type in ("stock", "etf"):
        name = gw.name(asset_type, market, code, refresh=refresh)
        return name or None

    # ── Index CN ──
    if asset_type == "index" and market == "cn":
        return CN_INDEX_NAMES.get(code)

    # ── Index global ──
    if asset_type == "index":
        return GLOBAL_INDEX_NAMES.get(code)

    # ── Forex ──
    if asset_type == "forex":
        return FOREX_NAMES.get(code)

    # ── Commodity ──
    if asset_type == "commodity":
        return COMMODITY_NAMES.get(code)

    # ── Crypto ──
    if asset_type == "crypto":
        return CRYPTO_NAMES.get(code)
    # ── Macro US ──
    if asset_type == "macro" and market == "us":
        return MACRO_US_NAMES.get(code)

    # ── Macro CN ──
    if asset_type == "macro" and market == "cn":
        return MACRO_CN_NAMES.get(code)

    # ── Flow ──
    if asset_type == "flow":
        return FLOW_NAMES.get(code)

    return None


def _existing_markers(dir_path: Path) -> set[str]:
    """Return set of existing marker filenames in a directory."""
    return {f.name for f in dir_path.glob("__*.name.txt")}


def _write_marker(dir_path: Path, name: str) -> str:
    """Write marker file. Returns 'created', 'skipped', or 'overwritten'.

    Filename: __{sanitized_name}__.name.txt
    """
    safe = name.replace(".", "-").replace(" ", "_").replace("/", "_").replace(":", "_").replace("?", "")
    filename = f"__{safe}__.name.txt"
    target = dir_path / filename

    if target.exists():
        return "skipped"

    target.write_text(name, encoding="utf-8")
    return "created"


def _collect_dirs() -> list[tuple[str, str, str, Path]]:
    """Walk data/ and yield (asset_type, market, code, dir_path) tuples."""
    results = []
    if not DATA_DIR.exists():
        return results

    for asset_dir in sorted(DATA_DIR.iterdir()):
        if not asset_dir.is_dir():
            continue
        asset_type = asset_dir.name
        for market_dir in sorted(asset_dir.iterdir()):
            if not market_dir.is_dir():
                continue
            market = market_dir.name

            for code_dir in sorted(market_dir.iterdir()):
                if not code_dir.is_dir():
                    continue
                code = code_dir.name
                results.append((asset_type, market, code, code_dir))

    return results


@click.command("label-data")
@click.option("--force", is_flag=True, default=False,
              help="Overwrite existing marker files")
@click.option("--refresh", is_flag=True, default=False,
              help="Clear name cache and re-fetch from API (for renamed stocks)")
def label_data(force: bool, refresh: bool):
    """为 data/ 下每个资产目录生成 __{简称}__.name.txt 标记文件.

    遍历 data/ 目录树，反推资产类型和市场，查中文名称后写入 marker 文件。
    A股走 AKShare，美股/港股走 yfinance，指数/商品/外汇/加密/宏观/资金流向走硬编码映射。
    文件名规范化: .→- 空格→_。
    """
    dirs = _collect_dirs()
    if not dirs:
        console.print("[yellow]No asset directories found under data/[/yellow]")
        return

    gw = DataGateway()
    stats = {"created": 0, "skipped": 0, "overwritten": 0, "no_name": 0}
    table = Table(title="label-data")
    table.add_column("Asset", style="cyan")
    table.add_column("Name")
    table.add_column("Status")

    for asset_type, market, code, dir_path in dirs:
        full = f"{asset_type}/{market}/{code}"

        # Check existing markers (skip unless --force)
        existing = _existing_markers(dir_path)
        if existing and not force:
            for m in existing:
                table.add_row(full, m.replace("__", "").replace(".name.txt", ""), "[dim]skipped[/dim]")
                stats["skipped"] += 1
            continue

        name = _resolve_name(gw, asset_type, market, code, refresh)
        if not name:
            stats["no_name"] += 1
            table.add_row(full, "—", "[yellow]no name[/yellow]")
            continue

        # Force: remove old markers
        if force and existing:
            for m in existing:
                (dir_path / m).unlink()

        status = _write_marker(dir_path, name)
        if force and status == "created":
            status = "overwritten"
        stats[status] += 1
        style = {"created": "green", "skipped": "dim", "overwritten": "bold green"}.get(status, "")
        table.add_row(full, name, f"[{style}]{status}[/{style}]")

    console.print(table)
    console.print(
        f"[green]{stats['created']} created[/green]  "
        f"[dim]{stats['skipped']} skipped[/dim]  "
        f"{stats['overwritten']} overwritten  "
        f"[yellow]{stats['no_name']} unresolved[/yellow]"
    )
