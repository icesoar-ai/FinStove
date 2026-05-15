"""Fetch US Treasury yield curve data."""
from datetime import date

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.data.gateway import DataGateway

console = Console()


@click.command("yield-curve")
@click.option("--history/--latest", default=False, help="Show historical curve instead of latest snapshot")
def yield_curve_data(history: bool):
    """美国国债收益率曲线 — 3月/1年/2年/5年/10年/30年.

    需要环境变量 FRED_API_KEY。
    """
    gw = DataGateway()

    if history:
        try:
            df = gw.get_yield_curve_history()
            if df is None or df.empty:
                console.print("[yellow]No yield curve history available.[/yellow]")
                return

            console.print(f"[green]{len(df)} rows[/green]")

            table = Table(title="US Treasury Yield Curve History")
            table.add_column("Date", style="cyan")
            for col in df.columns:
                if col != "date":
                    table.add_column(col, justify="right")

            for _, row in df.tail(20).iterrows():
                vals = [str(row.get("date", ""))]
                for col in df.columns:
                    if col != "date":
                        v = row.get(col)
                        vals.append(f"{v:.2f}%" if v and not str(v) == "nan" else "-")
                table.add_row(*vals)

            console.print(table)

        except Exception as e:
            console.print(f"[red]  Error: {e}[/red]")
    else:
        try:
            curve = gw.get_yield_curve()

            if not any(curve.values()):
                console.print("[yellow]No yield curve data available. Set FRED_API_KEY?[/yellow]")
                return

            # Build a panel
            lines = []
            tenors_ordered = ["30Y", "10Y", "5Y", "2Y", "1Y", "3M"]
            for tenor in tenors_ordered:
                val = curve.get(tenor)
                if val is not None:
                    lines.append(f"  [cyan]{tenor:>4s}[/cyan]: {val:.2f}%")
                else:
                    lines.append(f"  [cyan]{tenor:>4s}[/cyan]: --")

            # 10Y-2Y spread
            spread = None
            if curve.get("10Y") and curve.get("2Y"):
                spread = curve["10Y"] - curve["2Y"]
                color = "red" if spread < 0 else "green"
                lines.append(f"\n  [bold]10Y-2Y Spread:[/bold] [{color}]{spread:+.2f}%[/{color}]")

            if curve.get("10Y") and curve.get("3M"):
                spread_10y3m = curve["10Y"] - curve["3M"]
                color = "red" if spread_10y3m < 0 else "green"
                lines.append(f"  [bold]10Y-3M Spread:[/bold] [{color}]{spread_10y3m:+.2f}%[/{color}]")

            panel = Panel(
                "\n".join(lines),
                title="[bold]US Treasury Yield Curve[/bold]",
                subtitle=f"Data: FRED ({date.today().strftime('%Y-%m-%d')})",
            )
            console.print(panel)

        except Exception as e:
            console.print(f"[red]  Error: {e}[/red]")
