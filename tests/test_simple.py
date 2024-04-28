import os
from tempfile import NamedTemporaryFile

import aiofiles
import pytest

from aiocsv import AsyncReader, AsyncWriter

FILENAME = "tests/math_constants.csv"
HEADER = ["name", "value"]
VALUES = [["pi", "3.1416"], ["sqrt2", "1.4142"], ["phi", "1.618"], ["e", "2.7183"]]


@pytest.mark.asyncio
async def test_simple_read():
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as af:
        read_rows = [i async for i in AsyncReader(af)]
        assert read_rows == VALUES


@pytest.mark.asyncio
async def test_simple_line_nums():
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as af:
        r = AsyncReader(af)
        read_rows_and_line_nums = [(i, r.line_num) async for i in r]
        assert read_rows_and_line_nums == [(row, i) for i, row in enumerate(VALUES, start=1)]


@pytest.mark.asyncio
async def test_simple_write():
    # Create a TempFile to direct writer to
    with NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as tf:
        target_name = tf.name

    try:
        # Write rows
        async with aiofiles.open(target_name, mode="w", encoding="ascii", newline="") as afp:
            writer = AsyncWriter(afp)
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
