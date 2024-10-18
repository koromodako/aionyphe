"""aionyphe command line tool
"""

# import and setup uvloop when installed
# (linux and darwin platforms only)
try:
    from asyncio import set_event_loop_policy

    from uvloop import EventLoopPolicy

    set_event_loop_policy(EventLoopPolicy())
except ImportError:
    pass
finally:
    from asyncio import run, sleep
# cross-platform imports
from argparse import ArgumentParser
from getpass import getpass
from json import dumps
from pathlib import Path

from . import (
    OnypheAPIClient,
    OnypheAPIClientProxy,
    OnypheAPIError,
    OnypheCategory,
    OnypheSummaryType,
    client_session,
    iter_pages,
)
from .__version__ import version
from .client import BEST_CATEGORIES
from .config import load_config
from .logging import get_logger

LOGGER = get_logger('main')
SCHEMES = {'https', 'http'}
CATEGORIES = [category.value for category in OnypheCategory]
SUMMARY_TYPES = [summary_type.value for summary_type in OnypheSummaryType]
BEST_CATEGORIES = [category.value for category in BEST_CATEGORIES]


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
        print(dumps(result))


async def _myip_cmd(client, _args):
    async for meta, _ in client.user():
        print(dumps({'myip': meta['myip']}))


async def _user_cmd(client, _args):
    await _print_results(client.user())


async def _summary_cmd(client, args):
    await _print_results(
        iter_pages(
            client.summary,
            [OnypheSummaryType(args.summary_type), args.needle],
            args.first,
            args.last,
        )
    )


async def _simple_cmd(client, args):
    await _print_results(
        iter_pages(
            client.simple,
            [OnypheCategory(args.category), args.needle],
            args.first,
            args.last,
        )
    )


async def _simple_best_cmd(client, args):
    await _print_results(
        iter_pages(
            client.simple_best,
            [OnypheCategory(args.category), args.ipaddr],
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


async def _bulk_simple_cmd(client, args):
    if not args.filepath.is_file():
        raise ValueError("filepath should be an existing file.")
    await _print_results(
        client.bulk_simple_ip(
            OnypheCategory(args.category),
            args.filepath,
        )
    )


async def _bulk_summary_cmd(client, args):
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


async def _bulk_discovery_asset_cmd(client, args):
    if not args.filepath.is_file():
        raise ValueError("filepath should be an existing file.")
    await _print_results(
        client.bulk_discovery_asset(
            OnypheCategory(args.category),
            args.filepath,
        )
    )


async def _export_cmd(client, args):
    await _print_results(client.export(args.oql))


async def _main(args):
    config = load_config()
    api_key = config.get('api_key') or getpass("Onyphe api key: ")
    proxy_password = None
    proxy_username = args.proxy_username or config.get('proxy_username')
    if proxy_username:
        proxy_password = config.get('proxy_password') or getpass(
            "Proxy password: "
        )
    proxy = OnypheAPIClientProxy(
        scheme=args.proxy_scheme or parse_scheme(config.get('proxy_scheme')),
        host=args.proxy_host or config.get('proxy_host'),
        port=args.proxy_port or parse_port(config.get('proxy_port')),
        headers=(
            args.proxy_headers or parse_headers(config.get('proxy_headers'))
        ),
        username=proxy_username,
        password=proxy_password,
    )
    async with client_session(
        api_key,
        scheme=args.scheme or parse_scheme(config.get('scheme')),
        host=args.host or config.get('host'),
        port=args.port or parse_port(config.get('port')),
        total=args.total or parse_timeout(config.get('total')),
        connect=args.connect or parse_timeout(config.get('connect')),
        sock_read=args.sock_read or parse_timeout(config.get('sock_read')),
        sock_connect=(
            args.sock_connect or parse_timeout(config.get('sock_connect'))
        ),
    ) as client:
        api_client = OnypheAPIClient(client=client, proxy=proxy)
        await args.afunc(api_client, args)
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
    # myip
    myip = cmd.add_parser('myip', help="Display current user public IP")
    myip.set_defaults(afunc=_myip_cmd)
    # user
    user = cmd.add_parser(
        'user', help="Display current user account information"
    )
    user.set_defaults(afunc=_user_cmd)
    # summary
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
    summary.add_argument('needle', help="Needle to be found")
    summary.set_defaults(afunc=_summary_cmd)
    # simple
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
    simple.add_argument('needle', help="Needle to be found")
    simple.set_defaults(afunc=_simple_cmd)
    # simple-best
    simple_best = cmd.add_parser('simple-best', help="Query simple best API")
    simple_best.add_argument(
        '--first', type=int, default=1, help="First page to retrieve"
    )
    simple_best.add_argument(
        '--last', type=int, default=1, help="Last page to retrieve"
    )
    simple_best.add_argument(
        'category', choices=BEST_CATEGORIES, help="Category of data to query"
    )
    simple_best.add_argument('ipaddr', help="IP address")
    simple_best.set_defaults(afunc=_simple_best_cmd)
    # search
    search = cmd.add_parser('search', help="Query search API")
    search.add_argument(
        '--first', type=int, default=1, help="First page to retrieve"
    )
    search.add_argument(
        '--last', type=int, default=1, help="Last page to retrieve"
    )
    search.add_argument('oql', help="")
    search.set_defaults(afunc=_search_cmd)
    # alert-list
    alert_list = cmd.add_parser('alert-list', help="List configured alerts")
    alert_list.add_argument(
        '--first', type=int, default=1, help="First page to retrieve"
    )
    alert_list.add_argument(
        '--last', type=int, default=1, help="Last page to retrieve"
    )
    alert_list.set_defaults(afunc=_alert_list_cmd)
    # alert-add
    alert_add = cmd.add_parser('alert-add', help="Configure an alert")
    alert_add.add_argument('name', help="Alert name")
    alert_add.add_argument('email', help="Alert notification recipient email")
    alert_add.add_argument('oql', help="Alert Onyphe Query Language query")
    alert_add.set_defaults(afunc=_alert_add_cmd)
    # alert-del
    alert_del = cmd.add_parser('alert-del', help="Delete an existing alert")
    alert_del.add_argument('identifier', help="Alert identifier")
    alert_del.set_defaults(afunc=_alert_del_cmd)
    # bulk-simple
    bulk_simple = cmd.add_parser('bulk-simple', help="Query bulk simple API")
    bulk_simple.add_argument(
        'category', choices=CATEGORIES, help="Category of data to query"
    )
    bulk_simple.add_argument(
        'filepath', type=Path, help="Path to file containing needles"
    )
    bulk_simple.set_defaults(afunc=_bulk_simple_cmd)
    # bulk-summary
    bulk_summary = cmd.add_parser(
        'bulk-summary', help="Query bulk summary API"
    )
    bulk_summary.add_argument(
        'summary_type', choices=SUMMARY_TYPES, help="Type of summary to query"
    )
    bulk_summary.add_argument(
        'filepath', type=Path, help="Path to file containing needles"
    )
    bulk_summary.set_defaults(afunc=_bulk_summary_cmd)
    # bulk-simple-best
    bulk_simple_best = cmd.add_parser(
        'bulk-simple-best', help="Query bulk simple best API"
    )
    bulk_simple_best.add_argument(
        'category', choices=BEST_CATEGORIES, help="Category of data to query"
    )
    bulk_simple_best.add_argument(
        'filepath', type=Path, help="Path to file containing needles"
    )
    bulk_simple_best.set_defaults(afunc=_bulk_simple_best_cmd)
    # bulk-discovery-asset
    bulk_discovery_asset = cmd.add_parser(
        'bulk-discovery-asset', help="Query bulk discovery asset API"
    )
    bulk_discovery_asset.add_argument(
        'category', choices=CATEGORIES, help="Category of data to query"
    )
    bulk_discovery_asset.add_argument(
        'filepath', type=Path, help="Path to file containing needles"
    )
    bulk_discovery_asset.set_defaults(afunc=_bulk_discovery_asset_cmd)
    # export
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
    """Application entrypoint"""
    args = _parse_args()
    try:
        run(_main(args))
    except OnypheAPIError:
        LOGGER.critical("onyphe API error.")
    except KeyboardInterrupt:
        LOGGER.warning("user interruption.")


if __name__ == '___main__':
    app()
