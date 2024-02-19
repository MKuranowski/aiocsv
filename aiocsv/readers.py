import csv
from warnings import warn
from typing import Dict, List, Optional, Sequence
from .protocols import WithAsyncRead

try:
    from ._parser import Parser
except ImportError:
    warn("using slow, pure-Python parser")
    from .parser import Parser


class AsyncReader:
    """An object that iterates over lines in given asynchronous file.
    Additional keyword arguments are passed to the underlying csv.reader instance.
    Iterating over this object returns parsed CSV rows (List[str]).
    """
    def __init__(self, asyncfile: WithAsyncRead, **csvreaderparams) -> None:
        self._file = asyncfile

        # csv.Dialect isn't a class, instead it's a weird proxy
        # (at least in CPython) to _csv.Dialect. Instead of figuring how
        # this shit works, just let `csv` figure the dialects out.
        self.dialect = csv.reader("", **csvreaderparams).dialect

        self._parser = Parser(self._file, self.dialect)

    @property
    def line_num(self) -> int:
        warn("aiocsv doesn't support the line_num attribute on readers")
        return -1

    def __aiter__(self):
        return self

    async def __anext__(self) -> List[str]:
        return await self._parser.__anext__()


class AsyncDictReader:
    """An object that iterates over lines in given asynchronous file.
    Additional keyword arguments are passed to the underlying csv.DictReader instance.
    If given csv file has no header, provide a 'fieldnames' keyword argument,
    like you would to csv.DictReader.
    Iterating over this object returns parsed CSV rows (Dict[str, str]).
    """
    def __init__(self, asyncfile: WithAsyncRead, fieldnames: Optional[Sequence[str]] = None,
                 restkey: Optional[str] = None, restval: Optional[str] = None,
                 **csvreaderparams) -> None:

        self.fieldnames: Optional[List[str]] = list(fieldnames) if fieldnames else None
        self.restkey: Optional[str] = restkey
        self.restval: Optional[str] = restval
        self.reader = AsyncReader(asyncfile, **csvreaderparams)

    @property
    def dialect(self) -> csv.Dialect:
        return self.reader.dialect

    @property
    def line_num(self) -> int:
        return self.reader.line_num

    def __aiter__(self):
        return self

    async def __anext__(self) -> Dict[str, str]:
        # check if header needs to be parsed
        if self.fieldnames is None:
            self.fieldnames = await self.reader.__anext__()

        # skip empty rows
        cells = await self.reader.__anext__()
        while not cells:
            cells = await self.reader.__anext__()

        # join the header with the row
        row = dict(zip(self.fieldnames, cells))

        len_header = len(self.fieldnames)
        len_cells = len(cells)

        if len_cells > len_header:
            row[self.restkey] = cells[len_header:]  # type: ignore

        elif len_cells < len_header:
            for k in self.fieldnames[len_cells:]:
                row[k] = self.restval  # type: ignore

        return row
