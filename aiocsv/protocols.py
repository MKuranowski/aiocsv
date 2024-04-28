# © Copyright 2020-2024 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING, Any, Optional, Protocol, Type, TypedDict, Union

from typing_extensions import NotRequired

if TYPE_CHECKING:
    import csv


class WithAsyncWrite(Protocol):
    async def write(self, __b: str) -> Any: ...


class WithAsyncRead(Protocol):
    async def read(self, __size: int) -> str: ...


class DialectLike(Protocol):
    delimiter: str
    quotechar: Optional[str]
    escapechar: Optional[str]
    doublequote: bool
    skipinitialspace: bool
    quoting: int
    strict: bool


CsvDialectArg = Union[str, "csv.Dialect", Type["csv.Dialect"]]


class CsvDialectKwargs(TypedDict):
    delimiter: NotRequired[str]
    quotechar: NotRequired[Optional[str]]
    escapechar: NotRequired[Optional[str]]
    doublequote: NotRequired[bool]
    skipinitialspace: NotRequired[bool]
    lineterminator: NotRequired[str]
    quoting: NotRequired[int]
    strict: NotRequired[bool]
