"""Real-time spot quotes — global markets, movers, ticker detail, watchlist."""
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.data.cache import DataCache
from src.data.providers.akshare import AKShareProvider
from src.data.providers.coingecko import CoinGeckoProvider
from src.utils.ticker import detect_market, parse_ticker

console = Console()
CHG_STYLE = {"+": "green", "-": "red", "0": "dim"}

# ---- helpers ----

def _chg_color(val: float) -> str:
    """Return Rich style tag for change value."""
    if val > 0:
        return "green"
    elif val < 0:
        return "red"
    return "dim"


def _fmt_chg(val: float | None) -> str:
    """Format change as +X.XX% string."""
    if val is None or val != val:
        return "[dim]N/A[/dim]"
    sign = "+" if val > 0 else ""
    return f"[{_chg_color(val)}]{sign}{val:.2f}%[/]"


def _fmt_price(p: float | None) -> str:
    if p is None or p != p:
        return "[dim]N/A[/dim]"
    return f"{p:,.2f}"


def _fmt_vol(v: float | None) -> str:
    if v is None or v != v:
        return "[dim]N/A[/dim]"
    yi = v / 1e8
    if yi >= 1:
        return f"{yi:.2f} 亿"
    return f"{v/1e4:.0f} 万"


# ---- data helpers ----

def _safe_float(s) -> float | None:
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# ==== Mode: global overview ====

def _overview(ak: AKShareProvider, cg: CoinGeckoProvider):
    console.print(Panel.fit("实时行情概览", style="bold cyan"))

    # --- Indices table ---
    idx_table = Table(title="全球指数", border_style="blue")
    idx_table.add_column("名称", style="bold")
    idx_table.add_column("最新价", justify="right")
    idx_table.add_column("涨跌幅", justify="right")

    cn_keys = {"上证指数", "深证成指", "沪深300", "创业板指", "科创50", "中证500"}
    global_keys = {"道琼斯", "纳斯达克", "标普500", "恒生指数", "日经225", "英国富时100", "德国DAX30", "法国CAC40"}

    try:
        idx_df = ak.get_index_spot()
        for _, r in idx_df.iterrows():
            name = str(r.get("名称", ""))
            if name in cn_keys or name in global_keys:
                price = _safe_float(r.get("最新价"))
                chg = _safe_float(r.get("涨跌幅"))
                idx_table.add_row(name, _fmt_price(price), _fmt_chg(chg))
    except Exception as e:
        idx_table.caption = f"[red]指数数据获取失败: {e}[/red]"

    console.print(idx_table)

    # --- FX + Commodities table ---
    fxc_table = Table(title="外汇 / 商品", border_style="yellow")
    fxc_table.add_column("名称", style="bold")
    fxc_table.add_column("最新价", justify="right")
    fxc_table.add_column("涨跌幅", justify="right")

    # Forex: USDCNY + DXY
    try:
        fx_df = ak.get_forex_spot()
        targets = {"美元/人民币", "欧元/美元", "美元/日元", "英镑/美元", "美元/加元", "澳元/美元"}
        fx_df_filtered = fx_df[fx_df["名称"].isin(targets)]
        for _, r in fx_df_filtered.iterrows():
            price = _safe_float(r.get("最新价"))
            chg = _safe_float(r.get("涨跌幅"))
            fxc_table.add_row(str(r.get("名称", "")), _fmt_price(price), _fmt_chg(chg))

        # DXY from yfinance (use AKShare forex if available under "美元指数")
        dxy_row = fx_df[fx_df["名称"].str.contains("美元指数", na=False)]
        if not dxy_row.empty:
            r = dxy_row.iloc[0]
            price = _safe_float(r.get("最新价"))
            chg = _safe_float(r.get("涨跌幅"))
            fxc_table.add_row("美元指数 DXY", _fmt_price(price), _fmt_chg(chg))
    except Exception:
        pass

    # Commodities
    cmods = {"COMEX黄金": "黄金", "COMEX白银": "白银", "WTI原油": "美原油",
             "布伦特原油": "布伦特", "COMEX铜": "铜", "天然气": "天然气"}
    try:
        fut_df = ak.get_futures_spot()
        for kw, label in cmods.items():
            rows = fut_df[fut_df["名称"].str.contains(kw, na=False)]
            if not rows.empty:
                r = rows.iloc[0]
                price = _safe_float(r.get("最新价"))
                chg = _safe_float(r.get("涨跌幅"))
                fxc_table.add_row(label, _fmt_price(price), _fmt_chg(chg))
    except Exception:
        pass

    console.print(fxc_table)

    # --- Crypto table ---
    crypto_table = Table(title="加密货币", border_style="magenta")
    crypto_table.add_column("名称", style="bold")
    crypto_table.add_column("最新价", justify="right")
    crypto_table.add_column("24h涨跌", justify="right")

    for sym in ("BTC", "ETH"):
        try:
            md = cg.get_market_data(sym)
            if md:
                price = md.get("price")
                chg = md.get("change_24h")
                crypto_table.add_row(sym, _fmt_price(price), _fmt_chg(chg))
        except Exception:
            crypto_table.add_row(sym, "[dim]unavailable[/dim]", "[dim]—[/dim]")

    console.print(crypto_table)


# ==== Mode: market movers ====

def _market_movers(ak: AKShareProvider, market: str, limit: int):
    mk_label = {"cn": "A股", "hk": "港股", "us": "美股"}.get(market, market.upper())
    market_fn = {"cn": ak.get_a_share_spot, "hk": ak.get_hk_stock_spot, "us": ak.get_us_stock_spot}

    fn = market_fn.get(market)
    if fn is None:
        console.print(f"[red]不支持的市场: {market}[/red]")
        return

    try:
        df = fn()
        if df.empty:
            console.print("[yellow]暂无数据[/yellow]")
            return
    except Exception as e:
        console.print(f"[red]数据获取失败: {e}[/red]")
        return

    # Sort by 涨跌幅
    df = df.copy()
    df["_chg"] = pd.to_numeric(df.get("涨跌幅", 0), errors="coerce")
    top = df.nlargest(limit, "_chg")
    bottom = df.nsmallest(limit, "_chg")

    # Gainers
    gain_table = Table(title=f"涨幅榜 TOP{limit}", border_style="red")
    gain_table.add_column("代码", style="dim")
    gain_table.add_column("名称", style="bold")
    gain_table.add_column("最新价", justify="right")
    gain_table.add_column("涨跌幅", justify="right")
    gain_table.add_column("成交额", justify="right")

    for _, r in top.iterrows():
        code = str(r.get("代码", ""))
        name = str(r.get("名称", ""))
        price = _safe_float(r.get("最新价"))
        chg = _safe_float(r.get("涨跌幅"))
        amt = _safe_float(r.get("成交额", 0))
        gain_table.add_row(code, name, _fmt_price(price), _fmt_chg(chg),
                          _fmt_vol(amt) if market != "us" else str(amt))

    console.print(gain_table)

    # Losers
    loss_table = Table(title=f"跌幅榜 TOP{limit}", border_style="green")
    loss_table.add_column("代码", style="dim")
    loss_table.add_column("名称", style="bold")
    loss_table.add_column("最新价", justify="right")
    loss_table.add_column("涨跌幅", justify="right")
    loss_table.add_column("成交额", justify="right")

    for _, r in bottom.iterrows():
        code = str(r.get("代码", ""))
        name = str(r.get("名称", ""))
        price = _safe_float(r.get("最新价"))
        chg = _safe_float(r.get("涨跌幅"))
        amt = _safe_float(r.get("成交额", 0))
        loss_table.add_row(code, name, _fmt_price(price), _fmt_chg(chg),
                          _fmt_vol(amt) if market != "us" else str(amt))

    console.print(loss_table)


# ==== Mode: ticker detail ====

def _ticker_detail(ak: AKShareProvider, cg: CoinGeckoProvider, ticker: str):
    symbol, market = parse_ticker(ticker)

    # Crypto
    if ticker.upper() in ("BTC", "ETH"):
        try:
            md = cg.get_market_data(ticker.upper())
            if md:
                chg = md.get("change_24h", 0) or 0
                color = _chg_color(chg)
                panel = Panel.fit(
                    f"{ticker.upper()}  {_fmt_price(md.get('price'))}  "
                    f"24h {_fmt_chg(chg)}",
                    title=ticker.upper(), border_style=color)
                console.print(panel)
                dt = Table(show_header=False, box=None)
                dt.add_column("field", style="dim"); dt.add_column("value", justify="right")
                dt.add_row("市值", _fmt_price(md.get("market_cap")))
                dt.add_row("24h 成交量", _fmt_price(md.get("volume_24h")))
                dt.add_row("7d 涨跌", _fmt_chg(md.get("change_7d")))
                dt.add_row("30d 涨跌", _fmt_chg(md.get("change_30d")))
                dt.add_row("历史最高", _fmt_price(md.get("ath")))
                console.print(dt)
                return
        except Exception as e:
            console.print(f"[red]CoinGecko 获取失败: {e}[/red]")
            return

    # CN stock
    if market == "CN":
        try:
            df = ak.get_a_share_spot()
            row = df[df["代码"] == symbol]
            if row.empty:
                console.print(f"[yellow]未找到 {symbol}[/yellow]")
                return
            _show_detail_row(row.iloc[0])
            return
        except Exception as e:
            console.print(f"[red]A股行情获取失败: {e}[/red]")
            return

    # HK stock
    if market == "HK":
        try:
            df = ak.get_hk_stock_spot()
            row = df[df["代码"] == symbol]
            if row.empty:
                row = df[df["代码"] == symbol.zfill(5)]
            if row.empty:
                console.print(f"[yellow]未找到 {symbol}[/yellow]")
                return
            _show_detail_row(row.iloc[0])
            return
        except Exception as e:
            console.print(f"[red]港股行情获取失败: {e}[/red]")
            return

    # US stock
    if market == "US":
        try:
            df = ak.get_us_stock_spot()
            row = df[df["代码"] == symbol.upper()]
            if not row.empty:
                _show_detail_row(row.iloc[0])
                return
        except Exception:
            pass
        # Fallback: yfinance fast_info
        try:
            import yfinance as yf
            t = yf.Ticker(symbol.upper())
            fi = t.fast_info
            price = fi.get("lastPrice") or fi.get("regularMarketPrice")
            prev = fi.get("regularMarketPreviousClose") or fi.get("previousClose")
            chg_pct = ((price - prev) / prev * 100) if price and prev else None
            color = _chg_color(chg_pct or 0)
            panel = Panel.fit(
                f"{symbol.upper()}  {_fmt_price(price)}  {_fmt_chg(chg_pct)}",
                title=symbol.upper(), border_style=color)
            console.print(panel)
            dt = Table(show_header=False, box=None)
            dt.add_column("field", style="dim"); dt.add_column("value", justify="right")
            dt.add_row("今开", _fmt_price(fi.get("open")))
            dt.add_row("最高", _fmt_price(fi.get("dayHigh")))
            dt.add_row("最低", _fmt_price(fi.get("dayLow")))
            dt.add_row("昨收", _fmt_price(prev))
            dt.add_row("市值", _fmt_price(fi.get("marketCap")))
            console.print(dt)
        except Exception as e:
            console.print(f"[red]美股行情获取失败: {e}[/red]")


def _show_detail_row(r):
    name = str(r.get("名称", ""))
    code = str(r.get("代码", ""))
    price = _safe_float(r.get("最新价"))
    chg_amt = _safe_float(r.get("涨跌额"))
    chg_pct = _safe_float(r.get("涨跌幅"))

    color = _chg_color(chg_pct or 0)
    sign = "+" if (chg_pct or 0) > 0 else ""
    header = f"{code} {name}  [{color}]{_fmt_price(price)}  {sign}{_fmt_chg(chg_pct)}[/]"
    if chg_amt:
        header += f"  涨跌额 {sign}{chg_amt:,.2f}"

    panel = Panel.fit(header, border_style=color)
    console.print(panel)

    dt = Table(show_header=False, box=None)
    dt.add_column("field", style="dim"); dt.add_column("value", justify="right")

    fields = [
        ("今开", "今开"), ("最高", "最高"), ("最低", "最低"),
        ("昨收", "昨收"), ("成交量", "成交量"), ("成交额", "成交额"),
        ("振幅", "振幅"), ("换手率", "换手率"),
        ("市盈率", "市盈率-动态"), ("市净率", "市净率"),
    ]
    for label, col in fields:
        raw = r.get(col) if col in r.index else r.get(label)
        if raw is not None and str(raw) not in ("nan", ""):
            val = _safe_float(raw)
            if val is not None:
                if "成交额" in label:
                    dt.add_row(label, _fmt_vol(val))
                elif "换手率" in label or "振幅" in label:
                    dt.add_row(label, f"{val:.2f}%")
                elif "市盈率" in label or "市净率" in label:
                    dt.add_row(label, f"{val:.2f}")
                else:
                    dt.add_row(label, _fmt_price(val))
            else:
                dt.add_row(label, str(raw))
    console.print(dt)


# ==== Mode: watchlist ====

def _watchlist(ak: AKShareProvider, cg: CoinGeckoProvider, path: str):
    import os
    if not os.path.exists(path):
        console.print(f"[red]文件不存在: {path}[/red]")
        return

    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)

    if not lines:
        console.print("[yellow]自选列表为空[/yellow]")
        return

    wl_table = Table(title="自选股行情")
    wl_table.add_column("代码", style="dim")
    wl_table.add_column("名称", style="bold")
    wl_table.add_column("最新价", justify="right")
    wl_table.add_column("涨跌幅", justify="right")
    wl_table.add_column("涨跌额", justify="right")

    # Pre-fetch CN DataFrame once if any CN tickers
    cn_df = None
    hk_df = None
    us_df = None

    for raw in lines:
        symbol, market = parse_ticker(raw)

        if market == "CN":
            if cn_df is None:
                try:
                    cn_df = ak.get_a_share_spot()
                except Exception:
                    pass
            row = cn_df[cn_df["代码"] == symbol] if cn_df is not None else None
            if row is not None and not row.empty:
                r = row.iloc[0]
                wl_table.add_row(symbol, str(r.get("名称", "")),
                                 _fmt_price(_safe_float(r.get("最新价"))),
                                 _fmt_chg(_safe_float(r.get("涨跌幅"))),
                                 str(r.get("涨跌额", "")))
                continue

        elif market == "HK":
            if hk_df is None:
                try:
                    hk_df = ak.get_hk_stock_spot()
                except Exception:
                    pass
            row = hk_df[hk_df["代码"] == symbol] if hk_df is not None else None
            if row is not None and not row.empty:
                r = row.iloc[0]
                wl_table.add_row(symbol, str(r.get("名称", "")),
                                 _fmt_price(_safe_float(r.get("最新价"))),
                                 _fmt_chg(_safe_float(r.get("涨跌幅"))),
                                 str(r.get("涨跌额", "")))
                continue

        elif raw.upper() in ("BTC", "ETH"):
            try:
                md = cg.get_market_data(raw.upper())
                if md:
                    wl_table.add_row(raw.upper(), raw.upper(),
                                     _fmt_price(md.get("price")),
                                     _fmt_chg(md.get("change_24h")),
                                     "")
                    continue
            except Exception:
                pass

        wl_table.add_row(raw, "[dim]unknown[/dim]", "[dim]—[/dim]", "[dim]—[/dim]", "[dim]—[/dim]")

    console.print(wl_table)


# ==== Click command ====

import pandas as pd  # noqa: E402


@click.command("spot")
@click.argument("ticker", required=False)
@click.option("--market", "-m", default=None, help="市场: cn / hk / us")
@click.option("--watchlist", "-w", default=None, help="自选股文件路径")
@click.option("--limit", "-n", default=10, help="涨跌榜数量 (默认10)")
def spot(ticker: str, market: str, watchlist: str, limit: int):
    """实时行情查询 — 全球指数/外汇/商品/加密货币/A股/港股/美股.

    \b
    用法:
      spot              全球概览
      spot -m cn        A股涨跌榜
      spot -m hk        港股涨跌榜
      spot -m us        美股涨跌榜 (延迟15分钟)
      spot 600519       A股个股行情
      spot AAPL         美股个股行情
      spot -w config/watchlist.txt  自选股行情
    """
    cache = DataCache()
    ak = AKShareProvider(cache=cache)
    cg = CoinGeckoProvider(cache=cache)

    if watchlist:
        return _watchlist(ak, cg, watchlist)

    if market:
        return _market_movers(ak, market, limit)

    if ticker:
        return _ticker_detail(ak, cg, ticker)

    _overview(ak, cg)
