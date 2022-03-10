"""Onyphe asynchronous client
"""
import typing as t
from ssl import SSLContext
from json import loads
from pathlib import Path
from yarl import URL
from aiohttp.client import (
    ClientSession,
    ClientTimeout,
    ClientResponse,
    ClientResponseError,
    ClientProxyConnectionError,
)
from .enum import OnypheCategory, OnypheSummaryType
from .logging import get_logger
from .exception import OnypheAPIError
from .__version__ import version as VERSION


LOGGER = get_logger('client')
DEFAULT_HOST = 'www.onyphe.io'
DEFAULT_PORT = 443
DEFAULT_SCHEME = 'https'
DEFAULT_VERSION = 'v2'
BEST_CATEGORIES = [
    OnypheCategory.WHOIS,
    OnypheCategory.GEOLOC,
    OnypheCategory.INETNUM,
    OnypheCategory.THREATLIST,
]

AsyncAPIResultIterator = t.AsyncIterator[
    t.Tuple[t.Optional[t.Mapping], t.Mapping]
]


async def _parse_json_resp(response: ClientResponse) -> AsyncAPIResultIterator:
    """Parse json api response"""
    data = await response.json()
    meta = {}
    meta.update(data)
    del meta['results']
    for result in data['results']:
        yield meta, result


async def _parse_json_error(
    response: ClientResponse,
) -> AsyncAPIResultIterator:
    """Parse json api error"""
    data = await response.json()
    yield None, data


async def _parse_ndjson_resp(
    response: ClientResponse,
) -> AsyncAPIResultIterator:
    """Parse ndjson api response"""
    while True:
        line = await response.content.readline()
        if not line:
            break
        yield None, loads(line)


async def _handle_resp(
    response: ClientResponse, parse_resp: AsyncAPIResultIterator
) -> AsyncAPIResultIterator:
    """Generic response handler"""
    try:
        async with response as resp:
            async for meta, result in parse_resp(resp):
                yield meta, result
    except ClientProxyConnectionError as exc:
        LOGGER.critical("failed to connect to proxy!")
        raise OnypheAPIError from exc
    except ClientResponseError as exc:
        if exc.status == 429:
            LOGGER.critical("rate limiting triggered!")
        elif exc.status == 400:
            LOGGER.critical(
                "bad request, server cannot understand your request!"
            )
        else:
            LOGGER.exception("unexpected response from API!")
        raise OnypheAPIError from exc


class OnypheAPIClientSession(ClientSession):
    """Asynchronous Onyphe API client"""

    # pylint: disable=R0913,R0914
    def __init__(
        self,
        api_key: str,
        scheme: str = DEFAULT_SCHEME,
        version: str = DEFAULT_VERSION,
        host: str = DEFAULT_HOST,
        port: t.Optional[int] = DEFAULT_PORT,
        proxy_host: t.Optional[str] = None,
        proxy_port: t.Optional[int] = None,
        proxy_scheme: t.Optional[str] = None,
        proxy_headers: t.Optional[t.Mapping[str, str]] = None,
        proxy_username: t.Optional[str] = None,
        proxy_password: t.Optional[str] = None,
        ssl: t.Optional[SSLContext] = None,
        total: t.Optional[int] = None,
        connect: t.Optional[int] = None,
        sock_read: t.Optional[int] = None,
        sock_connect: t.Optional[int] = None,
    ):
        self.__version = version
        self.__timeout = ClientTimeout(
            total=total,
            connect=connect,
            sock_read=sock_read,
            sock_connect=sock_connect,
        )
        self.__base_url = URL.build(scheme=scheme, host=host, port=port)
        self.__request_kwargs = {}
        if ssl:
            self.__request_kwargs['ssl'] = ssl
        if proxy_scheme:
            proxy = URL.build(
                scheme=proxy_scheme,
                host=proxy_host,
                port=proxy_port,
                user=proxy_username,
                password=proxy_password,
            )
            LOGGER.info(
                "client using proxy: %s",
                URL.build(
                    scheme=proxy_scheme,
                    host=proxy_host,
                    port=proxy_port,
                ),
            )
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
        )

    # pylint: enable=R0913,R0914

    def __build_url(self, url: str) -> str:
        """Build url helper"""
        return f'/api/{self.__version}/{url}'

    async def __get(
        self,
        url: str,
        parse_resp: AsyncAPIResultIterator,
        page: t.Optional[int] = None,
    ) -> AsyncAPIResultIterator:
        """
        GET request wrapper
        """
        url = self.__build_url(url)
        params = {}
        if page:
            params['page'] = page
        response = self.get(url, params=params, **self.__request_kwargs)
        async for meta, result in _handle_resp(response, parse_resp):
            yield meta, result

    async def __post(
        self,
        url: str,
        parse_resp: AsyncAPIResultIterator,
        data: t.Optional[bytes] = None,
        json: t.Optional[dict] = None,
    ) -> AsyncAPIResultIterator:
        """
        POST request wrapper
        """
        url = self.__build_url(url)
        response = self.post(
            url, data=data, json=json, **self.__request_kwargs
        )
        async for meta, result in _handle_resp(response, parse_resp):
            yield meta, result

    async def user(self) -> AsyncAPIResultIterator:
        """
        Which API endpoints you have access to,
        the complete list of filters you are allowed to user as per your license,
        or how many credits are remaining.
        """
        async for meta, result in self.__get('user', _parse_json_resp):
            yield meta, result

    async def summary(
        self, summary_type: OnypheSummaryType, needle: str, page: int = 1
    ) -> AsyncAPIResultIterator:
        """
        Results about all categories of information we have for the given
        needle (ip, domain or hostname).
        Only the 10 latest results per category will be returned.
        Note: all fields are returned except data and content and those not
        allowed by your subscription.
        """
        async for meta, result in self.__get(
            f'summary/{summary_type.value}/{needle}',
            _parse_json_resp,
            page=page,
        ):
            yield meta, result

    async def simple(
        self, category: OnypheCategory, needle: str, page: int = 1
    ) -> AsyncAPIResultIterator:
        """
        Results about category of information we have for the given needle with
        history of changes, if any.
        """
        async for meta, result in self.__get(
            f'simple/{category.value}/{needle}',
            _parse_json_resp,
            page=page,
        ):
            yield meta, result

    async def simple_datascan_datamd5(
        self, md5: str, page: int = 1
    ) -> AsyncAPIResultIterator:
        """
        Results about datascan/datamd5 category of information we have for the
        given domain or hostname with history of changes, if any.
        """
        async for meta, result in self.__get(
            f'simple/datascan/datamd5/{md5}',
            _parse_json_resp,
            page=page,
        ):
            yield meta, result

    async def simple_resolver_forward(
        self, domain_or_hostname: str, page: int = 1
    ) -> AsyncAPIResultIterator:
        """
        Results about resolver category of information we have for the given
        domain or hostname with history of changes, if any.
        """
        async for meta, result in self.__get(
            f'simple/resolver/forward/{domain_or_hostname}',
            _parse_json_resp,
            page=page,
        ):
            yield meta, result

    async def simple_resolver_reverse(
        self, ipaddr: str, page: int = 1
    ) -> AsyncAPIResultIterator:
        """
        Results about resolver category of information we have for the given
        ip address with history of changes, if any.
        """
        async for meta, result in self.__get(
            f'simple/resolver/reverse/{ipaddr}',
            _parse_json_resp,
            page=page,
        ):
            yield meta, result

    async def simple_best(
        self, category: OnypheCategory, ipaddr: str, page: int = 1
    ) -> AsyncAPIResultIterator:
        """
        Return one result about category of information we have for the given
        ip address.
        There will be no history of changes, the goal of this API is to return
        the best matching subnet regarding the given ip address.
        Best matching subnet means the one with the smallest CIDR mask.
        """
        if category not in BEST_CATEGORIES:
            raise ValueError(f"unsupported best category: {category}")
        async for meta, result in self.__get(
            f'simple/{category.value}/best/{ipaddr}',
            _parse_json_resp,
            page=page,
        ):
            yield meta, result

    async def search(self, oql: str, page: int = 1) -> AsyncAPIResultIterator:
        """
        Search all information we have using the ONYPHE Query Language (OQL).
        Multiple entries may match so we return all of them with history of
        changes.
        Each page of results displays 10 entries. By default, the last 30 days
        of data are queried.
        Entreprise functions allows to query older data or even shorter
        timeranges like just the previous day, for instance.
        """
        async for meta, result in self.__get(
            f'search/{oql}',
            _parse_json_resp,
            page=page,
        ):
            yield meta, result

    async def alert_list(self, page: int = 1) -> AsyncAPIResultIterator:
        """
        List of configured alerts
        """
        async for meta, result in self.__get(
            'alert/list',
            _parse_json_resp,
            page=page,
        ):
            yield meta, result

    async def alert_add(
        self, name: str, oql: str, email: str
    ) -> AsyncAPIResultIterator:
        """
        Add an alert
        """
        async for meta, result in self.__post(
            'alert/add',
            _parse_json_error,
            json={'name': name, 'query': oql, 'email': email},
        ):
            yield meta, result

    async def alert_del(self, identifier: str) -> AsyncAPIResultIterator:
        """
        Delete an alert
        """
        async for meta, result in self.__post(
            f'alert/del/{identifier}',
            _parse_json_error,
        ):
            yield meta, result

    async def bulk_summary(
        self, summary_type: OnypheSummaryType, filepath: Path
    ) -> AsyncAPIResultIterator:
        """
        Results about all categories of information we have for the given
        IPv{4,6} address.
        Only the 10 latest results per category will be returned.
        Results are rendered as one JSON entry per line for easier integration
        with external tools.
        """
        async for meta, result in self.__post(
            f'bulk/summary/{summary_type.value}',
            _parse_ndjson_resp,
            data=filepath.read_bytes(),
        ):
            yield meta, result

    async def bulk_simple_ip(
        self,
        category: OnypheCategory,
        filepath: Path,
    ) -> AsyncAPIResultIterator:
        """
        Results about category of information we have for the given IPv{4,6}
        address.
        Only the 10 latest results for the queried category will be returned.
        Results are rendered as one JSON entry per line for easier integration
        with external tools.
        """
        async for meta, result in self.__post(
            f'bulk/simple/{category.value}/ip',
            _parse_ndjson_resp,
            data=filepath.read_bytes(),
        ):
            yield meta, result

    async def bulk_simple_best_ip(
        self,
        category: OnypheCategory,
        filepath: Path,
    ) -> AsyncAPIResultIterator:
        """
        Result about geoloc category of information we have for the given
        IPv{4,6} address.
        There will be no history of changes, the goal of this API is to return
        the best matching subnet regarding each given addresses.
        Best matching subnet means the one with the smallest CIDR mask.
        Results are rendered as one JSON entry per line for easier integration
        with external tools.
        """
        if category not in BEST_CATEGORIES:
            raise ValueError
        async for meta, result in self.__post(
            f'bulk/simple/{category.value}/best/ip',
            _parse_ndjson_resp,
            data=filepath.read_bytes(),
        ):
            yield meta, result

    async def export(self, oql: str) -> AsyncAPIResultIterator:
        """
        This method requires an API key and an Eagle View subscription.
        It allows to export all information we have using the ONYPHE Query
        Language (OQL). Multiple entries may match so we return all of them
        with history of changes. It will auto-scroll through all results.
        Results are rendered as one JSON entry per line for easier integration
        with external tools. The last 30 days of data are queried.

        Here is an example of a OQL query string:
            category:datascan product:Nginx protocol:http os:Windows tls:true.
        """
        async for meta, result in self.__get(
            f'export/{oql}', _parse_ndjson_resp
        ):
            yield meta, result
