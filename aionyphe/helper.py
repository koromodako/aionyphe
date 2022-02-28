"""aionyphe helper
"""
import typing as t
from .client import AsyncAPIResultIterator
from .logging import get_logger


LOGGER = get_logger('helper')


async def iter_pages(
    afunc: AsyncAPIResultIterator,
    args: t.List[t.Any],
    first: int = 1,
    last: t.Optional[int] = None,
) -> AsyncAPIResultIterator:
    """Iterate through pages"""
    current = first
    while True:
        async for meta, result in afunc(*args, page=current):
            # ensure last page is consistent
            if last:
                last = min(last, meta.get('max_page', 1))
            else:
                last = meta.get('max_page', 1)
            # yield result
            yield meta, result
        # last page reached ?
        LOGGER.info("fetched page %d of %d", current, last)
        if current >= last:
            break
        # goto next page
        current += 1
