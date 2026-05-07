import pandas as pd

COLUMN_MAP = {
    "date": ["date", "Date", "trade_date", "datetime", "时间", "日期"],
    "open": ["open", "Open", "开盘", "open_price"],
    "high": ["high", "High", "最高", "high_price"],
    "low": ["low", "Low", "最低", "low_price"],
    "close": ["close", "Close", "收盘", "close_price"],
    "volume": ["volume", "Volume", "成交量", "vol"],
    "adjusted_close": ["adjusted_close", "Adj Close", "复权价", "adj_close"],
}


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
