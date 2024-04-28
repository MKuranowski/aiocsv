import csv
import os
from tempfile import NamedTemporaryFile

import aiofiles
import pytest

from aiocsv import AsyncDictReader, AsyncDictWriter

FILENAME = "tests/metro_systems.tsv"
PARAMS = {"delimiter": "\t", "quotechar": "'", "quoting": csv.QUOTE_ALL}
HEADER = ["City", "Stations", "System Length"]
VALUES = [
    dict(zip(HEADER, i))
    for i in [
        ["New York", "424", "380"],
        ["Shanghai", "345", "676"],
        ["Seoul", "331", "353"],
        ["Beijing", "326", "690"],
        ["Paris", "302", "214"],
        ["London", "270", "402"],
    ]
]


@pytest.mark.asyncio
async def test_dict_read():
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as afp:
        read_rows = [i async for i in AsyncDictReader(afp, **PARAMS)]
        assert read_rows == VALUES


@pytest.mark.asyncio
async def test_dict_read_line_nums():
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as afp:
        r = AsyncDictReader(afp, **PARAMS)
        read_rows = [(row, r.line_num) async for row in r]
        assert read_rows == [(row, i) for i, row in enumerate(VALUES, start=2)]


@pytest.mark.asyncio
async def test_dict_read_get_fieldnames():
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as afp:
        reader = AsyncDictReader(afp, **PARAMS)

        assert reader.fieldnames is None
        assert await reader.get_fieldnames() == ["City", "Stations", "System Length"]
        assert reader.fieldnames == ["City", "Stations", "System Length"]


@pytest.mark.asyncio
async def test_dict_write():
    # Create a TempFile to direct writer to
    with NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as tf:
        target_name = tf.name

    try:
        # Write rows
        async with aiofiles.open(target_name, mode="w", encoding="ascii", newline="") as afp:
            writer = AsyncDictWriter(afp, HEADER, **PARAMS)
            await writer.writeheader()
            await writer.writerow(VALUES[0])
            await writer.writerows(VALUES[1:])

        # Read original and created files
        with open(target_name, mode="r", encoding="ascii") as created_f:
            created = created_f.read()

        with open(FILENAME, mode="r", encoding="ascii") as original_f:
            original = original_f.read()

        # Check if content matches
        assert created == original

    finally:
        os.remove(target_name)
