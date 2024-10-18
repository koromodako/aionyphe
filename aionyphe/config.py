"""aionyphe config
"""

from json import JSONDecodeError, loads
from pathlib import Path

from .logging import get_logger

LOGGER = get_logger('config')


def load_config():
    """Load configuration file"""
    filepath = Path.home() / '.aionyphe'
    if not filepath.is_file():
        return {}
    data = filepath.read_text(encoding='utf-8')
    try:
        return loads(data)
    except JSONDecodeError:
        LOGGER.exception("failed to load configuration file!")
        return {}
