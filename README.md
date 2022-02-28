# aionyphe

Asynchronous API SDK and command line interface written in Python
for [Onyphe](https://www.onyphe.io). This software is cross-platform and works
on Linux, Mac and Windows.

Using asyncio enables the user to perform concurrent requests without the need
of threading or subprocessing. Be careful not to trigger the rate limiting
protection though.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install git+https://github.com/koromodako/aionyphe
```

## Testing

There is no automated testing for now. Manual testing was performed using
Python 3.9.7 on Ubuntu 21.10. Assume all Python versions above 3.9 are supported.

## Documentation

There is no documentation for now but most of the code is documented.

## Coding rules

Code is formatted using [black](https://github.com/psf/black) and
[Pylint](https://pylint.org) is used to ensure most of the code is
[PEP8](https://www.python.org/dev/peps/pep-0008) compliant and error free.

## API Usage

### Direct connection

```python
from asyncio import run
from getpass import getpass
from orjson import dumps
from aionyphe import OnypheAPIClientSession

async def main():
    oql = 'category:synscan ip:8.8.8.8'
    api_key = getpass("Enter Onyphe API key: ")
    kwargs = dict(api_key=api_key)
    async with OnypheAPIClientSession(**kwargs) as client:
        async for _, result in client.export(oql):
            print(dumps(result).decode())

if __name__ == '__main__':
    run(main())
```

### Proxy connection

```python
from asyncio import run
from getpass import getpass
from orjson import dumps
from aionyphe import OnypheAPIClientSession

async def main():
    oql = 'category:synscan ip:8.8.8.8'
    api_key = getpass("Enter Onyphe API key: ")
    kwargs = dict(
        api_key=api_key,
        proxy_scheme='http',
        proxy_host='squid.domain.tld',
        proxy_port=3128,
    )
    async with OnypheAPIClientSession(**kwargs) as client:
        async for _, result in client.export(oql):
            print(dumps(result).decode())

if __name__ == '__main__':
    run(main())
```

### Get a specific result page

```python
from asyncio import run
from getpass import getpass
from orjson import dumps
from aionyphe import OnypheAPIClientSession

async def main():
    oql = 'category:datascan domain:google.com'
    api_key = getpass("Enter Onyphe API key: ")
    kwargs = dict(api_key=api_key)
    async with OnypheAPIClientSession(**kwargs) as client:
        async for _, result in client.search(oql, page=2):
            print(dumps(result).decode())

if __name__ == '__main__':
    run(main())
```

### A helper to iterate over pages

```python
from asyncio import run
from getpass import getpass
from orjson import dumps
from aionyphe import OnypheAPIClientSession, iter_pages

async def main():
    oql = 'category:datascan domain:google.com'
    api_key = getpass("Enter Onyphe API key: ")
    kwargs = dict(api_key=api_key)
    async with OnypheAPIClientSession(**kwargs) as client:
        async for _, result in iter_pages(client.search, [oql], 2, 4):
            print(dumps(result).decode())

if __name__ == '__main__':
    run(main())
```

## Command Line Interface Usage

This client does not support as much features as the original Onyphe
[client](https://github.com/onyphe/client) written in Perl but it does allow
the user to pipe the output to another tool keeping the JSON-based pipe interface.

```bash
# get usage information
aionyphe -h
# get 'export' command usage
aionyphe export -h
# export data for given oql query
aionyphe export 'category:synscan ip:8.8.8.8'
# get your public ip address
aionyphe myip
# get information about your user account
aionyphe user | jq
# show pages 2 to 4 for search query
aionyphe search --first 2 --last 4 'category:datascan domain:google.com'
```
