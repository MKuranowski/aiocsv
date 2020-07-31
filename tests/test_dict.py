from tempfile import NamedTemporaryFile
from aiofile import AIOFile
import pytest
import csv
import os

from aiocsv import AsyncDictReader, AsyncDictWriter

FILENAME = "tests/metro_systems.tsv"
PARAMS = {"delimiter": "\t", "quotechar": "'", "quoting": csv.QUOTE_ALL}
HEADER = ["City", "Stations", "System Length"]
VALUES = [dict(zip(HEADER, i)) for i in [
    ["New York", "424", "380"],
    ["Shanghai", "345", "676"],
    ["Seoul", "331", "353"],
    ["Beijing", "326", "690"],
    ["Paris", "302", "214"],
    ["London", "270", "402"],
]]


@pytest.mark.asyncio
async def test_dict_read():
    async with AIOFile(FILENAME, mode="r", encoding="ascii") as afp:
        read_rows = [i async for i in AsyncDictReader(afp, **PARAMS)]
        assert read_rows == VALUES


@pytest.mark.asyncio
async def test_dict_write():
    # Create a TempFile to direct writer to
    with NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as tf:
        target_name = tf.name

    try:
        # Write rows
        async with AIOFile(target_name, mode="w", encoding="ascii") as afp:
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
