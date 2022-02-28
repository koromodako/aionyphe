"""aionyphe enumerations
"""
from enum import Enum


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
