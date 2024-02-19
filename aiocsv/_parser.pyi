from typing import AsyncIterator, List

from .protocols import WithAsyncRead, DialectLike

class _Parser:
    """Return type of the "Parser" function, not accessible from Python."""

    def __aiter__(self) -> AsyncIterator[List[str]]: ...
    @property
    def line_num(self) -> int: ...

def Parser(reader: WithAsyncRead, dialect: DialectLike) -> _Parser: ...
