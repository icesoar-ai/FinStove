from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class ValidationIssue:
    level: str       # "fatal" | "warn"
    file: str        # "daily" | "dividends"
    message: str


class DataValidationError(Exception):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        fatal = [i for i in issues if i.level == "fatal"]
        msg = "\n".join(f"  [{i.level}] {i.file}: {i.message}" for i in issues)
        super().__init__(f"数据校验失败 ({len(fatal)} 致命, {len(issues) - len(fatal)} 警告):\n{msg}")


def validate_daily(df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if "date" not in df.columns:
        issues.append(ValidationIssue("fatal", "daily", "缺少 date 列"))
    if "close" not in df.columns:
        issues.append(ValidationIssue("fatal", "daily", "缺少 close 列"))

    if "high" in df.columns and "low" in df.columns:
        bad = df[df["high"] < df["low"]]
        if len(bad) > 0:
            issues.append(ValidationIssue(
                "fatal", "daily",
                f"high < low 的行数: {len(bad)}, 涉及日期: {bad.iloc[0]['date']} ~ {bad.iloc[-1]['date']}"
            ))

    if "close" in df.columns and "high" in df.columns and "low" in df.columns:
        eps = 1e-6  # 容差：避免 float 序列化/反序列化的精度误差（~1e-15）
        out_of_range = df[(df["close"] + eps < df["low"]) | (df["close"] > df["high"] + eps)]
        if len(out_of_range) > 0:
            issues.append(ValidationIssue(
                "fatal", "daily",
                f"close 超出 [low, high] 范围的行数: {len(out_of_range)}"
            ))

    return issues


def validate_dividends(df: pd.DataFrame, latest_price_date=None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if "除权除息日" not in df.columns:
        issues.append(ValidationIssue("fatal", "dividends", "缺少 除权除息日 列"))
    if "派息" not in df.columns:
        issues.append(ValidationIssue("fatal", "dividends", "缺少 派息 列"))
    if "送股" not in df.columns:
        issues.append(ValidationIssue("fatal", "dividends", "缺少 送股 列"))
    if "转增" not in df.columns:
        issues.append(ValidationIssue("fatal", "dividends", "缺少 转增 列"))

    if "派息" in df.columns:
        neg = df[df["派息"] < 0]
        if len(neg) > 0:
            issues.append(ValidationIssue("fatal", "dividends", f"派息为负的行数: {len(neg)}"))

    if latest_price_date is not None and "除权除息日" in df.columns:
        ex_dates = pd.to_datetime(df["除权除息日"])
        latest_ex = ex_dates.max()
        if not isinstance(latest_price_date, pd.Timestamp):
            latest_price_date = pd.Timestamp(latest_price_date)
        gap = (latest_price_date - latest_ex).days
        if gap > 400:
            issues.append(ValidationIssue(
                "warn", "dividends",
                f"最新除权日 ({latest_ex.date()}) 距最新价格日 ({latest_price_date.date()}) {gap} 天, 分红数据可能过时"
            ))

    return issues


def recover_raw_prices(
    daily: pd.DataFrame,
    dividends: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """从 qfq 价格反推不复权价格和股本缩放因子.

    Returns:
        raw_prices: 与 daily 等长的 notional 复权价格数组
        scale_factors: 与 daily 等长的股本缩放因子 (历史 1 股 → 今天 N 股)
    """
    dates = pd.to_datetime(daily["date"].values)
    close = daily["close"].values.copy().astype(float)
    n = len(dates)

    raw_prices = close.copy()
    scale_factors = np.ones(n, dtype=float)

    if dividends.empty:
        return raw_prices, scale_factors

    ex_dates = pd.to_datetime(dividends["除权除息日"].values)
    dps_raw = dividends["派息"].values / 10.0       # 每 10 股 → 每股
    song = dividends["送股"].values
    zhuan = dividends["转增"].values

    for i in range(n):
        d = dates[i]
        px = raw_prices[i]
        sf = 1.0

        for j in range(len(ex_dates)):
            if ex_dates[j] > d:
                # 先反推现金分红
                px += dps_raw[j] / sf
                # 再反推送转
                sr = song[j]
                zr = zhuan[j]
                if sr > 0 or zr > 0:
                    ratio = 1.0 + sr / 10.0 + zr / 10.0
                    px *= ratio
                    sf *= ratio

        raw_prices[i] = px
        scale_factors[i] = sf

    return raw_prices, scale_factors


def compute_dividend_yield(
    daily: pd.DataFrame,
    dividends: pd.DataFrame,
    raw_prices: np.ndarray,
    scale_factors: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """计算 TTM 股息率序列.

    Returns:
        yield_pct: 股息率 (%) 数组
        ttm_dps: TTM 每股股息数组
    """
    dates = pd.to_datetime(daily["date"].values)
    n = len(dates)

    ttm_dps = np.zeros(n, dtype=float)

    if dividends.empty:
        yield_pct = ttm_dps / raw_prices * 100
        return yield_pct, ttm_dps

    ex_dates = pd.to_datetime(dividends["除权除息日"].values)
    dps_raw = dividends["派息"].values / 10.0

    # 对每个交易日，求过去 365 天内的除权日 (ex_date > date-365, ex_date <= date)
    for i in range(n):
        d = dates[i]
        year_ago = d - timedelta(days=365)
        total = 0.0
        for j in range(len(ex_dates)):
            if year_ago < ex_dates[j] <= d:
                # 归一化到当前股本
                total += dps_raw[j] * scale_factors[i]
        ttm_dps[i] = total

    yield_pct = ttm_dps / raw_prices * 100

    # 前向填充间隙（无分红覆盖的交易日）
    nonzero = ttm_dps > 0
    if nonzero.any():
        idx = np.where(nonzero)[0]
        # fill forward: for each zero position, use last non-zero
        last_val = 0.0
        last_ttm = 0.0
        for i in range(n):
            if ttm_dps[i] > 0:
                last_val = yield_pct[i]
                last_ttm = ttm_dps[i]
            else:
                yield_pct[i] = last_val
                ttm_dps[i] = last_ttm

    return yield_pct, ttm_dps


@dataclass
class DividendYieldSummary:
    current: float
    max_val: float
    max_date: str
    min_val: float
    min_date: str
    mean: float
    median: float
    percentile: float


def summarize(
    dates: np.ndarray,
    yield_pct: np.ndarray,
    ttm_dps: np.ndarray,
    close: np.ndarray,
) -> DividendYieldSummary:
    idx = np.isfinite(yield_pct) & (yield_pct > 0)
    valid = yield_pct[idx]
    valid_dates = dates[idx]

    if len(valid) == 0:
        return DividendYieldSummary(0, 0, "", 0, "", 0, 0, 0)

    pct_rank = (valid < yield_pct[-1]).mean() * 100

    return DividendYieldSummary(
        current=yield_pct[-1],
        max_val=valid.max(),
        max_date=str(valid_dates[valid.argmax()]),
        min_val=valid.min(),
        min_date=str(valid_dates[valid.argmin()]),
        mean=float(np.mean(valid)),
        median=float(np.median(valid)),
        percentile=pct_rank,
    )
