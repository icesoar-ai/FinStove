from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.data.cache import DataCache
from src.data.storage import ParquetStorage

console = Console()


@click.command("flow")
@click.option("--start", default="2010-01-01", help="Start date")
@click.option("--end", default="", help="End date (default: today)")
def flow_data(start: str, end: str):
    """Fetch northbound/southbound capital flow data (沪深港通资金流向)."""
    from src.data.providers.akshare import AKShareProvider

    end = end or date.today().strftime("%Y-%m-%d")
    cache = DataCache()
    storage = ParquetStorage()
    ak = AKShareProvider(cache=cache, storage=storage)

    for direction, label, fetch_fn in [
        ("northbound", "北向资金 (沪股通+深股通→A股)", ak.get_northbound),
        ("southbound", "南向资金 (港股通→港股)", ak.get_southbound),
    ]:
        console.print(f"[bold]Fetching {label}[/bold]")

        try:
            start_fmt = start.replace("-", "") if "-" in start else start
            end_fmt = end.replace("-", "") if "-" in end else end
            df = fetch_fn(start_fmt, end_fmt)

            if df is None or df.empty:
                console.print(f"[yellow]  No data for {direction}[/yellow]")
                continue

            console.print(f"[green]  {len(df)} rows[/green]")

            # Show latest flow value
            latest_val = None
            for col in df.columns:
                if col.lower() != "date" and df.iloc[-1][col]:
                    try:
                        latest_val = float(df.iloc[-1][col])
                        console.print(f"  Latest: [bold]{latest_val:+.2f} 亿[/bold]")
                        break
                    except (ValueError, TypeError):
                        pass

            table = Table(title=direction)
            table.add_column("Date", style="cyan")
            # Show last 10 rows of first numeric column
            numeric_cols = [c for c in df.columns if c.lower() != "date"]
            for col in numeric_cols[:3]:
                table.add_column(col, justify="right")

            for _, row in df.tail(10).iterrows():
                vals = [str(row.get("date", ""))]
                for col in numeric_cols[:3]:
                    v = row.get(col)
                    vals.append(f"{v:.2f}" if v is not None and str(v) != "nan" else "-")
                table.add_row(*vals)

            console.print(table)

        except Exception as e:
            console.print(f"[red]  Error: {e}[/red]")
