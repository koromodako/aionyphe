"""aionyphe enumerations
"""

from enum import Enum


class OnypheFeature(Enum):
    """Onyphe features"""

    USER = 'user'
    SUMMARY = 'summary'
    SIMPLE = 'simple'  # deprecated in Onyphe API v3
    DATAMD5 = 'datamd5'  # deprecated in Onyphe API v3
    RESOLVER_FWD = 'resolver_fwd'  # deprecated in Onyphe API v3
    RESOLVER_REV = 'resolver_rev'  # deprecated in Onyphe API v3
    SIMPLE_BEST = 'simple_best'
    SEARCH = 'search'
    ALERT_LIST = 'alert_list'
    ALERT_ADD = 'alert_add'
    ALERT_DEL = 'alert_del'
    BULK_SUMMARY = 'bulk_summary'
    BULK_SIMPLE_IP = 'bulk_simple_ip'  # deprecated in Onyphe API v3
    BULK_SIMPLE_BEST_IP = 'bulk_simple_best_ip'
    BULK_DISCOVERY_ASSET = 'bulk_discovery_asset'
    EXPORT = 'export'


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


class OnypheSummaryType(Enum):
    """Onyphe summary types"""

    IP = 'ip'
    DOMAIN = 'domain'
    HOSTNAME = 'hostname'
