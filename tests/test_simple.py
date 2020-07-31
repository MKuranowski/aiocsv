from tempfile import NamedTemporaryFile
from aiofile import AIOFile
import pytest
import os

from aiocsv import AsyncReader, AsyncWriter

FILENAME = "tests/math_constants.csv"
HEADER = ["name", "value"]
VALUES = [
    ["pi", "3.1416"],
    ["sqrt2", "1.4142"],
    ["phi", "1.618"],
    ["e", "2.7183"]
]


@pytest.mark.asyncio
async def test_simple_read():
    async with AIOFile(FILENAME, mode="r", encoding="ascii") as afp:
        read_rows = [i async for i in AsyncReader(afp)]
        assert read_rows == VALUES


@pytest.mark.asyncio
async def test_simple_write():
    # Create a TempFile to direct writer to
    with NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as tf:
        target_name = tf.name

    try:
        # Write rows
        async with AIOFile(target_name, mode="w", encoding="ascii") as afp:
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
