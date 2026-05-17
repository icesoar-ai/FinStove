"""Data validation command — checks parquet files for quality issues."""
from pathlib import Path

import click
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.data.validator import (
    Severity,
    ValidationIssue,
    validate_daily,
)

console = Console()
DEFAULT_DATA_DIR = Path.cwd() / "data"


def _walk_parquets(data_dir: Path) -> list[tuple[str, Path]]:
    """Walk data/ directory, yield (asset_path, file_path) for each parquet."""
    result = []
    for parquet_path in data_dir.rglob("*.parquet"):
        rel = parquet_path.relative_to(data_dir)
        asset_path = str(rel.with_suffix("")).replace("\\", "/")
        result.append((asset_path, parquet_path))
    return sorted(result, key=lambda x: x[0])


@click.command("validate")
@click.option("--data-dir", default=str(DEFAULT_DATA_DIR), help="数据目录路径")
@click.option("--errors-only", is_flag=True, default=False, help="仅显示错误")
def validate_data(data_dir: str, errors_only: bool):
    """数据校验 — 检查 Parquet 数据文件的完整性和合理性.

    检查项：
    - 列完整性 (OHLCV 六列齐备)
    - 数据合理性 (high>=low, volume>=0)
    - 日期合理性 (无未来日期, 单调递增)
    - 数据新鲜度 (是否过期)
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        console.print(f"[red]数据目录不存在: {data_dir}[/red]")
        return

    all_issues: list[ValidationIssue] = []
    scanned = 0
    errors_total = 0
    warnings_total = 0

    for asset_path, file_path in _walk_parquets(data_path):
        scanned += 1
        try:
            df = pd.read_parquet(file_path)
        except Exception as e:
            all_issues.append(ValidationIssue(
                severity=Severity.ERROR,
                category="file",
                message=f"Failed to read parquet: {e}",
                asset_path=asset_path,
            ))
            errors_total += 1
            continue

        if df.empty:
            continue

        # Determine data_type for freshness
        data_type = "daily"
        fname = file_path.stem
        if fname in ("monthly",) or "monthly" in asset_path:
            data_type = "monthly"
        elif fname in ("quarterly",):
            data_type = "quarterly"

        df_issues = validate_daily(df, asset_path, data_type)
        all_issues.extend(df_issues)
        for i in df_issues:
            if i.severity == Severity.ERROR:
                errors_total += 1
            elif i.severity == Severity.WARNING:
                warnings_total += 1

    # Group by severity
    errors = [i for i in all_issues if i.severity == Severity.ERROR]
    warnings = [i for i in all_issues if i.severity == Severity.WARNING]

    # Errors table
    if errors:
        table = Table(title="[bold red]数据错误[/bold red]")
        table.add_column("资产", style="cyan")
        table.add_column("类别")
        table.add_column("问题")
        for e in sorted(errors, key=lambda x: x.asset_path):
            table.add_row(e.asset_path, e.category, e.message)
        console.print(table)
        console.print()

    # Warnings table
    if warnings and not errors_only:
        table = Table(title="[bold yellow]数据警告[/bold yellow]")
        table.add_column("资产", style="cyan")
        table.add_column("类别")
        table.add_column("问题")
        for w in sorted(warnings, key=lambda x: x.asset_path):
            table.add_row(w.asset_path, w.category, w.message)
        console.print(table)
        console.print()

    # Summary panel
    summary_color = "red" if errors_total > 0 else ("yellow" if warnings_total > 0 else "green")
    summary_text = f"扫描 {scanned} 个 parquet 文件"
    if errors_total > 0:
        summary_text += f" | [red]错误 {errors_total}[/red]"
    if warnings_total > 0:
        summary_text += f" | [yellow]警告 {warnings_total}[/yellow]"
    if errors_total == 0 and warnings_total == 0:
        summary_text += " | [green]全部正常[/green]"

    panel = Panel(summary_text, title="[bold]校验结果[/bold]", border_style=summary_color)
    console.print(panel)
