import csv
from typing import AsyncIterator, List

from .protocols import WithAsyncRead


def parser(__reader: WithAsyncRead, __pydialect: csv.Dialect) -> AsyncIterator[List[str]]: ...
