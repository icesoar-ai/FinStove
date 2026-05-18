"""Tests for src.utils.ticker — ticker parsing and market detection."""
import pytest

from src.data.base import Market
from src.utils.ticker import detect_market, parse_ticker, stock_dir


class TestDetectMarket:
    def test_cn_shanghai_6digit(self):
        assert detect_market("600519") == Market.CN

    def test_cn_shenzhen_6digit(self):
        assert detect_market("000001") == Market.CN

    def test_cn_with_suffix(self):
        assert detect_market("601318.SH") == Market.CN
        assert detect_market("000002.SZ") == Market.CN

    def test_hk(self):
        assert detect_market("00700.HK") == Market.HK
        assert detect_market("0700.HK") == Market.HK

    def test_us(self):
        assert detect_market("AAPL") == Market.US
        assert detect_market("AAPL.US") == Market.US

    def test_jp(self):
        assert detect_market("7203.T") == Market.JP

    def test_uk(self):
        assert detect_market("VOD.L") == Market.UK

    def test_de(self):
        assert detect_market("SAP.DE") == Market.DE

    def test_fr(self):
        assert detect_market("MC.PA") == Market.FR

    def test_unknown_falls_to_us(self):
        assert detect_market("XYZ") == Market.US
        assert detect_market("ABC.XYZ") == Market.US


class TestParseTicker:
    def test_cn_strips_suffix(self):
        symbol, market = parse_ticker("600519.SH")
        assert symbol == "600519"
        assert market == Market.CN

    def test_cn_no_suffix(self):
        symbol, market = parse_ticker("000001")
        assert symbol == "000001"
        assert market == Market.CN

    def test_hk_strips_suffix(self):
        symbol, market = parse_ticker("00700.HK")
        assert symbol == "00700"
        assert market == Market.HK

    def test_us_no_suffix(self):
        symbol, market = parse_ticker("AAPL")
        assert symbol == "AAPL"
        assert market == Market.US


class TestStockDir:
    def test_shanghai_codes(self):
        assert stock_dir("601318") == "601318.SH"
        assert stock_dir("600519") == "600519.SH"
        assert stock_dir("688981") == "688981.SH"
        assert stock_dir("510050") == "510050.SH"

    def test_shenzhen_codes(self):
        assert stock_dir("000001") == "000001.SZ"
        assert stock_dir("300750") == "300750.SZ"
        assert stock_dir("159919") == "159919.SZ"

    def test_hk_short_codes(self):
        assert stock_dir("00700") == "00700.HK"
        assert stock_dir("9988") == "9988.HK"

    def test_us_alpha_codes(self):
        assert stock_dir("AAPL") == "AAPL.US"
        assert stock_dir("TSLA") == "TSLA.US"
