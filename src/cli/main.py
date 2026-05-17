import os
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).resolve().parents[2] / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

import click

# Groups
from src.cli.commands.fetch_group import fetch_group
from src.cli.commands.live_group import live_group

# Top-level analysis commands
from src.cli.commands.stock import analyze_stock
from src.cli.commands.macro import macro_check
from src.cli.commands.valuation import valuation
from src.cli.commands.full_report import full_report
from src.cli.commands.sentiment import sentiment
from src.cli.commands.report_analyze import report_analyze
from src.cli.commands.review import review
from src.cli.commands.correlation import correlation_check
from src.cli.commands.risk import risk_check
from src.cli.commands.benchmark import benchmark
from src.cli.commands.scenario import scenario

# Top-level tools
from src.cli.commands.market_scan import market_scan
from src.cli.commands.summary import daily_summary
from src.cli.commands.label_data import label_data


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version="0.1.0")
def cli():
    """金融分析助手 CLI — 多市场金融分析系统."""


# Groups
cli.add_command(fetch_group)
cli.add_command(live_group)

# Analysis
cli.add_command(analyze_stock)
cli.add_command(macro_check)
cli.add_command(valuation)
cli.add_command(full_report)
cli.add_command(sentiment)
cli.add_command(report_analyze)
cli.add_command(review)
cli.add_command(correlation_check)
cli.add_command(risk_check)
cli.add_command(benchmark)
cli.add_command(scenario)

# Tools
cli.add_command(market_scan)
cli.add_command(daily_summary)
cli.add_command(label_data)


if __name__ == "__main__":
    cli()
