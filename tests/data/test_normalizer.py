"""Tests for src.data.normalizer — column, date, and financial value normalization."""
from datetime import date

import pandas as pd
import pytest

from src.data.normalizer import (
    normalize_columns,
    normalize_dates,
    normalize_financials,
    parse_financial_value,
    standardize,
)


class TestNormalizeColumns:
    def test_chinese_columns(self):
        df = pd.DataFrame({
            "日期": ["2024-01-01"], "开盘": [100.0], "最高": [102.0],
            "最低": [99.0], "收盘": [101.0], "成交量": [1000000],
        })
        result = normalize_columns(df)
        assert set(result.columns) == {"date", "open", "high", "low", "close", "volume"}

    def test_english_aliases(self):
        df = pd.DataFrame({
            "trade_date": ["2024-01-01"], "Close": [101.0], "vol": [1000000],
        })
        result = normalize_columns(df)
        assert "date" in result.columns
        assert "close" in result.columns
        assert "volume" in result.columns

    def test_already_normalized(self):
        df = pd.DataFrame({"date": ["2024-01-01"], "open": [100.0], "close": [101.0]})
        result = normalize_columns(df)
        assert list(result.columns) == ["date", "open", "close"]


class TestNormalizeDates:
    def test_yyyymmdd_strings(self):
        df = pd.DataFrame({"date": ["20240103", "20240101", "20240102"]})
        result = normalize_dates(df)
        assert result["date"].iloc[0] == date(2024, 1, 1)
        assert result["date"].iloc[2] == date(2024, 1, 3)

    def test_iso_dates(self):
        df = pd.DataFrame({"date": ["2024-01-03", "2024-01-01", "2024-01-02"]})
        result = normalize_dates(df)
        assert result["date"].iloc[0] == date(2024, 1, 1)
        assert result["date"].iloc[2] == date(2024, 1, 3)

    def test_no_date_column(self):
        df = pd.DataFrame({"value": [1, 2, 3]})
        result = normalize_dates(df)
        assert "date" not in result.columns


class TestParseFinancialValue:
    def test_yi(self):
        assert parse_financial_value("2.44 亿") == 244000000.0

    def test_wan(self):
        assert parse_financial_value("5000 万") == 50000000.0

    def test_qian(self):
        assert parse_financial_value("3000 千") == 3000000.0

    def test_percentage(self):
        assert parse_financial_value("60.42%") == pytest.approx(0.6042)
        assert parse_financial_value("-19.26%") == pytest.approx(-0.1926)

    def test_null_markers(self):
        assert parse_financial_value("--") is None
        assert parse_financial_value("N/A") is None
        assert parse_financial_value("") is None

    def test_plain_number(self):
        assert parse_financial_value("123.45") == 123.45

    def test_boolean_false(self):
        assert parse_financial_value(False) is None

    def test_already_numeric(self):
        assert parse_financial_value(42.5) == 42.5


class TestStandardize:
    def test_full_pipeline(self):
        df = pd.DataFrame({
            "日期": ["20240101"],
            "开盘": [100.0],
            "收盘": [101.0],
        })
        result = standardize(df)
        assert "date" in result.columns
        assert "open" in result.columns
        assert "close" in result.columns
        assert result["date"].iloc[0] == date(2024, 1, 1)
