from typing import AsyncIterator, Callable, List
import pytest
import csv
import io

from aiocsv.parser import Parser as PyParser
from aiocsv.protocols import WithAsyncRead

Parser = Callable[[WithAsyncRead, csv.Dialect], AsyncIterator[List[str]]]

PARSERS: List[Parser] = [PyParser]
PARSER_NAMES: List[str] = ["pure_python_parser"]


class AsyncStringIO:
    """Simple wrapper to fulfill WithAsyncRead around a string"""
    def __init__(self, data: str = "") -> None:
        self.ptr = 0
        self.data = data

    async def read(self, size: int) -> str:
        start = self.ptr
        self.ptr += size
        return self.data[start:self.ptr]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_simple(parser: Parser):
    data = 'abc,"def",ghi\r\n' \
        '"j""k""l",mno,pqr\r\n' \
        'stu,vwx,"yz"\r\n'

    csv_result = list(csv.reader(io.StringIO(data, newline="")))
    custom_result = [r async for r in parser(AsyncStringIO(data), csv.get_dialect("excel"))]

    assert csv_result == custom_result
    assert custom_result == [
        ["abc", "def", "ghi"], ['j"k"l', "mno", "pqr"], ["stu", "vwx", "yz"]
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_escapes(parser: Parser):
    data = 'ab$"c,de$\nf\r\n' \
        '"$"",$$gh$"\r\n' \
        '"i\nj",k$,\r\n' \

    csv_parser = csv.reader(io.StringIO(data, newline=""), escapechar="$", strict=True)
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [
        ['ab"c', "de\nf"], ['"', '$gh"'], ['i\nj', "k,"]
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_empty(parser: Parser):
    data = '\r\n  a,,\r\n,\r\n  '

    csv_parser = csv.reader(io.StringIO(data, newline=""), skipinitialspace=True, strict=True)
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [
        [], ["a", "", ""], ["", ""], [""]
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_nonnumeric(parser: Parser):
    data = '1,2\n"a",,3.14'

    csv_parser = csv.reader(io.StringIO(data, newline=""), quoting=csv.QUOTE_NONNUMERIC,
                            strict=True)
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [
        [1.0, 2.0], ["a", "", 3.14]
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_nonnumeric_invalid(parser: Parser):
    data = '1,2\na,3.14\n'

    csv_parser = csv.reader(io.StringIO(data, newline=""), quoting=csv.QUOTE_NONNUMERIC,
                            strict=True)

    with pytest.raises(ValueError):
        list(csv_parser)

    with pytest.raises(ValueError):
        [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_none_quoting(parser: Parser):
    data = '1" hello,"2\na","3.14"'

    csv_parser = csv.reader(io.StringIO(data, newline=""), quoting=csv.QUOTE_NONE, strict=True)
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [
        ['1" hello', '"2'], ['a"', '"3.14"']
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_weird_quotes(parser: Parser):
    data = 'a"b,$"cd"\r\n' \
        '"ef"g",\r\n' \
        '"$"""","e"$f"\r\n'

    csv_parser = csv.reader(io.StringIO(data, newline=""), escapechar="$", strict=False)
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [
        ['a"b', '"cd"'], ['efg"', ""], ['""', 'e$f"']
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_strict_quoting(parser: Parser):
    data = '"ab"c,def\r\n'

    csv_parser = csv.reader(io.StringIO(data, newline=""), strict=True)

    with pytest.raises(csv.Error):
        list(csv_parser)

    with pytest.raises(csv.Error):
        [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_weird_quotes_nonnumeric(parser: Parser):
    data = '3.0,\r\n"1."5,"15"\r\n$2,"-4".5\r\n-5$.2,-11'

    csv_parser = csv.reader(io.StringIO(data, newline=""), quoting=csv.QUOTE_NONNUMERIC,
                            escapechar="$", strict=False)
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [
        [3.0, ""], ["1.5", "15"], ["2", "-4.5"], [-5.2, -11.0]
    ]

# TODO: Test QUOTE_STRINGS and QUOTE_NOTNULL
# TODO: Test what happens on escapechar in QUOTE_IN_QUOTED state
# TODO: Test what happens when a single escapechar escapes "\r\n" - both in quoted and unquoted
# TODO: Sequences "\r", "\n" and "\r\n" should all translate into "\n" (regardless if escaped).
# TODO: Check "foo\r\n\r\nspam\r\n".
# TODO: How to cause csv.Error("new-line character seen in unquoted field - ...")?
