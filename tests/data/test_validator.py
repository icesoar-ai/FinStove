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
        df = _make_df(high=[98.0, 103.0, 104.0, 103.0, 104.5])
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
        # Introduce issues across multiple checkers: high<low, negative volume,
        # non-monotonic dates, stale data — validating that validate_daily
        # delegates to all sub-validators.
        old_dates = [date.today() - timedelta(days=i) for i in range(30, 25, -1)]
        df = _make_df(
            high=[98.0, 103.0, 104.0, 103.0, 104.5],
            volume=[1, -1, 1, 1, 1],
            date=sorted(old_dates, reverse=True),  # non-monotonic + stale
        )
        issues = validate_daily(df, "test")
        # Expect: high<low, negative volume, non-monotonic dates, stale
        assert len(issues) >= 3
