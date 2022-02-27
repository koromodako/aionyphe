"""Onyphe asynchronous client
"""
from enum import Enum
from yarl import URL
from aiohttp.client import ClientSession, ClientTimeout
from .__version__ import version as VERSION


DEFAULT_VERSION = 'v2'


class OnypheCategory(Enum):
    """Onyphe data categories"""
    CTL = 'ctl'
    WHOIS = 'whois'
    GEOLOC = 'geoloc'
    INETNUM = 'inetnum'
    SNIFFER = 'sniffer'
    SYNSCAN = 'synscan'
    TOPSITE = 'topsite'
    DATASCAN = 'datascan'
    DATASHOT = 'datashot'
    PASTRIES = 'pastries'
    RESOLVER = 'resolver'
    VULNSCAN = 'vulnscan'
    ONIONSCAN = 'onionscan'
    ONIONSHOT = 'onionshot'
    THREATLIST = 'threatlist'


BEST_CATEGORIES = [
    OnypheCategory.WHOIS,
    OnypheCategory.GEOLOC,
    OnypheCategory.INETNUM,
    OnypheCategory.THREATLIST,
]


class OnypheAPIClientSession(ClientSession):
    """Asynchronous Onyphe API client"""
    # pylint: disable=R0913,R0914
    def __init__(
        self,
        host='www.onyphe.io',
        port=443,
        scheme='https',
        version='v2',
        api_key=None,
        proxy_host=None,
        proxy_port=None,
        proxy_scheme=None,
        proxy_headers=None,
        proxy_username=None,
        proxy_password=None,
        ssl=None,
        total=None,
        connect=None,
        sock_read=None,
        sock_connect=None,
    ):
        self.__timeout = ClientTimeout(
            total=total,
            connect=connect,
            sock_read=sock_read,
            sock_connect=sock_connect,
        )
        self.__base_url = URL.build(
            scheme=scheme, host=host, port=port
        ).with_path(f'api/{version}')
        self.__request_kwargs = {}
        if ssl:
            self.__request_kwargs['ssl'] = ssl
        proxy = URL.build(
            scheme=proxy_scheme,
            host=proxy_host,
            port=proxy_port,
            user=proxy_username,
            password=proxy_password,
        )
        if proxy:
            self.__request_kwargs['proxy'] = proxy
            self.__request_kwargs['proxy_headers'] = proxy_headers
        self.__headers = {
            'User-Agent': f'aionyphe/{VERSION}',
            'Content-Type': 'application/json',
        }
        if api_key:
            self.__headers['Authorization'] = f'apikey {api_key}'
        super().__init__(
            base_url=str(self.__base_url),
            headers=self.__headers,
            timeout=self.__timeout,
            raise_for_status=True,
            skip_auto_headers=True,
        )
    # pylint: enable=R0913,R0914

    async def __get(self, url):
        async with self.get(url, **self.__request_kwargs) as resp:
            data = await resp.json()
            for result in data['results']:
                yield result

    async def __post(self, url):
        async with self.post(url, **self.__request_kwargs) as resp:
            data = await resp.json()
            for result in data['results']:
                yield result

    async def user(self):
        async for result in self.__get('/user'):
            yield result

    async def summary_ip(self, ipaddr):
        async for result in self.__get(f'/summary/ip/{ipaddr}'):
            yield result

    async def summary_domain(self, domain):
        async for result in self.__get(f'/summary/domain/{domain}'):
            yield result

    async def summary_hostname(self, hostname):
        async for result in self.__get(f'/summary/hostname/{hostname}'):
            yield result

    async def simple(self, category, needle):
        async for result in self.__get(f'/simple/{category.value}/{needle}'):
            yield result

    async def simple_datascan_datamd5(self, md5):
        async for result in self.__get(f'/simple/datascan/datamd5/{md5}'):
            yield result

    async def simple_resolver_forward(self, ipaddr):
        async for result in self.__get(f'/simple/resolver/forward/{ipaddr}'):
            yield result

    async def simple_resolver_reverse(self, ipaddr):
        async for result in self.__get(f'/simple/resolver/reverse/{ipaddr}'):
            yield result

    async def simple_best(self, category, ipaddr):
        if category not in BEST_CATEGORIES:
            raise ValueError
        async for result in self.__get(f'/simple/{category.value}/best/{ipaddr}'):
            yield result

    async def search(self, oql):
        async for result in self.__get(f'/search/{oql}'):
            yield result

    async def alert_list(self):
        async for result in self.__get('/alert/list'):
            yield result

    async def alert_add(self):
        async for result in self.__post('/alert/add'):
            yield result

    async def alert_del(self, identifier):
        async for result in self.__post(f'/alert/del/{identifier}'):
            yield result

    async def bulk_summary_ip(self):
        async for result in self.__post('/bulk/summary/ip'):
            yield result

    async def bulk_summary_domain(self):
        async for result in self.__post('/bulk/summary/domain'):
            yield result

    async def bulk_summary_hostname(self):
        async for result in self.__post('/bulk/summary/hostname'):
            yield result

    async def bulk_simple_ip(self, category):
        async for result in self.__post(f'/bulk/simple/{category.value}/ip'):
            yield result

    async def bulk_simple_best_ip(self, category):
        if category not in BEST_CATEGORIES:
            raise ValueError
        async for result in self.__post(f'/bulk/simple/{category.value}/best/ip'):
            yield result

    async def export(self, oql):
        """
        This method requires an API key and an Eagle View subscription.
        It allows to export all information we have using the ONYPHE Query Language (OQL).
        Multiple entries may match so we return all of them with history of changes.
        It will auto-scroll through all results.
        Results are rendered as one JSON entry per line for easier integration with external tools.
        The last 30 days of data are queried.

        Here is an example of a OQL query string:
            category:datascan product:Nginx protocol:http os:Windows tls:true.
        """
        async for result in self.__get(f'/export/{oql}'):
            yield result
