# © Copyright 2020-2026 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from collections.abc import AsyncIterator, Awaitable
from typing import Self

from .protocols import DialectLike, WithAsyncRead

class Parser:
    """Return type of the "Parser" function, not accessible from Python."""

    def __new__(cls, reader: WithAsyncRead, dialect: DialectLike) -> Self: ...
    def __aiter__(self) -> AsyncIterator[list[str]]: ...
    def __anext__(self) -> Awaitable[list[str]]: ...
    @property
    def line_num(self) -> int: ...
