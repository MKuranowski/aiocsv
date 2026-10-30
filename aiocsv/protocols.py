# © Copyright 2020-2026 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

import sys
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Protocol, TypedDict, Union

if TYPE_CHECKING:
    import csv

if sys.version_info < (3, 12):
    _QuotingType = Literal[0, 1, 2, 3]
else:
    _QuotingType = Literal[0, 1, 2, 3, 4, 5]


class WithAsyncWrite(Protocol):
    async def write(self, b: str, /) -> Any: ...


class WithAsyncRead(Protocol):
    async def read(self, size: int, /) -> str: ...


class DialectLike(Protocol):
    delimiter: str
    quotechar: str | None
    escapechar: str | None
    doublequote: bool
    skipinitialspace: bool
    quoting: _QuotingType
    strict: bool


CsvDialectArg = Union[str, "csv.Dialect", type["csv.Dialect"]]


class CsvDialectKwargs(TypedDict):
    delimiter: NotRequired[str]
    quotechar: NotRequired[str | None]
    escapechar: NotRequired[str | None]
    doublequote: NotRequired[bool]
    skipinitialspace: NotRequired[bool]
    lineterminator: NotRequired[str]
    quoting: NotRequired[_QuotingType]
    strict: NotRequired[bool]
