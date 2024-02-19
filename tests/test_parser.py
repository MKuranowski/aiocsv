from typing import AsyncIterator, Callable, List, Type
import pytest
import csv
import io
import sys

from aiocsv.parser import Parser as PyParser
from aiocsv._parser import Parser as CParser
from aiocsv.protocols import WithAsyncRead, DialectLike

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol


class Parser(Protocol):
    def __aiter__(self) -> AsyncIterator[List[str]]: ...
    @property
    def line_num(self) -> int: ...


PARSERS: List[Callable[[WithAsyncRead, DialectLike], Parser]] = [PyParser, CParser]
PARSER_NAMES: List[str] = ["pure_python_parser", "c_parser"]


class AsyncStringIO:
    """Simple wrapper to fulfill WithAsyncRead around a string"""

    def __init__(self, data: str = "") -> None:
        self.ptr = 0
        self.data = data

    async def read(self, size: int) -> str:
        start = self.ptr
        self.ptr += size
        return self.data[start : self.ptr]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_simple(parser: Type[Parser]):
    data = 'abc,"def",ghi\r\n' '"j""k""l",mno,pqr\r\n' 'stu,vwx,"yz"\r\n'

    csv_result = list(csv.reader(io.StringIO(data, newline="")))
    custom_result = [
        r async for r in parser(AsyncStringIO(data), csv.get_dialect("excel"))
    ]

    assert csv_result == custom_result
    assert custom_result == [
        ["abc", "def", "ghi"],
        ['j"k"l', "mno", "pqr"],
        ["stu", "vwx", "yz"],
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_escapes(parser: Type[Parser]):
    data = 'ab$"c,de$\nf\r\n' '"$"",$$gh$"\r\n' '"i\nj",k$,\r\n'
    csv_parser = csv.reader(io.StringIO(data, newline=""), escapechar="$", strict=True)
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [['ab"c', "de\nf"], ['"', '$gh"'], ["i\nj", "k,"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_empty(parser: Type[Parser]):
    data = "\r\n  a,,\r\n,\r\n  "

    csv_parser = csv.reader(
        io.StringIO(data, newline=""), skipinitialspace=True, strict=True
    )
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [[], ["a", "", ""], ["", ""], [""]]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_nonnumeric(parser: Type[Parser]):
    data = '1,2\n"a",,3.14'

    csv_parser = csv.reader(
        io.StringIO(data, newline=""), quoting=csv.QUOTE_NONNUMERIC, strict=True
    )
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [[1.0, 2.0], ["a", "", 3.14]]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_nonnumeric_invalid(parser: Type[Parser]):
    data = "1,2\na,3.14\n"

    csv_parser = csv.reader(
        io.StringIO(data, newline=""), quoting=csv.QUOTE_NONNUMERIC, strict=True
    )

    with pytest.raises(ValueError):
        list(csv_parser)

    with pytest.raises(ValueError):
        [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_none_quoting(parser: Type[Parser]):
    data = '1" hello,"2\na","3.14"'

    csv_parser = csv.reader(
        io.StringIO(data, newline=""), quoting=csv.QUOTE_NONE, strict=True
    )
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [['1" hello', '"2'], ['a"', '"3.14"']]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_weird_quotes(parser: Type[Parser]):
    data = 'a"b,$"cd"\r\n' '"ef"g",\r\n' '"$"""","e"$f"\r\n'

    csv_parser = csv.reader(io.StringIO(data, newline=""), escapechar="$", strict=False)
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [['a"b', '"cd"'], ['efg"', ""], ['""', 'e$f"']]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_strict_quoting(parser: Type[Parser]):
    data = '"ab"c,def\r\n'

    csv_parser = csv.reader(io.StringIO(data, newline=""), strict=True)

    with pytest.raises(csv.Error, match="',' expected after '\"'"):
        list(csv_parser)

    with pytest.raises(csv.Error, match="',' expected after '\"'"):
        [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_weird_quotes_nonnumeric(parser: Type[Parser]):
    data = '3.0,\r\n"1."5,"15"\r\n$2,"-4".5\r\n-5$.2,-11'

    csv_parser = csv.reader(
        io.StringIO(data, newline=""),
        quoting=csv.QUOTE_NONNUMERIC,
        escapechar="$",
        strict=False,
    )
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]

    assert csv_result == custom_result
    assert custom_result == [[3.0, ""], ["1.5", "15"], ["2", "-4.5"], [-5.2, -11.0]]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_escape_after_quote_in_quoted(parser: Type[Parser]):
    data = '"fo"$o\r\n'

    csv_parser = csv.reader(io.StringIO(data, newline=""), escapechar="$")
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]
    expected_result = [["fo$o"]]

    assert csv_result == expected_result
    assert custom_result == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_escaped_crlf(parser: Type[Parser]):
    data = "foo$\r\nbar\r\n"

    csv_parser = csv.reader(io.StringIO(data, newline=""), escapechar="$")
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]
    expected_result = [["foo\r"], ["bar"]]

    assert csv_result == expected_result
    assert custom_result == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_escaped_crlf_in_quoted(parser: Type[Parser]):
    data = '"foo$\r\n",bar\r\n'

    csv_parser = csv.reader(io.StringIO(data, newline=""), escapechar="$")
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]
    expected_result = [["foo\r\n", "bar"]]

    assert csv_result == expected_result
    assert custom_result == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_consecutive_newlines(parser: Type[Parser]):
    data = "foo\r\rbar\n\rbaz\n\nspam\r\n\neggs"

    csv_parser = csv.reader(io.StringIO(data, newline=""), escapechar="$")
    csv_result = list(csv_parser)
    custom_result = [r async for r in parser(AsyncStringIO(data), csv_parser.dialect)]
    expected_result = [["foo"], [], ["bar"], [], ["baz"], [], ["spam"], [], ["eggs"]]

    assert csv_result == expected_result
    assert custom_result == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize("parser", PARSERS, ids=PARSER_NAMES)
async def test_parsing_line_num(parser: Type[Parser]):
    data = 'foo,bar,baz\r\nspam,"egg\reggs",milk\r\n'

    csv_parser = csv.reader(io.StringIO(data, newline=""))
    csv_result = [(csv_parser.line_num, line) for line in csv_parser]

    custom_parser = parser(AsyncStringIO(data), csv_parser.dialect)
    custom_result = [(custom_parser.line_num, line) async for line in custom_parser]

    expected_result = [
        (1, ["foo", "bar", "baz"]),
        (3, ["spam", "egg\reggs", "milk"]),
    ]

    assert csv_result == expected_result
    assert custom_result == expected_result
