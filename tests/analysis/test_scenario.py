"""Tests for src.analysis.scenario — bull/base/bear cases and sensitivity."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.analysis.base import AnalysisContext
from src.analysis.scenario import ScenarioAnalyzer
from src.data.base import Market
from src.data.models import Ticker


def _make_prices(n=300, current=100, seed=42) -> pd.DataFrame:
    """Generate prices ending at `current` with 52w high/low range."""
    rng = np.random.default_rng(seed)
    daily_std = 0.02
    returns = rng.normal(0.0005, daily_std, n)
    # Force a 52w high and low
    returns[100] = 0.15   # spike up
    returns[200] = -0.12  # spike down
    prices = current * np.cumprod(1 + returns[::-1]) / np.cumprod(1 + returns[::-1])[-1] * current
    dates = [date.today() - timedelta(days=n - i) for i in range(n)]

    return pd.DataFrame({
        "date": dates,
        "open": prices * 0.999,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": [1000000] * n,
    })


def _make_ctx(prices=None) -> AnalysisContext:
    tk = Ticker(raw="600519", market=Market.CN, symbol="600519")
    return AnalysisContext(ticker=tk, price_data=prices)


class TestScenarioScoring:
    def test_bull_upside_signal(self):
        prices = _make_prices(n=300)
        result = ScenarioAnalyzer().analyze(_make_ctx(prices))
        assert any("乐观空间" in s.name for s in result.signals)

    def test_sensitivity_output(self):
        prices = _make_prices(n=300)
        result = ScenarioAnalyzer().analyze(_make_ctx(prices))
        assert "current_price" in result.details
        assert "bull_1sigma_1m" in result.details
        assert "bear_1sigma_1m" in result.details
        assert result.details["bull_1sigma_1m"] > result.details["current_price"]
        assert result.details["bear_1sigma_1m"] < result.details["current_price"]

    def test_no_price_data(self):
        result = ScenarioAnalyzer().analyze(_make_ctx(None))
        assert result.score == 0
        assert "数据不足" in result.summary
