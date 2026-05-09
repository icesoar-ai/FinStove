"""Fetch command group — 数据抓取."""
import click

from src.cli.commands.ohlcv import ohlcv
from src.cli.commands.index_data import index_data
from src.cli.commands.commodity import commodity_data
from src.cli.commands.forex import forex_data
from src.cli.commands.crypto import crypto_data
from src.cli.commands.flow import flow_data
from src.cli.commands.yield_curve import yield_curve_data
from src.cli.commands.financials import financials
from src.cli.commands.reports import reports


@click.group(name="fetch")
def fetch_group():
    """数据抓取 — 日线/财报/年报."""
    pass


fetch_group.add_command(ohlcv)
fetch_group.add_command(index_data)
fetch_group.add_command(commodity_data)
fetch_group.add_command(forex_data)
fetch_group.add_command(crypto_data)
fetch_group.add_command(flow_data)
fetch_group.add_command(yield_curve_data)
fetch_group.add_command(financials)
fetch_group.add_command(reports)
