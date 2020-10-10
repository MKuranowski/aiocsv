# aiocsv

Asynchronous CSV reading and writing.  


## Installation

Python 3.6+ is required.  
`pip3 install aiocsv`


## Usage

Always open files in text mode and with `newline=""`, otherwise bad things happen.

AsyncReader & AsyncDictReader accept any object that has a `read(size: int)` coroutine,
which should return a string.

AsyncWriter & AsyncDictWriter accept any object that has a `write(b: str)` coroutine.

All objects in `aiocsv` pass keyword arguments to the underlying
csv.reader/csv.writer/... instances.

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
    async with aiofiles.open("new_file.csv", mode="r", encoding="utf-8", newline="") as afp:
        writer = AsyncWriter(afp, dialect="unix")
        await writer.writerow(["name", "age"])
        await writer.writerows([
            ["John", 26], ["Sasha", 42], ["Hana", 37]
        ])

    # dict writing, all quoted, "NULL" for missing fields
    async with aiofiles.open("new_file2.csv", mode="r", encoding="utf-8", newline="") as afp:
        writer = AsyncDictWriter(afp, ["name", "age"], restval="NULL", quoting=csv.QUOTE_ALL)
        await writer.writeheader()
        await writer.writerow({"name": "John", "age": 26})
        await writer.writerows([
            {"name": "Sasha", "age": 42},
            {"name": "Hana"}
        ])

asyncio.run(main())
```

## Caching

AsyncReader / AsyncDictReader will read a set amount of bytes from the provided stream,
cache it in a io.StringIO. This StringIO is then consumed by the
underlying csv.reader / csv.DictReader instances.

By default 1024 bytees are read from the stream,
you can change this value by setting `aiocsv.READ_SIZE`.


AsyncWriter / AsyncDictWriter will follow provided row(s) to their
underlying csv.writer / csv.DictWriter instances.
They output produced CSV rows into a io.StringIO, which is then rewritten to the actual stream.


## Reference


### aiocsv.AsyncReader
`AsyncReader(asyncfile: aiocsv._WithAsyncRead, **csvreaderparams)`

An object that iterates over lines in given asynchronous file.  
Additional keyword arguments are passed to the underlying csv.reader instance.

Iterating over this object returns parsed CSV rows (`List[str]`).

*Methods*:
- `__aiter__(self) -> self`
- `async __anext__(self) -> List[str]`
- `__init__(self, asyncfile: aiocsv._WithAsyncRead, **csvreaderparams) -> None`

*Readonly properties*:
- `dialect`: Link to underlying's csv.reader's `dialect` attribute
- `line_num`: Link to underlying's csv.reader's `line_num` attribute


### aiocsv.AsyncDictReader
`AsyncDictReader(asyncfile: aiocsv._WithAsyncRead, **csvdictreaderparams)`

An object that iterates over lines in given asynchronous file.  
Additional keyword arguments are passed to the underlying csv.DictReader instance.

If given csv file has no header, provide a 'fieldnames' keyword argument,  
like you would to csv.DictReader.

Iterating over this object returns parsed CSV rows (`Dict[str, str]`).

*Methods*:
- `__aiter__(self) -> self`
- `async __anext__(self) -> Dict[str, str]`
- `__init__(self, asyncfile: aiocsv._WithAsyncRead, **csvdictreaderparams) -> None`

*Readonly properties*:
- `dialect`: Link to underlying's csv.reader's `dialect` attribute
- `line_num`: Link to underlying's csv.reader's `line_num` attribute


### aiocsv.AsyncWriter
`AsyncWriter(asyncfile: aiocsv._WithAsyncWrite, **csvwriterparams)`

An object that writes csv rows to the given asynchronous file.  
In this object "row" is a sequence of values.

Additional keyword arguments are passed to the underlying csv.writer instance.

*Methods*:
- `__init__(self, asyncfile: aiocsv._WithAsyncWrite, **csvwriterparams) -> None`
- `async writerow(self, row: Iterable[Any]) -> None`  
    Writes one row to the specified file.

- `async writerows(self, rows: Iterable[Iterable[Any]]) -> None`  
    Writes multiple rows to the specified file.
    
    All rows are temporarly stored in RAM before actually being written to the file,  
    so don't provide a generator of loads of rows.

*Readonly properties*:
- `dialect`: Link to underlying's csv.reader's `dialect` attribute


### aiocsv.AsyncDictWriter
`AsyncDictWriter(asyncfile: aiocsv._WithAsyncWrite, fieldnames: Sequence[str], **csvdictwriterparams)`

An object that writes csv rows to the given asynchronous file.  
In this object "row" is a mapping from fieldnames to values.

Additional keyword arguments are passed to the underlying csv.DictWriter instance.

*Methods*:
-  ``__init__(self, asyncfile: aiocsv._WithAsyncWrite, fieldnames: Sequence[str], **csvdictwriterparams) -> None``
- `async writeheader(self) -> None`  
    Writes header row to the specified file.

- `async writerow(self, row: Mapping[str, Any]) -> None`  
    Writes one row to the specified file.

- `async writerows(self, rows: Iterable[Mapping[str, Any]]) -> None`  
    Writes multiple rows to the specified file.
    
    All rows are temporarly stored in RAM before actually being written to the file,
    so don't provide a generator of loads of rows.

*Readonly properties*:
- `dialect`: Link to underlying's csv.reader's `dialect` attribute


### aiocsv.READ_SIZE
(`int`); Amout of bytes to be read when consuming streams in Reader instances.



### aiocsv._WithAsyncRead
A `typing.Protocol` describing an asynchronous file, which can be read.


### aiocsv._WithAsyncWrite
A `typing.Protocol` describing an asynchronous file, which can be written to.
