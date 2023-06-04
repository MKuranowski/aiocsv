from tempfile import NamedTemporaryFile
import aiofiles
import pytest
import csv
import os
from functools import reduce

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
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as afp:
        read_rows = [i async for i in AsyncDictReader(afp, **PARAMS)]
        assert read_rows == VALUES


@pytest.mark.asyncio
async def test_dict_read_filter_rows():
    # Set filters for the rows to keep
    rowfilters = [
        lambda row: row["City"] == "Paris",
        lambda row: int(row["Stations"]) > 400,
        lambda row: row["System Length"][-1] == "0"
        ]
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as afp:
        read_rows = [
            i async for i in AsyncDictReader(afp, rowfilters=rowfilters, **PARAMS)
            ]
        result_cities = [row["City"] for row in read_rows]
        expected_cities = ["New York", "Beijing", "Paris"]
        assert result_cities == expected_cities


@pytest.mark.asyncio
async def test_dict_read_filter_columns():
    # Set filters for the rows to keep
    colfilters = [lambda fieldname: "y" in fieldname, ]
    async with aiofiles.open(FILENAME, mode="r", encoding="ascii", newline="") as afp:
        read_rows = [
            i async for i in AsyncDictReader(afp, colfilters=colfilters, **PARAMS)
            ]
        unique_fieldnames_in_result = reduce(
            lambda set1, set2: set1.union(set2), (set(row.keys()) for row in read_rows)
            )
        expected_fieldnames = {"City", "System Length"}
        assert unique_fieldnames_in_result == expected_fieldnames


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
