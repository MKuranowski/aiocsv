import aiofiles
import pytest

from aiocsv import AsyncDictReader, AsyncReader

DIALECT_PARAMS = {"escapechar": "$", "lineterminator": "\n"}
FILENAME = "tests/newlines.csv"
HEADER = ["field1", "field2", "field3"]
READ_VALUES = [
    ["hello", 'is it "me"', "you're\nlooking for"],
    ["this is going to be", "another\nbroken row", "this time with escapechar"],
    ["and now it's both quoted\nand", "with", "escape char"],
]


@pytest.mark.asyncio
async def test_newline_read():
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as af:
        read_rows = [i async for i in AsyncReader(af, **DIALECT_PARAMS)]
        assert read_rows == [HEADER] + READ_VALUES


@pytest.mark.asyncio
async def test_newline_dict_read():
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as af:
        read_rows = [i async for i in AsyncDictReader(af, **DIALECT_PARAMS)]

        for read_row, expected_values in zip(read_rows, READ_VALUES):
            assert read_row == dict(zip(HEADER, expected_values))
