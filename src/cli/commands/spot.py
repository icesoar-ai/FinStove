"""Real-time spot quotes — global markets, movers, ticker detail, watchlist."""
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.colors import load_scheme
from src.data.base import Market
from src.data.gateway import DataGateway
from src.utils.ticker import detect_market, parse_ticker

console = Console()
_C = load_scheme()

# ---- helpers ----

def _chg_color(val: float) -> str:
    """Return Rich style tag for change value."""
    return _C.chg_color(val)


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

def _overview():
    console.print(Panel.fit("实时行情概览", style="bold cyan"))
    import yfinance as yf

    # --- Indices table ---
    idx_table = Table(title="全球指数", border_style="blue")
    idx_table.add_column("名称", style="bold")
    idx_table.add_column("最新价", justify="right")
    idx_table.add_column("涨跌幅", justify="right")

    _IDX_TICKERS = {
        "000001.SS": "上证指数", "399001.SZ": "深证成指", "000300.SS": "沪深300",
        "399006.SZ": "创业板指", "000688.SS": "科创50",
        "^GSPC": "标普500", "^IXIC": "纳斯达克", "^DJI": "道琼斯",
        "^HSI": "恒生指数", "^N225": "日经225",
        "^FTSE": "英国富时100", "^GDAXI": "德国DAX", "^FCHI": "法国CAC",
    }
    try:
        for ticker, label in _IDX_TICKERS.items():
            t = yf.Ticker(ticker)
            fi = t.fast_info
            price = fi.get("lastPrice") or fi.get("regularMarketPrice")
            prev = fi.get("regularMarketPreviousClose") or fi.get("previousClose")
            if price and prev:
                chg = (price - prev) / prev * 100
                idx_table.add_row(label, _fmt_price(price), _fmt_chg(chg))
            elif price:
                idx_table.add_row(label, _fmt_price(price), "[dim]—[/dim]")
    except Exception as e:
        idx_table.caption = f"[red]指数数据获取失败: {e}[/red]"

    console.print(idx_table)

    # --- FX + Commodities table ---
    fxc_table = Table(title="外汇 / 商品", border_style="yellow")
    fxc_table.add_column("名称", style="bold")
    fxc_table.add_column("最新价", justify="right")
    fxc_table.add_column("涨跌幅", justify="right")

    # Forex + DXY (yfinance fast_info)
    _FX_TICKERS = {
        "USDCNY=X": "美元/人民币", "EURUSD=X": "欧元/美元",
        "USDJPY=X": "美元/日元", "GBPUSD=X": "英镑/美元",
        "AUDUSD=X": "澳元/美元", "USDCAD=X": "美元/加元",
        "DX-Y.NYB": "美元指数",
    }
    try:
        for ticker, label in _FX_TICKERS.items():
            t = yf.Ticker(ticker)
            fi = t.fast_info
            price = fi.get("lastPrice") or fi.get("regularMarketPrice")
            prev = fi.get("regularMarketPreviousClose") or fi.get("previousClose")
            if price and prev:
                chg = (price - prev) / prev * 100
                fxc_table.add_row(label, _fmt_price(price), _fmt_chg(chg))
            elif price:
                fxc_table.add_row(label, _fmt_price(price), "[dim]—[/dim]")
    except Exception:
        pass

    # Commodities (yfinance fast_info)
    _COMMODITY_SPOT_TICKERS = {
        "GC=F": "黄金", "SI=F": "白银", "CL=F": "美原油",
        "BZ=F": "布伦特", "HG=F": "铜", "NG=F": "天然气",
    }
    try:
        for ticker, label in _COMMODITY_SPOT_TICKERS.items():
            t = yf.Ticker(ticker)
            fi = t.fast_info
            price = fi.get("lastPrice") or fi.get("regularMarketPrice")
            prev = fi.get("regularMarketPreviousClose") or fi.get("previousClose")
            if price and prev:
                chg = (price - prev) / prev * 100
                fxc_table.add_row(label, _fmt_price(price), _fmt_chg(chg))
            elif price:
                fxc_table.add_row(label, _fmt_price(price), "[dim]—[/dim]")
    except Exception:
        pass

    console.print(fxc_table)

    # --- Crypto table (yfinance fast_info) ---
    crypto_table = Table(title="加密货币", border_style="magenta")
    crypto_table.add_column("名称", style="bold")
    crypto_table.add_column("最新价", justify="right")
    crypto_table.add_column("24h涨跌", justify="right")

    _CRYPTO_TICKERS = {"BTC-USD": "BTC", "ETH-USD": "ETH"}
    try:
        for ticker, label in _CRYPTO_TICKERS.items():
            t = yf.Ticker(ticker)
            fi = t.fast_info
            price = fi.get("lastPrice") or fi.get("regularMarketPrice")
            prev = fi.get("regularMarketPreviousClose") or fi.get("previousClose")
            if price and prev:
                chg = (price - prev) / prev * 100
                crypto_table.add_row(label, _fmt_price(price), _fmt_chg(chg))
            elif price:
                crypto_table.add_row(label, _fmt_price(price), "[dim]—[/dim]")
    except Exception:
        crypto_table.add_row("BTC", "[dim]unavailable[/dim]", "[dim]—[/dim]")
        crypto_table.add_row("ETH", "[dim]unavailable[/dim]", "[dim]—[/dim]")

    console.print(crypto_table)


# ==== Mode: market movers ====

def _market_movers(gw: DataGateway, market: str, limit: int):
    mk_label = {"cn": "A股", "hk": "港股", "us": "美股"}.get(market, market.upper())
    market_fn = {"cn": gw.get_a_share_spot, "hk": gw.get_hk_stock_spot, "us": gw.get_us_stock_spot}

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
    gain_table = Table(title=f"涨幅榜 TOP{limit}", border_style=_C.up)
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
    loss_table = Table(title=f"跌幅榜 TOP{limit}", border_style=_C.down)
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

def _ticker_detail(gw: DataGateway, ticker: str):
    symbol, market = parse_ticker(ticker)

    # Crypto
    if ticker.upper() in ("BTC", "ETH"):
        try:
            md = gw.get_crypto_market_data(ticker.upper())
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

    # CN stock (AKShare spot first, fallback to yfinance)
    if market == Market.CN:
        try:
            df = gw.get_a_share_spot()
            row = df[df["代码"] == symbol]
            if not row.empty:
                _show_detail_row(row.iloc[0])
                return
        except Exception:
            pass
        # Fallback: yfinance fast_info
        try:
            import yfinance as yf
            t = yf.Ticker(f"{symbol}.SS")
            fi = t.fast_info
            price = fi.get("lastPrice") or fi.get("regularMarketPrice")
            prev = fi.get("regularMarketPreviousClose") or fi.get("previousClose")
            if not price:
                t = yf.Ticker(f"{symbol}.SZ")
                fi = t.fast_info
                price = fi.get("lastPrice") or fi.get("regularMarketPrice")
                prev = fi.get("regularMarketPreviousClose") or fi.get("previousClose")
            if price:
                chg_pct = ((price - prev) / prev * 100) if price and prev else None
                color = _chg_color(chg_pct or 0)
                console.print(Panel.fit(
                    f"{symbol}  {_fmt_price(price)}  {_fmt_chg(chg_pct)}",
                    title=symbol, border_style=color))
                dt = Table(show_header=False, box=None)
                dt.add_column("field", style="dim"); dt.add_column("value", justify="right")
                dt.add_row("今开", _fmt_price(fi.get("open")))
                dt.add_row("最高", _fmt_price(fi.get("dayHigh")))
                dt.add_row("最低", _fmt_price(fi.get("dayLow")))
                dt.add_row("昨收", _fmt_price(prev))
                dt.add_row("市值", _fmt_price(fi.get("marketCap")))
                console.print(dt)
                return
        except Exception:
            pass
        console.print(f"[red]A股行情获取失败: {symbol}[/red]")

    # HK stock
    if market == Market.HK:
        try:
            df = gw.get_hk_stock_spot()
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
    if market == Market.US:
        try:
            df = gw.get_us_stock_spot()
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

def _watchlist(gw: DataGateway, path: str):
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

        if market == Market.CN:
            if cn_df is None:
                try:
                    cn_df = gw.get_a_share_spot()
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

        elif market == Market.HK:
            if hk_df is None:
                try:
                    hk_df = gw.get_hk_stock_spot()
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
                md = gw.get_crypto_market_data(raw.upper())
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
    gw = DataGateway()

    if watchlist:
        return _watchlist(gw, watchlist)

    if market:
        return _market_movers(gw, market, limit)

    if ticker:
        return _ticker_detail(gw, ticker)

    _overview()
