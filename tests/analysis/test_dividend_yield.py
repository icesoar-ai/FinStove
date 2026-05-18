from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.analysis.dividend_yield import (
    validate_daily,
    validate_dividends,
    recover_raw_prices,
    compute_dividend_yield,
    summarize,
    ValidationIssue,
    DataValidationError,
    DividendYieldSummary,
)


# ——— helpers ———

def _make_daily(n=500, start_price=10.0):
    """Generate synthetic qfq daily data."""
    rng = np.random.default_rng(42)
    returns = rng.normal(0.0002, 0.015, n)
    close = start_price * np.cumprod(1 + returns)
    dates = [date(2020, 1, 2) + timedelta(days=i) for i in range(n)]
    return pd.DataFrame({
        "date": dates,
        "open": close * 0.999,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": [1_000_000] * n,
    })


def _make_dividends(ex_dates=None, dps=None, song=None, zhuan=None):
    """Generate synthetic dividends data. dps in per-10-shares units."""
    if ex_dates is None:
        ex_dates = [date(2021, 7, 10), date(2022, 7, 10)]
    if dps is None:
        dps = [5.0, 6.0]
    if song is None:
        song = [0] * len(ex_dates)
    if zhuan is None:
        zhuan = [0] * len(ex_dates)
    return pd.DataFrame({
        "除权除息日": ex_dates,
        "派息": dps,
        "送股": song,
        "转增": zhuan,
        "公告日期": ex_dates,
        "进度": ["实施"] * len(ex_dates),
        "股权登记日": [d - timedelta(days=1) for d in ex_dates],
        "红股上市日": [None] * len(ex_dates),
    })


# ——— validation ———

class TestValidateDaily:
    def test_all_good(self):
        daily = _make_daily()
        issues = validate_daily(daily)
        assert len(issues) == 0

    def test_missing_close(self):
        daily = _make_daily().drop(columns=["close"])
        issues = validate_daily(daily)
        fatal = [i for i in issues if i.level == "fatal"]
        assert any("close" in i.message for i in fatal)

    def test_high_lt_low(self):
        daily = _make_daily()
        daily.loc[10, "low"] = daily.loc[10, "high"] + 10
        issues = validate_daily(daily)
        fatal = [i for i in issues if i.level == "fatal"]
        assert any("high < low" in i.message for i in fatal)

    def test_close_out_of_range(self):
        daily = _make_daily()
        daily.loc[5, "close"] = daily.loc[5, "high"] + 100
        issues = validate_daily(daily)
        fatal = [i for i in issues if i.level == "fatal"]
        assert any("超出" in i.message for i in fatal)


class TestValidateDividends:
    def test_all_good(self):
        divs = _make_dividends()
        issues = validate_dividends(divs)
        assert len(issues) == 0

    def test_missing_column(self):
        divs = _make_dividends().drop(columns=["派息"])
        issues = validate_dividends(divs)
        fatal = [i for i in issues if i.level == "fatal"]
        assert any("派息" in i.message for i in fatal)

    def test_negative_dps(self):
        divs = _make_dividends(dps=[5.0, -3.0])
        issues = validate_dividends(divs)
        fatal = [i for i in issues if i.level == "fatal"]
        assert any("派息为负" in i.message for i in fatal)

    def test_stale_data(self):
        divs = _make_dividends(ex_dates=[date(2019, 7, 10)], dps=[5.0])
        issues = validate_dividends(divs, latest_price_date=date(2025, 1, 1))
        warns = [i for i in issues if i.level == "warn"]
        assert any("过时" in i.message for i in warns)


# ——— qfq → raw price recovery ———

class TestRecoverRawPrices:
    def test_no_dividends_identity(self):
        daily = _make_daily(n=100, start_price=20)
        divs = _make_dividends(ex_dates=[], dps=[])
        raw, sf = recover_raw_prices(daily, divs)
        np.testing.assert_array_almost_equal(raw, daily["close"].values)
        np.testing.assert_array_almost_equal(sf, np.ones(len(daily)))

    def test_cash_dividend_only(self):
        daily = _make_daily(n=100, start_price=20)
        # 在 20 天后有一次除权，派息 5 元/10股 = 0.5/股
        divs = _make_dividends(
            ex_dates=[date(2020, 1, 22)],
            dps=[5.0],
        )
        raw, sf = recover_raw_prices(daily, divs)

        # 除权日之后的价格不变
        assert raw[21] == pytest.approx(daily["close"].iloc[21], rel=1e-6)
        # 除权日之前的价格增加 0.5
        assert raw[0] == pytest.approx(daily["close"].iloc[0] + 0.5, rel=1e-6)

    def test_with_songgu(self):
        daily = _make_daily(n=30, start_price=20)
        # 10送10 (送股=10), 前复权会把之前价格除以 2
        divs = _make_dividends(
            ex_dates=[date(2020, 1, 12)],
            dps=[0],
            song=[10],
            zhuan=[0],
        )
        raw, sf = recover_raw_prices(daily, divs)

        # 除权前 scale factor = 2 (1 旧股 = 2 新股)
        assert sf[0] == pytest.approx(2.0)
        # 除权后 scale factor = 1
        assert sf[11] == pytest.approx(1.0)
        # 除权前原始价格 = qfq * 2
        assert raw[0] == pytest.approx(daily["close"].iloc[0] * 2.0, rel=1e-4)
        # 除权后原始价格不变
        assert raw[11] == pytest.approx(daily["close"].iloc[11], rel=1e-4)

    def test_real_data_cmb(self):
        """Verify real 600036 data recovery gives sane prices."""
        daily = pd.read_parquet("data/stock/cn/600036.SH/daily.parquet")
        divs = pd.read_parquet("data/stock/cn/600036.SH/dividends.parquet")

        raw, sf = recover_raw_prices(daily, divs)

        # 所有反推价格非负
        assert (raw >= 0).all()

        # 最新价格不变（前复权的最后一天就是原始价格）
        assert raw[-1] == pytest.approx(daily["close"].iloc[-1], rel=1e-6)

        # 2010-01-04 价格应在 15-20 区间（招行实际 IPO 价格）
        assert 10 < raw[0] < 30

        # 送股/转增为 0，缩放因子恒为 1
        assert (sf == 1.0).all()


# ——— TTM yield ———

class TestComputeDividendYield:
    def test_single_dividend(self):
        daily = _make_daily(n=400, start_price=20)
        divs = _make_dividends(
            ex_dates=[date(2021, 1, 10)],
            dps=[10.0],  # 1.0 per share
        )
        raw, sf = recover_raw_prices(daily, divs)
        yld, ttm = compute_dividend_yield(daily, divs, raw, sf)

        # 分红后 365 天内的 yield = 1.0/price
        idx_after = 380  # ~2021-01-17, still within 365 days
        assert yld[idx_after] > 0

    def test_forward_fill_gap(self):
        daily = _make_daily(n=800, start_price=20)
        # 单次分红，超过 365 天后应该向前填充
        divs = _make_dividends(
            ex_dates=[date(2020, 7, 1)],
            dps=[10.0],
        )
        raw, sf = recover_raw_prices(daily, divs)
        yld, ttm = compute_dividend_yield(daily, divs, raw, sf)

        # gap 之后非零（已被填充）
        idx_far = 750  # well past 365 days from 2020-07-01
        assert yld[idx_far] > 0

    def test_dps_normalized_by_scale_factor(self):
        daily = _make_daily(n=60, start_price=20)
        # 10送10 on 2020-01-12, then 派息 1.0/share on 2020-02-01
        # 对于 split 之前的日期(d<2020-01-12): sf=2 → DPS_norm = 1.0 * 2 = 2.0
        # 对于 split 之后、分红之前的日期: sf=1 → DPS 需等分红入账
        divs = _make_dividends(
            ex_dates=[date(2020, 1, 12), date(2020, 2, 1)],
            dps=[0, 10.0],
            song=[10, 0],
            zhuan=[0, 0],
        )
        raw, sf = recover_raw_prices(daily, divs)
        yld, ttm = compute_dividend_yield(daily, divs, raw, sf)

        # idx 50 is after both events (2020-02-21), within 365 days of the dividend
        # sf at this date = 1.0 (post-split), DPS = 1.0 * 1.0 = 1.0
        idx = 50
        assert sf[idx] == pytest.approx(1.0)
        assert ttm[idx] == pytest.approx(1.0, rel=1e-2)


# ——— summary ———

class TestSummarize:
    def test_basic(self):
        dates = np.array([date(2020, 1, 1) + timedelta(days=i) for i in range(100)])
        yld = np.linspace(2, 6, 100)
        ttm = np.ones(100) * 0.5
        close = np.linspace(8, 12, 100)

        s = summarize(dates, yld, ttm, close)

        assert s.current == pytest.approx(6.0)
        assert s.max_val == pytest.approx(6.0)
        assert s.min_val == pytest.approx(2.0)
        assert 3 < s.mean < 5
        assert s.percentile > 95


# ——— DataValidationError ———

class TestDataValidationError:
    def test_formatting(self):
        issues = [
            ValidationIssue("fatal", "daily", "缺少 close 列"),
            ValidationIssue("warn", "dividends", "数据可能过时"),
        ]
        err = DataValidationError(issues)
        msg = str(err)
        assert "缺少 close 列" in msg
        assert "数据可能过时" in msg
