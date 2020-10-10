from typing import Sequence, List, Dict, Iterable, Mapping, Any, Union, Tuple
import csv
import io

try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol


__title__ = "aiocsv"
__description__ = "Asynchronous CSV reading/writing"
__version__ = "1.1.1"

__url__ = "https://github.com/MKuranowski/aiocsv"
__author__ = "Mikołaj Kuranowski"
__email__ = "".join(chr(i) for i in [109, 107, 117, 114, 97, 110, 111, 119, 115, 107, 105,
                                     64, 103, 109, 97, 105, 108, 46, 99, 111, 109])

__copyright__ = "© Copyright 2020 Mikołaj Kuranowski"
__license__ = "MIT"


# Amout of bytes to be read when consuming streams in Reader instances
READ_SIZE: int = 1024


class _WithAsyncRead(Protocol):
    async def read(self, size: int) -> Union[str, bytes]:
        ...


class _WithAsyncWrite(Protocol):
    async def write(self, b: str):
        ...


async def _read_until(buff: _WithAsyncRead, stop_char: str, leftovers: str = "") \
        -> Tuple[str, str]:
    """Reads the async stream until stop_char.
    Returns a tuple of text until `stop_char`, and whatever was leftover if too much was read.

    The first item is empty, assume end of buffer was reached."""
    value = leftovers
    while stop_char not in value:
        new_char = await buff.read(READ_SIZE)

        if not isinstance(new_char, str):
            raise TypeError("provided file was not opened in text mode")

        if not new_char:
            break

        value += new_char

    split = value.split(stop_char)
    if len(split) <= 1:
        return value, ""
    else:
        return split[0] + stop_char, stop_char.join(split[1:])


class AsyncReader:
    """An object that iterates over lines in given asynchronous file.
    Additional keyword arguments are passed to the underlying csv.reader instance.

    Iterating over this object returns parsed CSV rows (List[str]).
    """
    def __init__(self, asyncfile: _WithAsyncRead, **csvreaderparams) -> None:
        self._buffer = io.StringIO(newline="")
        self._read_leftovers = ""

        self._csv_reader = csv.reader(self._buffer, **csvreaderparams)
        self._file = asyncfile

        # Guess the line terminator
        self._line_sep = self._csv_reader.dialect.lineterminator or "\n"

    @property
    def dialect(self) -> csv.Dialect:
        return self._csv_reader.dialect

    @property
    def line_num(self) -> int:
        return self._csv_reader.line_num

    def __aiter__(self):
        return self

    async def __anext__(self) -> List[str]:
        line, self._read_leftovers = await _read_until(self._file, self._line_sep,
                                                       self._read_leftovers)

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
    """An object that iterates over lines in given asynchronous file.
    Additional keyword arguments are passed to the underlying csv.DictReader instance.

    If given csv file has no header, provide a 'fieldnames' keyword argument,
    like you would to csv.DictReader.

    Iterating over this object returns parsed CSV rows (Dict[str, str]).
    """
    def __init__(self, asyncfile: _WithAsyncRead, **csvdictreaderparams) -> None:
        self._buffer = io.StringIO(newline="")
        self._read_leftovers = ""

        self._csv_reader = csv.DictReader(self._buffer, **csvdictreaderparams)
        self._file = asyncfile

        # Guess the line terminator
        self._line_sep = self._csv_reader.reader.dialect.lineterminator or "\n"

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
            header_line, self._read_leftovers = await _read_until(self._file, self._line_sep,
                                                                  self._read_leftovers)
            self._buffer.write(header_line)

        line, self._read_leftovers = await _read_until(self._file, self._line_sep,
                                                       self._read_leftovers)

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
    """An object that writes csv rows to the given asynchronous file.
    In this object "row" is a sequence of values.

    Additional keyword arguments are passed to the underlying csv.writer instance.
    """
    def __init__(self, asyncfile: _WithAsyncWrite, **csvwriterparams) -> None:
        self._file = asyncfile
        self._buffer = io.StringIO(newline="")
        self._csv_writer = csv.writer(self._buffer, **csvwriterparams)

    @property
    def dialect(self) -> csv.Dialect:
        return self._csv_writer.dialect

    async def _rewrite_buffer(self) -> None:
        """Writes the current value of self._buffer to the actual target file.
        """
        # Write buffer value to the file
        await self._file.write(self._buffer.getvalue())

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
    """An object that writes csv rows to the given asynchronous file.
    In this object "row" is a mapping from fieldnames to values.

    Additional keyword arguments are passed to the underlying csv.DictWriter instance.
    """
    def __init__(self, asyncfile: _WithAsyncWrite, fieldnames: Sequence[str],
                 **csvdictwriterparams) -> None:
        self._file = asyncfile
        self._buffer = io.StringIO(newline="")
        self._csv_writer = csv.DictWriter(self._buffer, fieldnames, **csvdictwriterparams)

    @property
    def dialect(self) -> csv.Dialect:
        return self._csv_writer.writer.dialect

    async def _rewrite_buffer(self) -> None:
        """Writes the current value of self._buffer to the actual target file."""
        # Write buffer value to the file
        await self._file.write(self._buffer.getvalue())

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
