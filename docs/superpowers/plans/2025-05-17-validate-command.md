# Data Validation Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `./bin/fstove validate` command that checks parquet data files for structural integrity, OHLCV sanity, date integrity, and freshness.

**Architecture:** Pure-function validator module (`src/data/validator.py`) produces a list of `ValidationIssue` dataclasses from DataFrames. CLI command (`src/cli/commands/validate.py`) walks the `data/` directory tree, calls the validator on each parquet file, and renders results grouped by asset type with Rich.

**Tech Stack:** Python 3.12+, pandas, Rich (Console/Table/Panel), Click, pytest

---

## File Structure

| File | Role |
|------|------|
| `src/data/validator.py` (create) | Core validation logic — pure functions, no I/O |
| `src/cli/commands/validate.py` (create) | CLI command — walks `data/`, calls validator, Rich output |
| `src/cli/main.py` (modify) | Register `validate` command |
| `tests/data/test_validator.py` (create) | Unit tests for validator |
| `tests/conftest.py` (create) | Pytest fixtures (test data root) |

---

### Task 1: Define ValidationIssue dataclass and validator skeleton

**Files:**
- Create: `src/data/validator.py`

- [ ] **Step 1: Create validator module with data types**

```python
"""Data validation — pure functions that check parquet DataFrames for quality issues.

All functions take a pd.DataFrame + metadata and return a list of ValidationIssue.
No file I/O or CLI concerns here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Optional

import pandas as pd


class Severity(Enum):
    ERROR = "error"    # Data corruption — high < low, negative volume
    WARNING = "warn"   # Potential problem — stale data, missing files
    INFO = "info"      # Nice to know — empty but expected


@dataclass
class ValidationIssue:
    severity: Severity
    category: str       # "schema", "ohlcv", "date", "freshness", "file"
    message: str
    asset_path: str     # e.g. "stock/cn/600519.SH/daily"
    detail: str = ""


DAILY_OHLCV_COLS = {"date", "open", "high", "low", "close", "volume"}

# Freshness thresholds in days — how stale before WARNING
FRESHNESS_DAYS: dict[str, int] = {
    "daily": 3,       # daily data should be <= 2 trading days old
    "monthly": 35,    # monthly macro indicators
    "quarterly": 95,  # quarterly financials
}


def validate_columns(df: pd.DataFrame, asset_path: str) -> list[ValidationIssue]:
    """Check that daily OHLCV data has expected columns."""
    issues = []
    cols = set(df.columns)
    missing = DAILY_OHLCV_COLS - cols
    if missing:
        issues.append(ValidationIssue(
            severity=Severity.ERROR,
            category="schema",
            message=f"Missing columns: {', '.join(sorted(missing))}",
            asset_path=asset_path,
        ))
    return issues


def validate_ohlcv(df: pd.DataFrame, asset_path: str) -> list[ValidationIssue]:
    """Check OHLCV sanity: high >= low, volume >= 0, close in range."""
    issues = []
    required = {"high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        return issues  # Column check handles this

    bad_rows_hl = (df["high"] < df["low"]).sum()
    if bad_rows_hl > 0:
        issues.append(ValidationIssue(
            severity=Severity.ERROR,
            category="ohlcv",
            message=f"High < Low in {bad_rows_hl} rows",
            asset_path=asset_path,
        ))

    bad_rows_vol = (df["volume"] < 0).sum()
    if bad_rows_vol > 0:
        issues.append(ValidationIssue(
            severity=Severity.ERROR,
            category="ohlcv",
            message=f"Negative volume in {bad_rows_vol} rows",
            asset_path=asset_path,
        ))

    # close should be within [low, high] — allow 0.5% tolerance for rounding
    if "close" in df.columns and "high" in df.columns and "low" in df.columns:
        above_high = (df["close"] > df["high"] * 1.005).sum()
        below_low = (df["close"] < df["low"] * 0.995).sum()
        if above_high > 0:
            issues.append(ValidationIssue(
                severity=Severity.WARNING,
                category="ohlcv",
                message=f"Close > High in {above_high} rows",
                asset_path=asset_path,
            ))
        if below_low > 0:
            issues.append(ValidationIssue(
                severity=Severity.WARNING,
                category="ohlcv",
                message=f"Close < Low in {below_low} rows",
                asset_path=asset_path,
            ))

    return issues


def validate_dates(df: pd.DataFrame, asset_path: str) -> list[ValidationIssue]:
    """Check date integrity: no future dates, monotonically increasing."""
    issues = []
    if "date" not in df.columns:
        return issues

    dates = pd.to_datetime(df["date"]).dt.date
    today = date.today()

    future = sum(1 for d in dates if d > today)
    if future > 0:
        issues.append(ValidationIssue(
            severity=Severity.ERROR,
            category="date",
            message=f"Future dates in {future} rows",
            asset_path=asset_path,
        ))

    if not dates.is_monotonic_increasing:
        issues.append(ValidationIssue(
            severity=Severity.WARNING,
            category="date",
            message="Dates not monotonically increasing",
            asset_path=asset_path,
        ))

    return issues


def validate_freshness(df: pd.DataFrame, asset_path: str,
                       data_type: str = "daily") -> list[ValidationIssue]:
    """Check that the latest data point is recent enough."""
    issues = []
    if "date" not in df.columns:
        return issues

    dates = pd.to_datetime(df["date"]).dt.date
    if len(dates) == 0:
        return issues

    threshold = FRESHNESS_DAYS.get(data_type, 3)
    last_date = dates.max()
    days_since = (date.today() - last_date).days

    if days_since > threshold:
        issues.append(ValidationIssue(
            severity=Severity.WARNING,
            category="freshness",
            message=f"Stale: last data {last_date} ({days_since} days ago, threshold {threshold}d)",
            asset_path=asset_path,
            detail=f"last_date={last_date}, days_since={days_since}",
        ))

    return issues


def validate_daily(df: pd.DataFrame, asset_path: str,
                   data_type: str = "daily") -> list[ValidationIssue]:
    """Run all validations for a daily OHLCV parquet file."""
    issues = []
    issues.extend(validate_columns(df, asset_path))
    issues.extend(validate_ohlcv(df, asset_path))
    issues.extend(validate_dates(df, asset_path))
    issues.extend(validate_freshness(df, asset_path, data_type))
    return issues
```

- [ ] **Step 2: Commit**

```bash
git add src/data/validator.py
git commit -m "feat: add validator module with OHLCV/date/freshness checks"
```

---

### Task 2: Write unit tests for validator

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/data/test_validator.py`

- [ ] **Step 1: Create conftest.py**

```python
"""Pytest fixtures."""
```

- [ ] **Step 2: Write tests for validator**

```python
"""Tests for src.data.validator."""
from datetime import date, timedelta

import pandas as pd
import pytest

from src.data.validator import (
    Severity,
    ValidationIssue,
    validate_columns,
    validate_ohlcv,
    validate_dates,
    validate_freshness,
    validate_daily,
)


def _make_df(**overrides) -> pd.DataFrame:
    """Build a minimal valid OHLCV DataFrame, with optional column overrides."""
    data = {
        "date": [date.today() - timedelta(days=i) for i in range(5, 0, -1)],
        "open": [100.0, 101.0, 102.0, 101.5, 103.0],
        "high": [102.0, 103.0, 104.0, 103.0, 104.5],
        "low": [99.0, 100.0, 101.0, 100.5, 102.0],
        "close": [101.0, 102.0, 103.0, 102.5, 104.0],
        "volume": [1000000, 1200000, 1100000, 900000, 1300000],
    }
    data.update(overrides)
    return pd.DataFrame(data)


class TestValidateColumns:
    def test_all_columns_present(self):
        df = _make_df()
        assert validate_columns(df, "test") == []

    def test_missing_columns(self):
        df = _make_df()
        df = df.drop(columns=["high", "volume"])
        issues = validate_columns(df, "test")
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert "high" in issues[0].message
        assert "volume" in issues[0].message

    def test_extra_columns_ok(self):
        df = _make_df()
        df["extra_col"] = 1
        assert validate_columns(df, "test") == []


class TestValidateOHLCV:
    def test_valid_data(self):
        df = _make_df()
        assert validate_ohlcv(df, "test") == []

    def test_high_below_low(self):
        df = _make_df(high=[99.0, 103.0, 104.0, 103.0, 104.5])
        issues = validate_ohlcv(df, "test")
        assert any("High < Low" in i.message for i in issues)

    def test_negative_volume(self):
        df = _make_df(volume=[1000000, -1, 1100000, 900000, 1300000])
        issues = validate_ohlcv(df, "test")
        assert any("Negative volume" in i.message for i in issues)

    def test_close_outside_range(self):
        df = _make_df(close=[101.0, 200.0, 103.0, 102.5, 104.0])
        issues = validate_ohlcv(df, "test")
        assert any("Close > High" in i.message for i in issues)

    def test_missing_ohlcv_cols_skipped(self):
        df = pd.DataFrame({"date": [], "value": []})
        assert validate_ohlcv(df, "test") == []


class TestValidateDates:
    def test_valid_dates(self):
        df = _make_df()
        assert validate_dates(df, "test") == []

    def test_future_dates(self):
        df = _make_df(date=[date.today() + timedelta(days=i) for i in range(5)])
        issues = validate_dates(df, "test")
        assert any("Future dates" in i.message for i in issues)

    def test_non_monotonic(self):
        df = _make_df(date=sorted(
            [date.today() - timedelta(days=i) for i in range(5, 0, -1)],
            reverse=True,
        ))
        issues = validate_dates(df, "test")
        assert any("not monotonically" in i.message for i in issues)


class TestValidateFreshness:
    def test_recent_data(self):
        df = _make_df()
        assert validate_freshness(df, "test", "daily") == []

    def test_stale_data(self):
        old_dates = [date.today() - timedelta(days=i) for i in range(30, 25, -1)]
        df = _make_df(date=old_dates)
        issues = validate_freshness(df, "test", "daily")
        assert len(issues) == 1
        assert issues[0].severity == Severity.WARNING
        assert "Stale" in issues[0].message

    def test_monthly_freshness_longer_threshold(self):
        old_dates = [date.today() - timedelta(days=i) for i in range(50, 45, -1)]
        df = _make_df(date=old_dates)
        issues = validate_freshness(df, "test", "monthly")
        assert len(issues) == 1

    def test_no_date_column(self):
        df = pd.DataFrame({"value": [1, 2, 3]})
        assert validate_freshness(df, "test") == []


class TestValidateDaily:
    def test_clean_data_no_issues(self):
        df = _make_df()
        assert validate_daily(df, "stock/cn/600519/daily") == []

    def test_combines_all_checks(self):
        df = _make_df(high=[99.0, 103.0, 104.0, 103.0, 104.5], volume=[1, -1, 1, 1, 1])
        df = df.drop(columns=["close"])
        issues = validate_daily(df, "test")
        assert len(issues) >= 3  # missing close, high<low, negative volume
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
python -m pytest tests/data/test_validator.py -v
```
Expected: 14 tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/data/test_validator.py
git commit -m "test: add validator unit tests — columns, OHLCV, dates, freshness"
```

---

### Task 3: Create CLI validate command

**Files:**
- Create: `src/cli/commands/validate.py`

- [ ] **Step 1: Create the CLI command**

```python
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

# Asset types to scan and what data_type (for freshness) they use
ASSET_SCAN = [
    ("stock", "daily"),
    ("index", "daily"),
    ("etf", "daily"),
    ("commodity", "daily"),
    ("crypto", "daily"),
    ("forex", "daily"),
    ("flow", "daily"),
    # macro has mixed frequencies; skip for now, can add later
]


def _walk_parquets(data_dir: Path) -> list[tuple[str, Path]]:
    """Walk data/ directory, yield (asset_path, file_path) for each parquet."""
    result = []
    for parquet_path in data_dir.rglob("*.parquet"):
        rel = parquet_path.relative_to(data_dir)
        # Build asset_path: e.g. "stock/cn/600519.SH/daily"
        parts = list(rel.parts)
        asset_path = "/".join(Path(str(rel.with_suffix(""))).as_posix().split("/"))
        result.append((asset_path, parquet_path))
    return sorted(result, key=lambda x: x[0])


def _asset_type_label(asset_path: str) -> str:
    """Extract asset type from path for grouping."""
    parts = asset_path.split("/")
    return parts[0] if parts else "unknown"


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

    console.print(f"[bold]扫描数据目录: {data_path}[/bold]\n")

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
            continue  # Skip empty files — not necessarily an error

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

    # ── Group by severity and asset type ──
    errors = [i for i in all_issues if i.severity == Severity.ERROR]
    warnings = [i for i in all_issues if i.severity == Severity.WARNING]
    infos = [i for i in all_issues if i.severity == Severity.INFO]

    # ── Errors ──
    if errors:
        table = Table(title="[bold red]❌ 数据错误[/bold red]")
        table.add_column("资产", style="cyan")
        table.add_column("类别")
        table.add_column("问题")
        for e in sorted(errors, key=lambda x: x.asset_path):
            table.add_row(e.asset_path, e.category, e.message)
        console.print(table)
        console.print()

    # ── Warnings ──
    if warnings and not errors_only:
        table = Table(title="[bold yellow]⚠ 数据警告[/bold yellow]")
        table.add_column("资产", style="cyan")
        table.add_column("类别")
        table.add_column("问题")
        for w in sorted(warnings, key=lambda x: x.asset_path):
            table.add_row(w.asset_path, w.category, w.message)
        console.print(table)
        console.print()

    # ── Summary panel ──
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
```

- [ ] **Step 2: Register command in main.py**

Add after the label_data import:
```python
from src.cli.commands.validate import validate_data
```

Add after the label_data registration:
```python
cli.add_command(validate_data)
```

- [ ] **Step 3: Test the command manually**

```bash
./bin/fstove validate
```
Expected: scans all parquet files, reports issues with Rich formatting.

- [ ] **Step 4: Commit**

```bash
git add src/cli/commands/validate.py src/cli/main.py
git commit -m "feat: add validate CLI command for parquet data quality checks"
```

---

### Task 4: Run full validation and verify

- [ ] **Step 1: Run validate on current data**

```bash
./bin/fstove validate
```

- [ ] **Step 2: Check for any errors found**
  - If errors exist, investigate whether they're real data issues or validator bugs
  - Fix validator if needed, commit fixes

- [ ] **Step 3: Run tests one final time**

```bash
python -m pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final validation command adjustments"
```
