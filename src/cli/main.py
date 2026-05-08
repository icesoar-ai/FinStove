import os
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).resolve().parents[3] / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

import click

from src.cli.commands.stock import analyze_stock
from src.cli.commands.macro import macro_check
from src.cli.commands.financials import financials
from src.cli.commands.valuation import valuation
from src.cli.commands.ohlcv import ohlcv
from src.cli.commands.reports import reports
from src.cli.commands.full_report import full_report
from src.cli.commands.review import review
from src.cli.commands.index_data import index_data
from src.cli.commands.flow import flow_data
from src.cli.commands.us_index import us_index


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """金融分析助手 CLI."""


cli.add_command(analyze_stock)
cli.add_command(macro_check)
cli.add_command(financials)
cli.add_command(valuation)
cli.add_command(ohlcv)
cli.add_command(reports)
cli.add_command(full_report)
cli.add_command(review)
cli.add_command(index_data)
cli.add_command(flow_data)
cli.add_command(us_index)


if __name__ == "__main__":
    cli()
