"""Tests for src.analysis.risk — VaR, CVaR, max drawdown, volatility."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.analysis.base import AnalysisContext
from src.analysis.risk import RiskAnalyzer
from src.data.base import Market
from src.data.models import Ticker


def _make_prices(n=252, seed=42, annual_return=0.0, annual_vol=0.30) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    daily_ret = annual_return / 252
    daily_std = annual_vol / np.sqrt(252)
    returns = rng.normal(daily_ret, daily_std, n)
    prices = 100 * np.cumprod(1 + returns)
    dates = [date.today() - timedelta(days=n - i) for i in range(n)]

    # Generate matching volume
    vol = rng.integers(500000, 2000000, n)
    return pd.DataFrame({
        "date": dates,
        "open": prices * 0.999,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": vol,
    })


def _make_ctx(prices=None) -> AnalysisContext:
    tk = Ticker(raw="600519", market=Market.CN, symbol="600519")
    return AnalysisContext(ticker=tk, price_data=prices)


class TestVaR:
    def test_var_at_95(self):
        prices = _make_prices(n=252, seed=123)
        result = RiskAnalyzer().analyze(_make_ctx(prices))
        assert any("VaR(95%)" in s.name for s in result.signals)

    def test_var_not_enough_data(self):
        prices = _make_prices(n=15)
        result = RiskAnalyzer().analyze(_make_ctx(prices))
        # VaR needs 60, vol needs 20, liquidity needs 20 — all should skip with n=15
        assert len(result.signals) == 0


class TestMaxDrawdown:
    def test_max_drawdown_present(self):
        prices = _make_prices(n=252)
        result = RiskAnalyzer().analyze(_make_ctx(prices))
        assert any("最大回撤" in s.name for s in result.signals)


class TestVolatility:
    def test_volatility_present(self):
        prices = _make_prices(n=252)
        result = RiskAnalyzer().analyze(_make_ctx(prices))
        assert any("波动" in s.name for s in result.signals)


class TestNoPriceData:
    def test_empty_returns_zero(self):
        result = RiskAnalyzer().analyze(_make_ctx(None))
        assert result.score == 0
        assert "无价格数据" in result.summary
