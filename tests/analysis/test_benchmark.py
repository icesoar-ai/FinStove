"""Tests for src.analysis.benchmark — benchmark comparison scoring."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.analysis.base import AnalysisContext, AnalysisResult
from src.analysis.benchmark import BenchmarkAnalyzer
from src.data.base import Dimension, Market
from src.data.models import Ticker


def _make_prices(n=252, annual_return=0.1, seed=42) -> pd.DataFrame:
    """Generate synthetic daily OHLCV with given total return (pct_change sum)."""
    rng = np.random.default_rng(seed)
    # Distribute annual_return across n days with small noise
    base = np.full(n, annual_return / n)
    noise = rng.normal(0, 0.0005, n)
    noise -= noise.mean()  # Zero-mean noise so total = annual_return
    daily_returns = base + noise
    prices = 100 * np.cumprod(1 + daily_returns)
    dates = [date.today() - timedelta(days=n - i) for i in range(n)]

    df = pd.DataFrame({
        "date": dates,
        "open": prices * 0.999,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": [1000000] * n,
    })
    return df


def _make_ctx(prices=None, macro=None) -> AnalysisContext:
    tk = Ticker(raw="600519", market=Market.CN, symbol="600519")
    return AnalysisContext(ticker=tk, price_data=prices, macro_data=macro or {})


class TestBenchmarkScoring:
    def test_outperform_index(self):
        prices = _make_prices(n=252, annual_return=0.30)
        ctx = _make_ctx(prices, {"benchmark_returns": 0.10})
        result = BenchmarkAnalyzer().analyze(ctx)
        assert result.score > 0.2
        assert any("跑赢指数" in s.name for s in result.signals)

    def test_underperform_index(self):
        prices = _make_prices(n=252, annual_return=0.05)
        ctx = _make_ctx(prices, {"benchmark_returns": 0.20})
        result = BenchmarkAnalyzer().analyze(ctx)
        assert result.score < -0.2
        assert any("跑输指数" in s.name for s in result.signals)

    def test_no_benchmark_data(self):
        prices = _make_prices()
        ctx = _make_ctx(prices, {})
        result = BenchmarkAnalyzer().analyze(ctx)
        assert result.score == 0

    def test_no_price_data(self):
        ctx = _make_ctx(None, {"benchmark_returns": 0.10})
        result = BenchmarkAnalyzer().analyze(ctx)
        assert result.score == 0
        assert "数据不足" in result.summary


class TestRiskFreeComparison:
    def test_equity_risk_premium_bullish(self):
        prices = _make_prices()
        ctx = _make_ctx(prices, {
            "benchmark_returns": 0.05,
            "risk_free_rate": 0.03,
            "earnings_yield": 0.08,
        })
        result = BenchmarkAnalyzer().analyze(ctx)
        assert any("股债性价比" in s.name and s.direction == "bullish" for s in result.signals)

    def test_equity_risk_inverted(self):
        prices = _make_prices()
        ctx = _make_ctx(prices, {
            "benchmark_returns": 0.05,
            "risk_free_rate": 0.10,
            "earnings_yield": 0.03,
        })
        result = BenchmarkAnalyzer().analyze(ctx)
        assert any("股债倒挂" in s.name for s in result.signals)
