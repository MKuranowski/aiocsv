# aiocsv

Asynchronous CSV reading and writing.  
[AIOFile](https://pypi.org/project/aiofile/) and Python's [csv](https://docs.python.org/3/library/csv.html) module combined.


## Installation

`pip3 install aiocsv`


## Usage

All objects in `aiocsv` pass keyword arguments to the underlying
csv.reader/csv.writer/... instances.


```python
import asyncio
import csv

from aiofile import AIOFile
from aiocsv import AsyncReader, AsyncDictReader, AsyncWriter, AsyncDictWriter

async def main():
    # simple reading
    async with AIOFile("some_file.csv", mode="r", encoding="utf-8-sig") as afp:
        async for row in AsyncReader(afp):
            print(row)  # row is a list

    # dict reading, tab-separated
    async with AIOFile("some_other_file.tsv", mode="r", encoding="utf-8-sig") as afp:
        async for row in AsyncDictReader(afp, delimiter="\t"):
            print(row)  # row is a dict

    # simple writing, "unix"-dialect
    async with AIOFile("new_file.csv", mode="r", encoding="utf-8-sig") as afp:
        writer = AsyncWriter(afp, dialect="unix")
        await writer.writerow(["name", "age"])
        await writer.writerows([
            ["John", 26], ["Sasha", 42], ["Hana", 37]
        ])

    # dict writing, all quoted, "NULL" for missing fields
    async with AIOFile("another_new_file.csv", mode="r", encoding="utf-8-sig") as afp:
        writer = AsyncDictWriter(afp, ["name", "age"], restval="NULL", quoting=csv.QUOTE_ALL)
        await writer.writeheader()
        await writer.writerow({"name": "John", "age": 26})
        await writer.writerows([
            {"name": "Sasha", "age": 42},
            {"name": "Hana"}
        ])

asyncio.run(main())
```

## Reference

#### AsyncReader
```
class AsyncReader
 |  AsyncReader(aiofile: aiofile.aio.AIOFile, **csvreaderparams) -> None
 |  
 |  An object that iterates over lines in given aiofile.
 |  Additional keyword arguments are passed to the underlying csv.reader instance.
 |  
 |  Iterating over this object returns parsed rows (List[str]).
 |  
 |  ----------------------------------------------------------------------
 |  Methods defined here:
 |  
 |  __aiter__(self)
 |  
 |  async __anext__(self) -> List[str]
 |  
 |  __init__(self, aiofile: aiofile.aio.AIOFile, **csvreaderparams) -> None
 |      Initialize self.
 |  
 |  ----------------------------------------------------------------------
 |  Readonly properties defined here:
 |  
 |  dialect
 |  
 |  line_num
 |  
 |  ----------------------------------------------------------------------
```

#### AsyncDictReader
```
class AsyncDictReader(builtins.object)
 |  AsyncDictReader(aiofile: aiofile.aio.AIOFile, **csvdictreaderparams) -> None
 |  
 |  An object that iterates over lines in given aiofile.
 |  Additional keyword arguments are passed to the underlying csv.DictReader instance.
 |  
 |  If given csv file has no header, provide a 'fieldnames' keyword argument,
 |  like you would to csv.DictReader.
 |  
 |  Iterating over this object returns parsed rows (Dict[str, str]).
 |  
 |  ----------------------------------------------------------------------
 |  Methods defined here:
 |  
 |  __aiter__(self)
 |  
 |  async __anext__(self) -> Dict[str, str]
 |  
 |  __init__(self, aiofile: aiofile.aio.AIOFile, **csvdictreaderparams) -> None
 |      Initialize self.
 |  
 |  ----------------------------------------------------------------------
 |  Readonly properties defined here:
 |  
 |  dialect
 |  
 |  line_num
 |  
 |  ----------------------------------------------------------------------
 ```

#### AsyncWriter
```
class AsyncWriter(builtins.object)
 |  AsyncWriter(aiofile: aiofile.aio.AIOFile, **csvwriterparams) -> None
 |  
 |  An object that writes csv rows to the given aiofile.
 |  In this object "row" is a sequence of values.
 |  
 |  Additional keyword arguments are passed to the underlying csv.writer instance.
 |  
 |  ----------------------------------------------------------------------
 |  Methods defined here:
 |  
 |  __init__(self, aiofile: aiofile.aio.AIOFile, **csvwriterparams) -> None
 |      Initialize self.
 |  
 |  async writerow(self, row: Iterable[Any]) -> None
 |      Writes one row to the specified file.
 |  
 |  async writerows(self, rows: Iterable[Iterable[Any]]) -> None
 |      Writes multiple rows to the specified file.
 |      
 |      All rows are temporarly stored in RAM before actually being written to the file,
 |      so don't provide a generator of loads of rows.
 |  
 |  ----------------------------------------------------------------------
 |  Readonly properties defined here:
 |  
 |  dialect
 |  
 |  ----------------------------------------------------------------------
```

#### AsyncDictWriter
```
class AsyncDictWriter(builtins.object)
 |  AsyncDictWriter(aiofile: aiofile.aio.AIOFile, fieldnames: Sequence[str], **csvdictwriterparams) -> None
 |  
 |  An object that writes csv rows to the given aiofile.
 |  In this object "row" is a mapping from fieldnames to values.
 |  
 |  Additional keyword arguments are passed to the underlying csv.DictWriter instance.
 |  
 |  ----------------------------------------------------------------------
 |  Methods defined here:
 |  
 |  __init__(self, aiofile: aiofile.aio.AIOFile, fieldnames: Sequence[str], **csvdictwriterparams) -> None
 |      Initialize self.
 |  
 |  async writeheader(self) -> None
 |      Writes header row to the specified file.
 |  
 |  async writerow(self, row: Mapping[str, Any]) -> None
 |      Writes one row to the specified file.
 |  
 |  async writerows(self, rows: Iterable[Mapping[str, Any]]) -> None
 |      Writes multiple rows to the specified file.
 |      
 |      All rows are temporarly stored in RAM before actually being written to the file,
 |      so don't provide a generator of loads of rows.
 |  
 |  ----------------------------------------------------------------------
 |  Readonly properties defined here:
 |  
 |  dialect
 |  
 |  ----------------------------------------------------------------------
```
