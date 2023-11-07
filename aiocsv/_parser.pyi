from typing import AsyncIterator, List

from .protocols import WithAsyncRead, DialectLike


class parser(AsyncIterator[List[str]]):
    line_number: int

    def __init__(self, __reader: WithAsyncRead, __dialect: DialectLike) -> None: ...
