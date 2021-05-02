import csv
import io
from typing import Dict, List, Protocol, Tuple, Union


# Amout of bytes to be read when consuming streams in Reader instances
READ_SIZE: int = 1024


class _WithAsyncRead(Protocol):
    async def read(self, __size: int) -> Union[str, bytes]: ...


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
