"""Onyphe asynchronous client
"""

from asyncio import Semaphore
from collections.abc import AsyncIterator
from copy import deepcopy
from dataclasses import dataclass, field
from json import JSONDecodeError, loads
from pathlib import Path
from ssl import SSLContext
from urllib.parse import quote
from warnings import warn

from aiohttp.client import (
    ClientProxyConnectionError,
    ClientResponse,
    ClientResponseError,
    ClientSession,
    ClientTimeout,
    ContentTypeError,
)
from yarl import URL

from .__version__ import version as VERSION
from .enum import OnypheCategory, OnypheFeature, OnypheSummaryType
from .exception import OnypheAPIError
from .logging import get_logger

LOGGER = get_logger('client')
DEFAULT_HOST = 'www.onyphe.io'
DEFAULT_PORT = 443
DEFAULT_SCHEME = 'https'
DEFAULT_VERSION = 'v2'
BEST_CATEGORIES = {
    OnypheCategory.WHOIS,
    OnypheCategory.GEOLOC,
    OnypheCategory.INETNUM,
    OnypheCategory.THREATLIST,
}
DEFAULT_RATE_LIMITS = {
    OnypheFeature.USER: None,
    OnypheFeature.SUMMARY: None,
    OnypheFeature.SIMPLE: None,
    OnypheFeature.DATAMD5: None,
    OnypheFeature.RESOLVER_FWD: None,
    OnypheFeature.RESOLVER_REV: None,
    OnypheFeature.SIMPLE_BEST: None,
    OnypheFeature.SEARCH: None,
    OnypheFeature.ALERT_LIST: None,
    OnypheFeature.ALERT_ADD: None,
    OnypheFeature.ALERT_DEL: None,
    OnypheFeature.BULK_SUMMARY: None,
    OnypheFeature.BULK_SIMPLE_IP: None,
    OnypheFeature.BULK_SIMPLE_BEST_IP: None,
    OnypheFeature.BULK_DISCOVERY_ASSET: None,
    OnypheFeature.EXPORT: 1,
}

AsyncAPIResultIterator = AsyncIterator[tuple[dict | None, dict]]


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
    """Parse newline delimited json api response"""
    while True:
        line = await response.content.readline()
        if not line:
            break
        yield None, loads(line)


def _api_error(message: str, *args, **kwargs):
    LOGGER.critical(message, *args, **kwargs)
    raise OnypheAPIError(message)


def _deprecated(method: str):
    warn(
        f"OnypheAPIClient.{method} is deprecated and will be removed soon",
        FutureWarning,
    )


async def _get_error_text(resp: ClientResponse) -> tuple[str, int]:
    try:
        body = await resp.json()
        return body['text'], body['error']
    except (ClientResponseError, ContentTypeError, JSONDecodeError, KeyError):
        return "error text is missing", -1


async def _handle_resp(
    response: ClientResponse, parse_resp: AsyncAPIResultIterator
) -> AsyncAPIResultIterator:
    """Generic response handler"""
    try:
        async with response as resp:
            if resp.status == 429:
                _api_error("rate limiting triggered!")
            if resp.status == 400:
                error_text, error_code = await _get_error_text(resp)
                _api_error(
                    "server refused to process your request: %s (err=%d)",
                    error_text,
                    error_code,
                )
            if resp.status >= 300:
                _api_error(
                    "unexpected response from onyphe api (resp.status=%d)",
                    resp.status,
                )
            async for meta, result in parse_resp(resp):
                yield meta, result
    except ClientProxyConnectionError as exc:
        LOGGER.critical("proxy connection failed!")
        raise OnypheAPIError from exc


def _select_data(filepath: Path | None, data: bytes | None):
    if data:
        return data
    if filepath:
        if filepath.is_file():
            return filepath.read_bytes()
        raise ValueError(f"file not found or not a regular file: {filepath}")
    raise ValueError("one of {filepath,data} argument shall be set")


def client_session(
    api_key: str,
    scheme: str = DEFAULT_SCHEME,
    host: str = DEFAULT_HOST,
    port: int | None = DEFAULT_PORT,
    total: int | None = None,
    connect: int | None = None,
    sock_read: int | None = None,
    sock_connect: int | None = None,
):
    """Create Onyphe API client underlying HTTP client session"""
    base_url = URL.build(scheme=scheme, host=host, port=port)
    LOGGER.info("aionyphe api client using base url: %s", base_url)
    return ClientSession(
        base_url=base_url,
        headers={
            'User-Agent': f'aionyphe/{VERSION}',
            'Content-Type': 'application/json',
            'Authorization': f'apikey {api_key}',
        },
        timeout=ClientTimeout(
            total=total,
            connect=connect,
            sock_read=sock_read,
            sock_connect=sock_connect,
        ),
    )


@dataclass
class OnypheAPIClientProxy:
    """Onyphe API client HTTP proxy information"""

    scheme: str | None = None
    host: str | None = None
    port: int | None = None
    headers: dict[str, str] | None = None
    username: str | None = None
    password: str | None = None

    def __str__(self):
        return str(
            URL.build(scheme=self.scheme, host=self.host, port=self.port)
        )

    @property
    def is_valid(self):
        """Determine if proxy is valid or not"""
        return self.scheme and self.host

    @property
    def url(self):
        """Proxy url with credentials"""
        return URL.build(
            scheme=self.scheme,
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
        )


class _SemaphoreStub:
    """asyncio.Semaphore partial stub"""

    def __init__(self, value: int = 0):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args, **kwargs):
        pass


@dataclass
class OnypheAPIClientRateLimiting:
    """Onyphe API client"""

    enabled: bool = True
    rate_limits: dict[OnypheFeature, int] | None = None

    @property
    def semaphores(self):
        """Lazy getter for semaphores matching rate limiting specs"""
        if not hasattr(self, '__semaphores'):
            rate_limits = deepcopy(DEFAULT_RATE_LIMITS)
            rate_limits.update(self.rate_limits or {})
            semaphores = {}
            for feature in OnypheFeature:
                if not self.enabled:
                    semaphores[feature] = _SemaphoreStub()
                    continue
                concurrency_limit = rate_limits.get(feature)
                semaphore_cls = (
                    _SemaphoreStub if concurrency_limit is None else Semaphore
                )
                semaphores[feature] = semaphore_cls(concurrency_limit)
            setattr(self, '__semaphores', semaphores)
        return getattr(self, '__semaphores')


@dataclass
class OnypheAPIClient:
    """Asynchronous Onyphe API client"""

    client: ClientSession
    version: str = DEFAULT_VERSION
    ssl: SSLContext | None = None
    proxy: OnypheAPIClientProxy = field(default_factory=OnypheAPIClientProxy)
    rate_limiting: OnypheAPIClientRateLimiting = field(
        default_factory=OnypheAPIClientRateLimiting
    )

    @property
    def request_kwargs(self):
        """Lazy getter for request kwargs"""
        if not hasattr(self, '__request_kwargs'):
            request_kwargs = {}
            if self.ssl:
                LOGGER.info("aionyphe api client using custom ssl context")
                request_kwargs['ssl'] = self.ssl
            if self.proxy.is_valid:
                LOGGER.info("aionyphe api client using proxy: %s", self.proxy)
                request_kwargs['proxy'] = str(self.proxy.url)
                request_kwargs['proxy_headers'] = self.proxy.headers
            setattr(self, '__request_kwargs', request_kwargs)
        return getattr(self, '__request_kwargs')

    def __build_url(self, url: str) -> str:
        """
        Build API URL helper
        """
        return f'/api/{self.version}/{url}'

    def __semaphore(
        self, feature: OnypheFeature
    ) -> Semaphore | _SemaphoreStub:
        """
        Get semaphore for given feature
        """
        return self.rate_limiting.semaphores[feature]

    async def __get(
        self,
        url: str,
        parse_resp: AsyncAPIResultIterator,
        page: int | None = None,
    ) -> AsyncAPIResultIterator:
        """
        GET request wrapper
        """
        url = self.__build_url(url)
        params = {}
        if page:
            params['page'] = page
        response = self.client.get(url, params=params, **self.request_kwargs)
        LOGGER.debug("GET %s %s", url, params)
        async for meta, result in _handle_resp(response, parse_resp):
            yield meta, result

    async def __post(
        self,
        url: str,
        parse_resp: AsyncAPIResultIterator,
        data: bytes | None = None,
        json: dict | None = None,
    ) -> AsyncAPIResultIterator:
        """
        POST request wrapper
        """
        url = self.__build_url(url)
        response = self.client.post(
            url, data=data, json=json, **self.request_kwargs
        )
        LOGGER.debug("POST %s (%s)", url, 'data' if json is None else 'json')
        async for meta, result in _handle_resp(response, parse_resp):
            yield meta, result

    async def user(self) -> AsyncAPIResultIterator:
        """
        Which API endpoints you have access to,
        the complete list of filters you are allowed to user as per your license,
        or how many credits are remaining.
        """
        async with self.__semaphore(OnypheFeature.USER):
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
        async with self.__semaphore(OnypheFeature.SUMMARY):
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
        _deprecated('simple')
        async with self.__semaphore(OnypheFeature.SIMPLE):
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
        _deprecated('simple_datascan_datamd5')
        async with self.__semaphore(OnypheFeature.DATAMD5):
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
        _deprecated('simple_resolver_forward')
        async with self.__semaphore(OnypheFeature.RESOLVER_FWD):
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
        _deprecated('simple_resolver_reverse')
        async with self.__semaphore(OnypheFeature.RESOLVER_REV):
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
        async with self.__semaphore(OnypheFeature.SIMPLE_BEST):
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
        async with self.__semaphore(OnypheFeature.SEARCH):
            async for meta, result in self.__get(
                f'search/{quote(oql)}',
                _parse_json_resp,
                page=page,
            ):
                yield meta, result

    async def alert_list(self, page: int = 1) -> AsyncAPIResultIterator:
        """
        List of configured alerts
        """
        async with self.__semaphore(OnypheFeature.ALERT_LIST):
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
        async with self.__semaphore(OnypheFeature.ALERT_ADD):
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
        async with self.__semaphore(OnypheFeature.ALERT_DEL):
            async for meta, result in self.__post(
                f'alert/del/{identifier}',
                _parse_json_error,
            ):
                yield meta, result

    async def bulk_summary(
        self,
        summary_type: OnypheSummaryType,
        filepath: Path | None = None,
        data: bytes | None = None,
    ) -> AsyncAPIResultIterator:
        """
        Results about all categories of information we have for the given
        IPv{4,6} address.
        Only the 10 latest results per category will be returned.
        Results are rendered as one JSON entry per line for easier integration
        with external tools.
        """
        data = _select_data(filepath, data)
        async with self.__semaphore(OnypheFeature.BULK_SUMMARY):
            async for meta, result in self.__post(
                f'bulk/summary/{summary_type.value}',
                _parse_ndjson_resp,
                data=data,
            ):
                yield meta, result

    async def bulk_simple_ip(
        self,
        category: OnypheCategory,
        filepath: Path | None = None,
        data: bytes | None = None,
    ) -> AsyncAPIResultIterator:
        """
        Results about category of information we have for the given IPv{4,6}
        address.
        Only the 10 latest results for the queried category will be returned.
        Results are rendered as one JSON entry per line for easier integration
        with external tools.
        """
        _deprecated('bulk_simple_ip')
        data = _select_data(filepath, data)
        async with self.__semaphore(OnypheFeature.BULK_SIMPLE_IP):
            async for meta, result in self.__post(
                f'bulk/simple/{category.value}/ip',
                _parse_ndjson_resp,
                data=data,
            ):
                yield meta, result

    async def bulk_simple_best_ip(
        self,
        category: OnypheCategory,
        filepath: Path | None = None,
        data: bytes | None = None,
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
            raise ValueError(f"unsupported best category: {category}")
        data = _select_data(filepath, data)
        async with self.__semaphore(OnypheFeature.BULK_SIMPLE_BEST_IP):
            async for meta, result in self.__post(
                f'bulk/simple/{category.value}/best/ip',
                _parse_ndjson_resp,
                data=data,
            ):
                yield meta, result

    async def bulk_discovery_asset(
        self,
        category: OnypheCategory,
        filepath: Path | None = None,
        data: bytes | None = None,
    ) -> AsyncAPIResultIterator:
        """
        It allows to execute bulk searches by leveraging the best from ONYPHE
        Query Language (OQL). Multiple entries may match so we return all of
        them with history of changes. It will auto-scroll through all results.
        Results are rendered as one JSON entry per line for easier integration
        with external tools. The last 30 days of data are queried by default,
        but you can use the -since function to fetch more.
        """
        data = _select_data(filepath, data)
        async with self.__semaphore(OnypheFeature.BULK_DISCOVERY_ASSET):
            async for meta, result in self.__post(
                f'bulk/discovery/{category.value}/asset',
                _parse_ndjson_resp,
                data=data,
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

        WARNING: export feature is limited and does not support concurrency,
                 this limitation also implemented on both server and client sides.
                 On client side, this limitation is implemented using
                 asyncio.Semaphore instances but can be disabled adding
                 disable_semaphores=True when creating OnypheAPIClientSession
        """
        async with self.__semaphore(OnypheFeature.EXPORT):
            async for meta, result in self.__get(
                f'export/{oql}', _parse_ndjson_resp
            ):
                yield meta, result
