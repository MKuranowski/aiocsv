import csv
import io
from typing import Any, Iterable, Mapping, Sequence

from .protocols import WithAsyncWrite


class AsyncWriter:
    """An object that writes csv rows to the given asynchronous file.
    In this object "row" is a sequence of values.

    Additional keyword arguments are passed to the underlying csv.writer instance.
    """
    def __init__(self, asyncfile: WithAsyncWrite, **csvwriterparams) -> None:
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
        """Writes multiple rows to the specified file."""
        for row in rows:
            # Pass row to underlying csv.writer instance
            self._csv_writer.writerow(row)

            # Flush occasionally io prevent buffering too much data
            if self._buffer.tell() >= io.DEFAULT_BUFFER_SIZE:
                await self._rewrite_buffer()

        # Write to actual file
        await self._rewrite_buffer()


class AsyncDictWriter:
    """An object that writes csv rows to the given asynchronous file.
    In this object "row" is a mapping from fieldnames to values.

    Additional keyword arguments are passed to the underlying csv.DictWriter instance.
    """
    def __init__(self, asyncfile: WithAsyncWrite, fieldnames: Sequence[str],
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
        """Writes multiple rows to the specified file."""
        for row in rows:
            # Pass row to underlying csv.writer instance
            self._csv_writer.writerow(row)

            # Flush occasionally io prevent buffering too much data
            if self._buffer.tell() >= io.DEFAULT_BUFFER_SIZE:
                await self._rewrite_buffer()

        # Write to actual file
        await self._rewrite_buffer()
