"""aionyphe logging module
"""

from logging import Logger, basicConfig, getLogger

from rich.console import Console
from rich.logging import RichHandler

basicConfig(
    level='INFO',
    format='%(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    handlers=[RichHandler(console=Console(stderr=True))],
)


def get_logger(name: str) -> Logger:
    """Retrieve logger for given name"""
    name = '.'.join(['aionyphe'] + name.split('.'))
    return getLogger(name)
