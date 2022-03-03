"""aionyphe command line tool
"""
# import and setup uvloop when installed
# (linux and darwin platforms only)
try:
    from uvloop import EventLoopPolicy
    from asyncio import set_event_loop_policy

    set_event_loop_policy(EventLoopPolicy())
except ImportError:
    pass
# cross-platform imports
from asyncio import run, sleep
from pathlib import Path
from getpass import getpass
from argparse import ArgumentParser
from orjson import loads, dumps
from . import (
    OnypheAPIClientSession,
    OnypheSummaryType,
    OnypheCategory,
    OnypheAPIError,
    iter_pages,
)
from .logging import get_logger
from .__version__ import version


LOGGER = get_logger('main')
SCHEMES = {'https', 'http'}
CATEGORIES = [category.value for category in OnypheCategory]
SUMMARY_TYPES = [summary_type.value for summary_type in OnypheSummaryType]


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


def parse_timeout(arg):
    """Parse timeout argument"""
    if not arg:
        return None
    return int(arg)


def parse_port(arg):
    """Parse port argument and raise ValueError if invalid"""
    if not arg:
        return None
    arg = int(arg)
    if arg < 1 or arg > 65535:
        raise ValueError("invalid port value!")
    return arg


def parse_scheme(arg):
    """Parse scheme argument and raise ValueError if invalid"""
    if not arg:
        return None
    if not arg in SCHEMES:
        raise ValueError("invalid scheme value!")
    return arg


def parse_headers(arg):
    """Parse headers argument"""
    if not arg:
        return None
    return dict(val.split(':', 1) for val in arg.split(','))


async def _print_results(agen):
    async for _, result in agen:
        print(dumps(result).decode())


async def _myip_cmd(client, _args):
    async for meta, _ in client.user():
        print(dumps({'myip': meta['myip']}).decode())


async def _user_cmd(client, _args):
    await _print_results(client.user())


async def _summary_cmd(client, args):
    await _print_results(
        iter_pages(
            client.summary,
            [OnypheSummaryType(args.summary_type)],
            args.first,
            args.last,
        )
    )


async def _simple_cmd(client, args):
    await _print_results(
        iter_pages(
            client.simple,
            [OnypheCategory(args.category)],
            args.first,
            args.last,
        )
    )


async def _simple_best_cmd(client, args):
    await _print_results(
        iter_pages(
            client.simple_best,
            [OnypheCategory(args.category)],
            args.first,
            args.last,
        )
    )


async def _search_cmd(client, args):
    await _print_results(
        iter_pages(client.search, [args.oql], args.first, args.last)
    )


async def _alert_list_cmd(client, args):
    await _print_results(
        iter_pages(client.alert_list, [], args.first, args.last)
    )


async def _alert_add_cmd(client, args):
    await _print_results(client.alert_add(args.name, args.oql, args.email))


async def _alert_del_cmd(client, args):
    await _print_results(client.alert_del(args.identifier))


async def _bulk__simple_cmd(client, args):
    if not args.filepath.is_file():
        raise ValueError("filepath should be an existing file.")
    await _print_results(
        client.bulk_simple_ip(
            OnypheCategory(args.category),
            args.filepath,
        )
    )


async def _bulk__summary_cmd(client, args):
    if not args.filepath.is_file():
        raise ValueError("filepath should be an existing file.")
    await _print_results(
        client.bulk_summary(
            OnypheSummaryType(args.summary_type),
            args.filepath,
        )
    )


async def _bulk_simple_best_cmd(client, args):
    if not args.filepath.is_file():
        raise ValueError("filepath should be an existing file.")
    await _print_results(
        client.bulk_simple_best_ip(
            OnypheCategory(args.category),
            args.filepath,
        )
    )


async def _export_cmd(client, args):
    await _print_results(client.export(args.oql))


async def _main(args):
    config = load_conf()
    api_key = config.get('api_key') or getpass("Onyphe api key: ")
    proxy_username = args.proxy_username or config.get('proxy_username')
    proxy_password = None
    if args.proxy_username:
        proxy_password = config.get('proxy_password') or getpass(
            "Proxy password: "
        )
    kwargs = dict(
        host=args.host or config.get('host'),
        port=args.port or parse_port(config.get('port')),
        scheme=args.scheme or parse_scheme(config.get('scheme')),
        version=args.version or config.get('version'),
        api_key=api_key,
        proxy_host=args.proxy_host or config.get('proxy_host'),
        proxy_port=args.proxy_port or parse_port(config.get('proxy_port')),
        proxy_scheme=args.proxy_scheme
        or parse_scheme(config.get('proxy_scheme')),
        proxy_headers=args.proxy_headers
        or parse_headers(config.get('proxy_headers')),
        proxy_username=proxy_username,
        proxy_password=proxy_password,
        total=args.total or parse_timeout(config.get('total')),
        connect=args.connect or parse_timeout(config.get('connect')),
        sock_read=args.sock_read or parse_timeout(config.get('sock_read')),
        sock_connect=args.sock_connect
        or parse_timeout(config.get('sock_connect')),
    )
    async with OnypheAPIClientSession(**kwargs) as client:
        await args.afunc(client, args)
    # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
    # wait 500ms to ensure underlying connection is closed before closing the
    # event loop
    await sleep(0.500)


def _setup_global_arguments(parser):
    """Setup parser generic arguments"""
    parser.add_argument(
        '--host', default='www.onyphe.io', help="Onyphe API host"
    )
    parser.add_argument(
        '--port', default=443, type=parse_port, help="Onyphe API port"
    )
    parser.add_argument(
        '--scheme',
        default='https',
        type=parse_scheme,
        help="Onyphe API scheme",
    )
    parser.add_argument('--version', default='v2', help="Onyphe API version")
    parser.add_argument('--proxy-host', help="Proxy host")
    parser.add_argument('--proxy-port', type=parse_port, help="Proxy port")
    parser.add_argument(
        '--proxy-scheme', type=parse_scheme, help="Proxy scheme"
    )
    parser.add_argument(
        '--proxy-headers',
        type=parse_headers,
        help="Proxy headers comma separated key:value list",
    )
    parser.add_argument(
        '--proxy-username',
        help="Proxy username, a password prompt might appear depending on "
        "configuration file content",
    )
    parser.add_argument(
        '--total', type=parse_timeout, help="Client total timeout"
    )
    parser.add_argument(
        '--connect', type=parse_timeout, help="Client connect timeout"
    )
    parser.add_argument(
        '--sock-read', type=parse_timeout, help="Client socket read timeout"
    )
    parser.add_argument(
        '--sock-connect',
        type=parse_timeout,
        help="Client socket connect timeout",
    )


def _setup_command_parsers(cmd):
    """Define command parsers"""
    myip = cmd.add_parser('myip', help="Display current user public IP")
    myip.set_defaults(afunc=_myip_cmd)
    user = cmd.add_parser(
        'user', help="Display current user account information"
    )
    user.set_defaults(afunc=_user_cmd)
    summary = cmd.add_parser('summary', help="Query summary API")
    summary.add_argument(
        '--first', type=int, default=1, help="First page to retrieve"
    )
    summary.add_argument(
        '--last', type=int, default=1, help="Last page to retrieve"
    )
    summary.add_argument(
        'summary_type', choices=SUMMARY_TYPES, help="Type of summary query"
    )
    summary.set_defaults(afunc=_summary_cmd)
    simple = cmd.add_parser('simple', help="Query simple API")
    simple.add_argument(
        '--first', type=int, default=1, help="First page to retrieve"
    )
    simple.add_argument(
        '--last', type=int, default=1, help="Last page to retrieve"
    )
    simple.add_argument(
        'category', choices=CATEGORIES, help="Category of data to query"
    )
    simple.set_defaults(afunc=_simple_cmd)
    simple_best = cmd.add_parser('simple-best', help="Query simple best API")
    simple_best.add_argument(
        '--first', type=int, default=1, help="First page to retrieve"
    )
    simple_best.add_argument(
        '--last', type=int, default=1, help="Last page to retrieve"
    )
    simple_best.add_argument(
        'category', choices=CATEGORIES, help="Category of data to query"
    )
    simple_best.set_defaults(afunc=_simple_best_cmd)
    search = cmd.add_parser('search', help="Query search API")
    search.add_argument(
        '--first', type=int, default=1, help="First page to retrieve"
    )
    search.add_argument(
        '--last', type=int, default=1, help="Last page to retrieve"
    )
    search.add_argument('oql', help="")
    search.set_defaults(afunc=_search_cmd)
    alert_list = cmd.add_parser('alert-list', help="List configured alerts")
    alert_list.add_argument(
        '--first', type=int, default=1, help="First page to retrieve"
    )
    alert_list.add_argument(
        '--last', type=int, default=1, help="Last page to retrieve"
    )
    alert_list.set_defaults(afunc=_alert_list_cmd)
    alert_add = cmd.add_parser('alert-add', help="Configure an alert")
    alert_add.add_argument('name', help="Alert name")
    alert_add.add_argument('email', help="Alert notification recipient email")
    alert_add.add_argument('oql', help="Alert Onyphe Query Language query")
    alert_add.set_defaults(afunc=_alert_add_cmd)
    alert_del = cmd.add_parser('alert-del', help="Delete an existing alert")
    alert_del.add_argument('identifier', help="Alert identifier")
    alert_del.set_defaults(afunc=_alert_del_cmd)
    bulk_simple = cmd.add_parser('bulk-simple', help="Query bulk simple API")
    bulk_simple.add_argument(
        'category', choices=CATEGORIES, help="Category of data to query"
    )
    bulk_simple.add_argument(
        'filepath', type=Path, help="Path to file containing needles"
    )
    bulk_simple.set_defaults(afunc=_bulk__simple_cmd)
    bulk_summary = cmd.add_parser(
        'bulk-summary', help="Query bulk summary API"
    )
    bulk_summary.add_argument(
        'summary_type', choices=SUMMARY_TYPES, help="Type of summary to query"
    )
    bulk_summary.add_argument(
        'filepath', type=Path, help="Path to file containing needles"
    )
    bulk_summary.set_defaults(afunc=_bulk__summary_cmd)
    bulk_simple_best = cmd.add_parser(
        'bulk-simple-best', help="Query bulk simple best API"
    )
    bulk_simple_best.add_argument(
        'category', choices=CATEGORIES, help="Category of data to query"
    )
    bulk_simple_best.add_argument(
        'filepath', type=Path, help="Path to file containing needles"
    )
    bulk_simple_best.set_defaults(afunc=_bulk_simple_best_cmd)
    export = cmd.add_parser('export', help="Query export API")
    export.add_argument('oql', help="Onyphe Query Language query")
    export.set_defaults(afunc=_export_cmd)


def _parse_args():
    """Parse command line arguments"""
    parser = ArgumentParser(description=f"Onyphe CLI v{version}")
    _setup_global_arguments(parser)
    cmd = parser.add_subparsers(dest='cmd')
    cmd.required = True
    _setup_command_parsers(cmd)
    return parser.parse_args()


def app():
    args = _parse_args()
    try:
        run(_main(args))
    except OnypheAPIError:
        LOGGER.critical("onyphe API error.")
    except KeyboardInterrupt:
        LOGGER.warning("user interruption.")


if __name__ == '___main__':
    app()
