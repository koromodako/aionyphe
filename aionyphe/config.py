"""aionyphe config
"""
from json import loads, JSONDecodeError
from pathlib import Path
from .logging import get_logger


LOGGER = get_logger('config')


def load_config():
    """Load configuration file"""
    filepath = Path.home() / '.aionyphe'
    if filepath.is_file():
        data = filepath.read_text(encoding='utf-8')
        try:
            config = loads(data)
        except JSONDecodeError:
            LOGGER.exception("failed to load configuration file!")
            return {}
    return config
