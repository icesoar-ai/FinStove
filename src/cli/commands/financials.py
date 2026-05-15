import click
import pandas as pd
from rich.console import Console
from rich.table import Table

from src.data.gateway import DataGateway
from src.data.storage import ParquetStorage
from src.utils.ticker import parse_ticker

console = Console()


@click.command()
@click.argument("ticker")
@click.option("--years", default="", help="过滤年份，逗号分隔 (如 2021,2022,2023)")
@click.option("--period", default="all",
              type=click.Choice(["all", "annual", "quarterly"]),
              help="显示周期，默认 all")
def financials(ticker: str, years: str, period: str):
    """A股三大财务报表 — 资产负债表 / 利润表 / 现金流量表 / 主要财务指标.

    数据源: AKShare (同花顺)，需先拉取数据: /fetch-stock <TICKER> financials
    """
    symbol, market = parse_ticker(ticker)
    gw = DataGateway()

    if market.value != "cn":
        # US/HK: fetch via yfinance directly
        console.print(f"[bold]Fetching financials for {symbol} (market={market.value})...[/bold]")
        try:
            result = gw.get_financials(symbol, market)
            if not result:
                console.print("[yellow]No financial data returned.[/yellow]")
                return
            for name in ["balance_sheet", "income", "cashflow"]:
                df = result.get(name)
                if df is not None and not df.empty:
                    df = df.reset_index()
                    if isinstance(df.columns, pd.DatetimeIndex):
                        df.columns = [str(c.date()) for c in df.columns]
                    gw._storage.save(df, "stock", market.value, symbol, name)
            # Dividends
            div_df = gw.get_dividends(symbol, market)
            if div_df is not None and not div_df.empty:
                gw._storage.save(div_df, "stock", market.value, symbol, "dividends")
                console.print(f"[green]Saved: balance_sheet, income, cashflow, dividends ({len(div_df)} records)[/green]")
            else:
                console.print(f"[green]Saved: balance_sheet, income, cashflow[/green]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        return

    from src.utils.ticker import stock_dir

    s = ParquetStorage()
    dir_name = stock_dir(symbol)

    console.print(f"[bold]Fetching financials for {dir_name}...[/bold]")

    # 1. 财务摘要 (可靠)
    try:
        import akshare as ak
        fin = ak.stock_financial_abstract_ths(symbol=symbol)
        fin["报告期_dt"] = pd.to_datetime(fin["报告期"])
        recent = fin.drop(columns=["报告期_dt"])
        s.save(recent, "stock", "cn", dir_name, "financials")
        console.print(f"[green]财务摘要: {len(recent)} 期[/green]")

        # Filter by years
        if years:
            year_list = [int(y.strip()) for y in years.split(",") if y.strip()]
            recent = recent[recent["报告期"].str[:4].isin([str(y) for y in year_list])]

        if not recent.empty:
            _display_financials(recent, symbol, period)

    except Exception as e:
        console.print(f"[red]财务摘要获取失败: {e}[/red]")

    # 2. 详细三张表 (可能失败)
    try:
        financials = gw.get_financials(symbol)
        if financials:
            for name, df in financials.items():
                if df is not None and not df.empty:
                    label = {"balance_sheet": "资产负债表", "income": "利润表", "cashflow": "现金流量表"}
                    console.print(f"[green]{label.get(name, name)}: {len(df)} 期[/green]")
    except Exception:
        console.print("[dim]详细三张表暂不可用 (东方财富接口维护中)[/dim]")

    # 3. 历史分红
    try:
        dividends = gw.get_dividends(symbol)
        if not dividends.empty:
            latest = dividends.iloc[-1]
            recent_5 = dividends.tail(5)
            total_dps = recent_5["派息"].sum()
            console.print(f"[green]历史分红: {len(dividends)} 次, 最近5次累计派息 {total_dps:.2f} 元/股[/green]")
    except Exception:
        console.print("[dim]分红数据不可用[/dim]")


def _display_financials(df, symbol: str, period: str = "all"):
    """Display financial metrics.

    A股报告期: 年报(12-31)/一季报(03-31)/半年报(06-30)/三季报(09-30).
    "quarterly" 组包含所有非年报期间(一季报+半年报+三季报).
    """
    if period == "annual":
        filtered = df[df["报告期"].str.endswith("-12-31")].sort_values("报告期")
    elif period == "quarterly":
        filtered = df[~df["报告期"].str.endswith("-12-31")].sort_values("报告期")
    else:
        filtered = df.sort_values("报告期")

    if filtered.empty:
        return

    period_label = {"annual": "年度", "quarterly": "季度", "all": "全期"}[period]
    table = Table(title=f"{symbol} {period_label}财务摘要")
    table.add_column("报告期")
    key_cols = ["净利润", "营业总收入", "基本每股收益", "每股净资产", "净资产收益率", "资产负债率"]
    for col in key_cols:
        if col in filtered.columns:
            table.add_column(col, justify="right")

    for _, row in filtered.iterrows():
        report_period = row["报告期"]
        vals = [report_period]
        for col in key_cols:
            if col in filtered.columns:
                v = row[col]
                if isinstance(v, (int, float)):
                    if abs(v) >= 1e8:
                        vals.append(f"{v/1e8:.2f}亿")
                    elif abs(v) >= 1e4:
                        vals.append(f"{v/1e4:.0f}万")
                    elif col in ("净资产收益率", "资产负债率"):
                        vals.append(f"{v:.1f}%")
                    else:
                        vals.append(f"{v:.2f}")
                else:
                    vals.append(str(v) if v else "")
        table.add_row(*vals)

    console.print(table)
