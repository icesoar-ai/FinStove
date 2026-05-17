"""Data validation — pure functions that check parquet DataFrames for quality issues.

All functions take a pd.DataFrame + metadata and return a list of ValidationIssue.
No file I/O or CLI concerns here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

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
    "daily": 3,       # warn if more than 3 days stale
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

    threshold = FRESHNESS_DAYS.get(data_type, FRESHNESS_DAYS["daily"])
    last_date = dates.max()
    days_since = (date.today() - last_date).days

    if days_since > threshold:
        issues.append(ValidationIssue(
            severity=Severity.WARNING,
            category="freshness",
            message=f"Stale: last data {last_date} ({days_since} days ago, threshold {threshold}d)",
            asset_path=asset_path,
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
