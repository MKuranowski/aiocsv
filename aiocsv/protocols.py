# © Copyright 2020-2024 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from typing import Any, Optional, Protocol


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
