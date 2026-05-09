"""Live command group — 实时行情."""
import click

from src.cli.commands.spot import spot
from src.cli.commands.intraday import intraday


@click.group(name="live")
def live_group():
    """实时行情 — 快照/盘中K线."""
    pass


live_group.add_command(spot)
live_group.add_command(intraday)
