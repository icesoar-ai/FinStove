import pandas as pd
import re

COLUMN_MAP = {
    "date": ["date", "Date", "trade_date", "datetime", "时间", "日期", "报告日"],
    "open": ["open", "Open", "开盘", "open_price"],
    "high": ["high", "High", "最高", "high_price"],
    "low": ["low", "Low", "最低", "low_price"],
    "close": ["close", "Close", "收盘", "close_price"],
    "volume": ["volume", "Volume", "成交量", "vol"],
    "adjusted_close": ["adjusted_close", "Adj Close", "复权价", "adj_close"],
}

# 财务数据格式化字符串解析（"2.44 亿", "60.42%", "-19.26%"）
UNIT_MULTIPLIERS = {
    "万亿": 1e12,
    "亿": 1e8,
    "万": 1e4,
    "千": 1e3,
}


def parse_financial_value(v) -> float | None:
    """Convert formatted Chinese financial string to float.

    Examples:
        "2.44 亿" → 244000000.0
        "60.42%" → 0.6042
        "-19.26%" → -0.1926
        "1,234.56 万" → 12345600.0
        "--" / "N/A" / "" / False → None
    """
    # Handle boolean False (common in AKShare data for missing values)
    if isinstance(v, bool):
        return None
    if not isinstance(v, str):
        return v
    v = v.strip()
    if v in ("", "-", "--", "N/A", "None", "False"):
        return None
    # Remove thousands separators
    v = v.replace(",", "")

    # Percentage
    if v.endswith("%"):
        try:
            return float(v[:-1]) / 100.0
        except ValueError:
            return None

    # Unit suffixes (longest first to match "万亿" before "亿")
    for suffix, multiplier in sorted(UNIT_MULTIPLIERS.items(), key=lambda x: -len(x[0])):
        if v.endswith(suffix):
            try:
                return float(v[:-len(suffix)]) * multiplier
            except ValueError:
                return None

    # Plain number
    try:
        return float(v)
    except ValueError:
        return None


def normalize_financials(df: pd.DataFrame) -> pd.DataFrame:
    """Convert all string columns with Chinese units to numeric values.

    Skips columns that are:
    - Date/report period columns ("报告期", "date", "日期")
    - Section headers (all values are None after parsing)

    Args:
        df: DataFrame with raw financial data (strings like "88.54 亿" or "123456.78")

    Returns:
        DataFrame with numeric values (floats)
    """
    df = df.copy()
    skip_cols = {"报告期", "report_date", "date", "日期", "报表核心指标", "报表全部指标"}

    for col in df.columns:
        if col in skip_cols:
            continue

        # Check if column has values to inspect
        sample = df[col].dropna()
        if sample.empty:
            continue

        first = sample.iloc[0]

        # Already numeric (int/float) - skip
        if isinstance(first, (int, float)):
            # But ensure the column dtype is actually numeric
            if df[col].dtype not in ('float64', 'int64'):
                df[col] = pd.to_numeric(df[col], errors='coerce')
            continue

        # Must be string - try to convert all values
        if not isinstance(first, str):
            continue

        # Apply conversion (handles "88.54 亿", "60.42%", "123456.78", etc.)
        df[col] = df[col].apply(parse_financial_value)
        # After conversion, ensure float64 dtype
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to standard English names based on COLUMN_MAP."""
    df = df.copy()
    rename = {}
    for std_name, aliases in COLUMN_MAP.items():
        for alias in aliases:
            if alias in df.columns and alias != std_name:
                rename[alias] = std_name
                break
    if rename:
        df = df.rename(columns=rename)
    return df


def normalize_dates(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Ensure date column is datetime and sorted ascending."""
    df = df.copy()
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col]).dt.date
        df = df.sort_values(date_col).reset_index(drop=True)
    return df


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Full normalization pipeline."""
    return normalize_dates(normalize_columns(df))
