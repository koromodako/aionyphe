"""
"""
from json import loads
from asyncio import run
from pathlib import Path
from getpass import getpass
from logging import basicConfig, getLogger
from argparse import ArgumentParser
from rich.logging import RichHandler
from .client import OnypheAPIClientSession, OnypheCategory
from .__version__ import version

basicConfig(
    level='INFO',
    format='%(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    handlers=[RichHandler()],
)

LOGGER = getLogger('aionyphe')
SCHEMES = {'https', 'http'}

def load_conf():
    """Load configuration file"""
    config = {}
    config_file = Path.home() / '.aionyphe'
    if config_file.is_file():
        try:
            config = loads(config_file.read_text())
        except:
            LOGGER.exception("failed to load configuration file!")
    return config


def parse_scheme(arg):
    """Return scheme if valid else raise ValueError"""
    if not arg in SCHEMES:
        raise ValueError
    return arg

def parse_headers(arg):
    """Parse headers argument"""
    if not arg:
        return None
    return dict(val.split(':', 1) for val in arg.split(','))


async def main(args):
    config = load_conf()
    api_key = config.get('api_key') or getpass("Onyphe api key: ")
    proxy_username = args.proxy_username or config.get('proxy_username')
    proxy_password = None
    if args.proxy_username:
        proxy_password = config.get('proxy_password') or getpass("Proxy password: ")
    oapics = OnypheAPIClientSession(
        host=args.host or config.get('host'),
        port=args.port or int(config.get('port')),
        scheme=args.scheme or parse_scheme(config.get('scheme')),
        version=args.version or config.get('version'),
        api_key=api_key,
        proxy_host=args.proxy_host or config.get('proxy_host'),
        proxy_port=args.proxy_port or int(config.get('proxy_port')),
        proxy_scheme=args.proxy_scheme or parse_scheme(config.get('proxy_scheme')),
        proxy_headers=args.proxy_headers or parse_headers(config.get('proxy_headers')),
        proxy_username=proxy_username,
        proxy_password=proxy_password,
        total=args.total or int(config.get('total')),
        connect=args.connect or int(config.get('connect')),
        sock_read=args.sock_read or int(config.get('sock_read')),
        sock_connect=args.sock_connect or int(config.get('sock_connect')),
    )
    async with oapics as client:
        async for result in client.user():
            print(result)


def parse_args():
    """Parse command line arguments"""
    parser = ArgumentParser(description=f"Onyphe CLI v{version}")
    parser.add_argument(
        '--host',
        default='www.onyphe.io',
        help="Onyphe API host",
    )
    parser.add_argument(
        '--port',
        default=443,
        type=int,
        help="Onyphe API port",
    )
    parser.add_argument(
        '--scheme',
        default='https',
        type=parse_scheme,
        help="Onyphe API scheme",
    )
    parser.add_argument(
        '--version',
        default='v2',
        help="Onyphe API version",
    )
    parser.add_argument('--proxy-host', help="Proxy host")
    parser.add_argument('--proxy-port', type=int, help="Proxy port")
    parser.add_argument(
        '--proxy-scheme',
        type=parse_scheme,
        help="Proxy scheme",
    )
    parser.add_argument(
        '--proxy-headers',
        type=parse_headers,
        help="Proxy headers comma separated key:value list",
    )
    parser.add_argument('--proxy-username', help="Proxy username")
    parser.add_argument('--total', type=int, help="Client total timeout")
    parser.add_argument('--connect', type=int, help="Client connect timeout")
    parser.add_argument(
        '--sock-read', type=int, help="Client socket read timeout"
    )
    parser.add_argument(
        '--sock-connect', type=int, help="Client socket connect timeout"
    )
    return parser.parse_args()


def app():
    args = parse_args()
    run(main(args))


if __name__ == '__main__':
    app()
