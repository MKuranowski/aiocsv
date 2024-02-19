# aiocsv

Asynchronous CSV reading and writing.


## Installation

`pip install aiocsv`. Python 3.8+ is required.

This module contains an extension written in C. Pre-build binaries
may not be available for your configuration. You might need a C compiler
and Python headers to install aiocsv.


## Usage

AsyncReader & AsyncDictReader accept any object that has a `read(size: int)` coroutine,
which should return a string.

AsyncWriter & AsyncDictWriter accept any object that has a `write(b: str)` coroutine.

Reading is implemented using a custom CSV parser, which should behave exactly like the CPython parser.

Writing is implemented using the synchronous csv.writer and csv.DictWriter objects -
the serializers write data to a StringIO, and that buffer is then rewritten to the underlying
asynchronous file.


## Example

Example usage with [aiofiles](https://pypi.org/project/aiofiles/).

```python
import asyncio
import csv

import aiofiles
from aiocsv import AsyncReader, AsyncDictReader, AsyncWriter, AsyncDictWriter

async def main():
    # simple reading
    async with aiofiles.open("some_file.csv", mode="r", encoding="utf-8", newline="") as afp:
        async for row in AsyncReader(afp):
            print(row)  # row is a list

    # dict reading, tab-separated
    async with aiofiles.open("some_other_file.tsv", mode="r", encoding="utf-8", newline="") as afp:
        async for row in AsyncDictReader(afp, delimiter="\t"):
            print(row)  # row is a dict

    # simple writing, "unix"-dialect
    async with aiofiles.open("new_file.csv", mode="w", encoding="utf-8", newline="") as afp:
        writer = AsyncWriter(afp, dialect="unix")
        await writer.writerow(["name", "age"])
        await writer.writerows([
            ["John", 26], ["Sasha", 42], ["Hana", 37]
        ])

    # dict writing, all quoted, "NULL" for missing fields
    async with aiofiles.open("new_file2.csv", mode="w", encoding="utf-8", newline="") as afp:
        writer = AsyncDictWriter(afp, ["name", "age"], restval="NULL", quoting=csv.QUOTE_ALL)
        await writer.writeheader()
        await writer.writerow({"name": "John", "age": 26})
        await writer.writerows([
            {"name": "Sasha", "age": 42},
            {"name": "Hana"}
        ])

asyncio.run(main())
```

## Differences with `csv`

`aiocsv` strives to be a drop-in replacement for Python's builtin [csv module](https://docs.python.org/3/library/csv.html). There are 2 notable differences:

- Readers accept objects with async `read` methods, instead of an AsyncIterable over lines
    from a file.
- `AsyncDictReader.fieldnames` can be `None` - use `await AsyncDictReader.get_fieldnames()` instead.


## Reference


### aiocsv.AsyncReader
`AsyncReader(asyncfile: aiocsv.protocols.WithAsyncRead, **csvreaderparams)`

An object that iterates over lines in given asynchronous file.
Additional keyword arguments are understood as dialect parameters.

Iterating over this object returns parsed CSV rows (`List[str]`).

*Methods*:
- `__aiter__(self) -> self`
- `async __anext__(self) -> List[str]`

*Properties*:
- `dialect`: The csv.Dialect used when parsing

*Read-only properties*:
- `line_num`: Not implemented in aiocsv - issues a warning and always returns -1.


### aiocsv.AsyncDictReader
```
AsyncDictReader(
    asyncfile: aiocsv.protocols.WithAsyncRead,
    fieldnames: Optional[Sequence[str]] = None,
    restkey: Optional[str] = None,
    restval: Optional[str] = None,
    **csvreaderparams,
)
```

An object that iterates over lines in given asynchronous file.
All arguments work exactly the same was as in csv.DictReader.

Iterating over this object returns parsed CSV rows (`Dict[str, str]`).

*Methods*:
- `__aiter__(self) -> self`
- `async __anext__(self) -> Dict[str, str]`
- `async get_fieldnames(self) -> List[str]`


*Properties*:
- `fieldnames`: field names used when converting rows to dictionaries  
    **⚠️** Unlike csv.DictReader, this property can't read the fieldnames if they are missing -
    it's not possible to `await` on the header row in a property getter.
    **Use `await reader.get_fieldnames()`**.
    ```py
    reader = csv.DictReader(some_file)
    reader.fieldnames  # ["cells", "from", "the", "header"]

    areader = aiofiles.AsyncDictReader(same_file_but_async)
    areader.fieldnames   # ⚠️ None
    await areader.get_fieldnames()  # ["cells", "from", "the", "header"]
    ```
- `restkey`: If a row has more cells then the header, all remaining cells are stored under
  this key in the returned dictionary. Defaults to `None`.
- `restval`: If a row has less cells then the header, then missing keys will use this
  value. Defaults to `None`.
- `reader`: Underlying `aiofiles.AsyncReader` instance

*Read-only properties*:
- `dialect`: Link to `self.reader.dialect` - the current csv.Dialect
- `line_num`: Not implemented in aiocsv - issues a warning and always returns -1


### aiocsv.AsyncWriter
`AsyncWriter(asyncfile: aiocsv.protocols.WithAsyncWrite, **csvwriterparams)`

An object that writes csv rows to the given asynchronous file.
In this object "row" is a sequence of values.

Additional keyword arguments are passed to the underlying csv.writer instance.

*Methods*:
- `async writerow(self, row: Iterable[Any]) -> None`:
    Writes one row to the specified file.
- `async writerows(self, rows: Iterable[Iterable[Any]]) -> None`:
    Writes multiple rows to the specified file.

*Readonly properties*:
- `dialect`: Link to underlying's csv.reader's `dialect` attribute


### aiocsv.AsyncDictWriter
`AsyncDictWriter(asyncfile: aiocsv.protocols.WithAsyncWrite, fieldnames: Sequence[str], **csvdictwriterparams)`

An object that writes csv rows to the given asynchronous file.
In this object "row" is a mapping from fieldnames to values.

Additional keyword arguments are passed to the underlying csv.DictWriter instance.

*Methods*:
- `async writeheader(self) -> None`: Writes header row to the specified file.
- `async writerow(self, row: Mapping[str, Any]) -> None`:
    Writes one row to the specified file.
- `async writerows(self, rows: Iterable[Mapping[str, Any]]) -> None`:
    Writes multiple rows to the specified file.

*Readonly properties*:
- `dialect`: Link to underlying's csv.reader's `dialect` attribute


### aiocsv.protocols.WithAsyncRead
A `typing.Protocol` describing an asynchronous file, which can be read.


### aiocsv.protocols.WithAsyncWrite
A `typing.Protocol` describing an asynchronous file, which can be written to.
