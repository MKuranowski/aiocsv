# © Copyright 2020-2024 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from typing import AsyncIterator, Awaitable, List

from .protocols import DialectLike, WithAsyncRead

class _Parser:
    """Return type of the "Parser" function, not accessible from Python."""

    def __aiter__(self) -> AsyncIterator[List[str]]: ...
    def __anext__(self) -> Awaitable[List[str]]: ...
    @property
    def line_num(self) -> int: ...

def Parser(reader: WithAsyncRead, dialect: DialectLike) -> _Parser: ...
