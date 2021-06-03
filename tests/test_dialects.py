from tempfile import NamedTemporaryFile
import aiofiles
import aiohttp
import pytest
import os

from aiocsv import AsyncReader, AsyncWriter

FILENAME = "tests/eu_cities_unix.csv"
REMOTE_FILENAME = "https://raw.githubusercontent.com/" \
                  "MKuranowski/aiocsv/master/{}".format(FILENAME)
PARAMS = {"dialect": "unix"}
VALUES = [
    ["Berlin", "Germany"],
    ["Madrid", "Spain"],
    ["Rome", "Italy"],
    ["Bucharest", "Romania"],
    ["Paris", "France"],
]


@pytest.mark.asyncio
async def test_dialect_read():
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as afp:
        read_rows = [i async for i in AsyncReader(afp, **PARAMS)]
        assert read_rows == VALUES


@pytest.mark.asyncio
async def test_dialect_network_read():
    async with aiohttp.ClientSession() as session:
        async with session.get(REMOTE_FILENAME) as response:
            read_rows = [i async for i in AsyncReader(response.content, **PARAMS)]
            assert read_rows == VALUES


@pytest.mark.asyncio
async def test_dialect_write():
    # Create a TempFile to direct writer to
    with NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as tf:
        target_name = tf.name

    try:
        # Write rows
        async with aiofiles.open(target_name, mode="w", encoding="ascii", newline="") as afp:
            writer = AsyncWriter(afp, **PARAMS)
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
