from typing import AsyncIterator, List

from .protocols import WithAsyncRead, DialectLike


class Parser(AsyncIterator[List[str]]):
    line_num: int

    def __init__(self, __reader: WithAsyncRead, __dialect: DialectLike) -> None: ...
