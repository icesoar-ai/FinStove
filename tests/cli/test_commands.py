"""CLI smoke tests — verify all commands are registered and parse correctly."""
import pytest
from click.testing import CliRunner

from src.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


# List of (group_or_cmd, args, expected_exit)
COMMANDS = [
    # Analysis
    ("analyze-stock", ["analyze-stock", "--help"], 0),
    ("macro-check", ["macro-check", "--help"], 0),
    ("valuation", ["valuation", "--help"], 0),
    ("full-report", ["full-report", "--help"], 0),
    ("sentiment", ["sentiment", "--help"], 0),
    ("report-analyze", ["report-analyze", "--help"], 0),
    ("review", ["review", "--help"], 0),
    ("correlation-check", ["correlation-check", "--help"], 0),
    ("risk-check", ["risk-check", "--help"], 0),
    ("benchmark", ["benchmark", "--help"], 0),
    ("scenario", ["scenario", "--help"], 0),
    ("market-scan", ["market-scan", "--help"], 0),
    ("summary", ["summary", "--help"], 0),
    # Tools
    ("label-data", ["label-data", "--help"], 0),
    ("validate", ["validate", "--help"], 0),
    # Fetch group
    ("fetch", ["fetch", "--help"], 0),
    ("fetch ohlcv", ["fetch", "ohlcv", "--help"], 0),
    ("fetch index", ["fetch", "index", "--help"], 0),
    ("fetch commodity", ["fetch", "commodity", "--help"], 0),
    ("fetch forex", ["fetch", "forex", "--help"], 0),
    ("fetch crypto", ["fetch", "crypto", "--help"], 0),
    ("fetch financials", ["fetch", "financials", "--help"], 0),
    ("fetch reports", ["fetch", "reports", "--help"], 0),
    ("fetch etf", ["fetch", "etf", "--help"], 0),
    ("fetch flow", ["fetch", "flow", "--help"], 0),
    ("fetch yield-curve", ["fetch", "yield-curve", "--help"], 0),
    # Live group
    ("live", ["live", "--help"], 0),
    ("live spot", ["live", "spot", "--help"], 0),
    ("live intraday", ["live", "intraday", "--help"], 0),
]


class TestCommandRegistration:
    @pytest.mark.parametrize("name,args,expected_exit", COMMANDS, ids=[c[0] for c in COMMANDS])
    def test_command_help(self, runner, name, args, expected_exit):
        result = runner.invoke(cli, args)
        assert result.exit_code == expected_exit, f"{name}: exit={result.exit_code}"

    def test_validate_custom_flag(self, runner):
        result = runner.invoke(cli, ["validate", "--errors-only"])
        assert result.exit_code == 0

    def test_validate_bad_data_dir(self, runner):
        result = runner.invoke(cli, ["validate", "--data-dir", "/no/such/path"])
        assert result.exit_code == 0  # Graceful error, no crash
