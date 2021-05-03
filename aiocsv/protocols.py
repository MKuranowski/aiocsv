from typing import Any, Union
import sys

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol


class WithAsyncWrite(Protocol):
    async def write(self, __b: str) -> Any: ...


class WithAsyncRead(Protocol):
    async def read(self, __size: int) -> Union[str, bytes]: ...
