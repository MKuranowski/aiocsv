from aiofile import AIOFile, LineReader, Writer
from typing import Sequence, List, Dict, Iterable, Mapping, Any
import asyncio
import csv
import io

__title__ = "aiocsv"
__description__ = "Asynchronous CSV reading/writing"
__version__ = "1.0.0"

__url__ = "https://github.com/MKuranowski/aiocsv"
__author__ = "Mikołaj Kuranowski"
__email__ = "".join(chr(i) for i in [109, 107, 117, 114, 97, 110, 111, 119, 115, 107, 105,
                                     64, 103, 109, 97, 105, 108, 46, 99, 111, 109])

__copyright__ = "© Copyright 2020 Mikołaj Kuranowski"
__license__ = "MIT"


class AsyncReader:
    """An object that iterates over lines in given aiofile.
    Additional keyword arguments are passed to the underlying csv.reader instance.

    Iterating over this object returns parsed rows (List[str]).
    """
    def __init__(self, aiofile: AIOFile, **csvreaderparams) -> None:
        if aiofile.mode.binary:
            raise ValueError("csv file should be opened in text mode")

        self._buffer = io.StringIO(newline="")
        self._csv_reader = csv.reader(self._buffer, **csvreaderparams)

        # Guess the line terminator
        line_sep = self._csv_reader.dialect.lineterminator or "\r\n"
        self._line_reader = LineReader(aiofile, line_sep=line_sep)

    @property
    def dialect(self) -> csv.Dialect:
        return self._csv_reader.dialect

    @property
    def line_num(self) -> int:
        return self._csv_reader.line_num

    def __aiter__(self):
        return self

    async def __anext__(self) -> List[str]:
        # __init__ checked if provided file is opened in text mode
        line: str = await self._line_reader.readline()  # type: ignore

        if not line:
            raise StopAsyncIteration

        # Try to parse line
        self._buffer.write(line)
        self._buffer.seek(0)

        # Get parsed line from the underlying csv.reader instance
        try:
            result = next(self._csv_reader)
        except StopIteration as e:
            raise StopAsyncIteration from e

        # Clear the buffer
        self._buffer.seek(0)
        self._buffer.truncate(0)

        # Return parsed row
        return result


class AsyncDictReader:
    """An object that iterates over lines in given aiofile.
    Additional keyword arguments are passed to the underlying csv.DictReader instance.

    If given csv file has no header, provide a 'fieldnames' keyword argument,
    like you would to csv.DictReader.

    Iterating over this object returns parsed rows (Dict[str, str]).
    """
    def __init__(self, aiofile: AIOFile, **csvdictreaderparams) -> None:
        if aiofile.mode.binary:
            raise ValueError("csv file should be opened in text mode")

        self._buffer = io.StringIO(newline="")
        self._csv_reader = csv.DictReader(self._buffer, **csvdictreaderparams)

        # Guess the line terminator
        line_sep = self._csv_reader.reader.dialect.lineterminator or "\r\n"
        self._line_reader = LineReader(aiofile, line_sep=line_sep)

    @property
    def dialect(self) -> csv.Dialect:
        return self._csv_reader.reader.dialect

    @property
    def line_num(self) -> int:
        return self._csv_reader.reader.line_num

    def __aiter__(self):
        return self

    async def __anext__(self) -> Dict[str, str]:
        # check if header needs to be parsed
        if self._csv_reader._fieldnames is None:  # type: ignore
            header_line: str = await self._line_reader.readline()  # type: ignore
            self._buffer.write(header_line)

        # __init__ checked if provided file is opened in text mode
        line: str = await self._line_reader.readline()  # type: ignore

        if not line:
            raise StopAsyncIteration

        # Try to parse line
        self._buffer.write(line)
        self._buffer.seek(0)

        # Get parsed line from the underlying csv.reader instance
        try:
            result = next(self._csv_reader)
        except StopIteration as e:
            raise StopAsyncIteration from e

        # Clear the buffer
        self._buffer.seek(0)
        self._buffer.truncate(0)

        # Return parsed row
        return result


class AsyncWriter:
    """An object that writes csv rows to the given aiofile.
    In this object "row" is a sequence of values.

    Additional keyword arguments are passed to the underlying csv.writer instance.
    """
    def __init__(self, aiofile: AIOFile, **csvwriterparams) -> None:
        if aiofile.mode.binary:
            raise ValueError("csv file should be opened in text mode")

        self._afp = aiofile
        self._buffer = io.StringIO(newline="")
        self._csv_writer = csv.writer(self._buffer, **csvwriterparams)
        self._file_writer = Writer(self._afp)

    @property
    def dialect(self) -> csv.Dialect:
        return self._csv_writer.dialect

    async def _rewrite_buffer(self) -> None:
        """Writes the current value of self._buffer to the actual target file.
        """
        # Write buffer value to the AIOFile
        await self._file_writer(self._buffer.getvalue())
        await self._afp.fsync()

        # Clear buffer
        self._buffer.seek(0)
        self._buffer.truncate(0)

    async def writerow(self, row: Iterable[Any]) -> None:
        """Writes one row to the specified file."""
        # Pass row to underlying csv.writer instance
        self._csv_writer.writerow(row)

        # Write to actual file
        await self._rewrite_buffer()

    async def writerows(self, rows: Iterable[Iterable[Any]]) -> None:
        """Writes multiple rows to the specified file.

        All rows are temporarly stored in RAM before actually being written to the file,
        so don't provide a generator of loads of rows."""
        # Pass row to underlying csv.writer instance
        self._csv_writer.writerows(rows)

        # Write to actual file
        await self._rewrite_buffer()


class AsyncDictWriter:
    """An object that writes csv rows to the given aiofile.
    In this object "row" is a mapping from fieldnames to values.

    Additional keyword arguments are passed to the underlying csv.DictWriter instance.
    """
    def __init__(self, aiofile: AIOFile, fieldnames: Sequence[str], **csvdictwriterparams) -> None:
        if aiofile.mode.binary:
            raise ValueError("csv file should be opened in text mode")

        self._afp = aiofile
        self._buffer = io.StringIO(newline="")
        self._csv_writer = csv.DictWriter(self._buffer, fieldnames, **csvdictwriterparams)
        self._file_writer = Writer(self._afp)

    @property
    def dialect(self) -> csv.Dialect:
        return self._csv_writer.writer.dialect

    async def _rewrite_buffer(self) -> None:
        """Writes the current value of self._buffer to the actual target file."""
        # Write buffer value to the AIOFile
        await self._file_writer(self._buffer.getvalue())
        await self._afp.fsync()

        # Clear buffer
        self._buffer.seek(0)
        self._buffer.truncate(0)

    async def writeheader(self) -> None:
        """Writes header row to the specified file."""
        self._csv_writer.writeheader()
        await self._rewrite_buffer()

    async def writerow(self, row: Mapping[str, Any]) -> None:
        """Writes one row to the specified file."""
        self._csv_writer.writerow(row)
        await self._rewrite_buffer()

    async def writerows(self, rows: Iterable[Mapping[str, Any]]) -> None:
        """Writes multiple rows to the specified file.

        All rows are temporarly stored in RAM before actually being written to the file,
        so don't provide a generator of loads of rows."""
        self._csv_writer.writerows(rows)
        await self._rewrite_buffer()
