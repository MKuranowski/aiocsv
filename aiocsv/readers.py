import csv
from warnings import warn
from typing import Dict, List, Optional, Sequence, Callable
from .protocols import WithAsyncRead

try:
    from ._parser import parser
except ImportError:
    warn("Using a slow, pure-python CSV parser")
    from .parser import parser


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

        self._parser = parser(self._file, self.dialect)

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
                 colfilters: Optional[List[Callable]] = None,
                 rowfilters: Optional[List[Callable]] = None,
                 **csvreaderparams) -> None:
        """Initialize AsyncDictReader instance.
        Args:
            asyncfile (WithAsyncRead): asynchronous file object.
            fieldnames (Optional[Sequence[str]]): field names to be used if given
                csv file has no header (used like in csv.DictReader).
            restkey (Optional[str]): passed to csv.DictReader.
            restval (Optional[str]): passed to csv.DictReader.
            colfilters (Optional[List[Callable]]): list of functions that filter
                columns. Multiple functions will be treated as OR.
            colvalues (Optional[List[Callable]]): list of functions that filter
                rows. Multiple functions will be treated as OR.
            **csvreaderparams: additional keyword arguments passed to the underlying
                csv.DictReader instance.
        """
        self.fieldnames: Optional[List[str]] = fieldnames if fieldnames else None
        self.restkey: Optional[str] = restkey
        self.restval: Optional[str] = restval
        self.reader = AsyncReader(asyncfile, **csvreaderparams)
        self.colfilters: Optional[List[Callable]] = colfilters
        self.rowfilters: Optional[List[Callable]] = rowfilters

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

        if self.rowfilters:
            while True:
                if not cells:
                    cells = await self.reader.__anext__()
                    continue
                row = self._join_header(cells)
                if any(rowfilter(row) for rowfilter in self.rowfilters):
                    break
                cells = await self.reader.__anext__()

        else:
            while not cells:
                cells = await self.reader.__anext__()
            row = self._join_header(cells)

        len_header = len(self.fieldnames)
        len_cells = len(cells)

        if len_cells > len_header:
            row[self.restkey] = cells[len_header:]  # type: ignore

        elif len_cells < len_header:
            for k in self.fieldnames[len_cells:]:
                row[k] = self.restval  # type: ignore

        if self.colfilters:
            # only include columns that pass the filter
            include_fieldnames = {
                fieldname for fieldname in self.fieldnames
                if any(colfilter(fieldname) for colfilter in self.colfilters)
                }
            row = {k: v for k, v in row.items() if k in include_fieldnames}

        return row

    def _join_header(self, cells: List[str]) -> Dict[str, str]:
        """Joins the header with the row."""
        row = dict(zip(self.fieldnames, cells))
        return row
