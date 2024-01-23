from enum import IntEnum, auto
from typing import Any, Awaitable, Generator, Self, Sequence
import csv

from .protocols import DialectLike, WithAsyncRead


class ParserState(IntEnum):
    AFTER_RECORD = auto()
    AFTER_DELIMITER = auto()
    IN_FIELD = auto()
    ESCAPE = auto()
    IN_QUOTED_FIELD = auto()
    ESCAPE_IN_QUOTED = auto()
    QUOTE_IN_QUOTED = auto()
    EAT_NEWLINE = auto()


class Decision(IntEnum):
    CONTINUE = auto()
    DONE = auto()


QUOTE_MINIMAL = csv.QUOTE_MINIMAL
QUOTE_ALL = csv.QUOTE_ALL
QUOTE_NONNUMERIC = csv.QUOTE_NONNUMERIC
QUOTE_NONE = csv.QUOTE_NONE
QUOTE_STRINGS: int = getattr(csv, "QUOTE_STRINGS", 4)
QUOTE_NOTNULL: int = getattr(csv, "QUOTE_NOTNULL", 5)


class Parser:
    def __init__(self, reader: WithAsyncRead, dialect: DialectLike) -> None:
        self.dialect = dialect
        self.reader = reader

        self.current_read: Generator[Any, None, str] | None = None
        self.buffer: str = ""
        self.eof: bool = False

        self.state = ParserState.AFTER_RECORD
        self.record_so_far: list[str] = []
        self.field_so_far: list[str] = []
        self.field_was_quoted: bool = False
        self.field_was_numeric: bool = False

    # AsyncIterator[list[str]] interface

    def __aiter__(self) -> Self:
        return self

    def __anext__(self) -> Awaitable[list[str]]:
        return self

    # Awaitable[list[str]] interface

    def __await__(self) -> Generator[Any, None, list[str]]:
        return self  # type: ignore

    # Generator[Any, None, list[str]] interface

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Any:
        # Loop until a record has been successfully parsed or EOF has been hit
        record: list[str] | None = None
        while record is None and (self.buffer or not self.eof):
            # No pending read and no data available - initiate one
            if not self.buffer and self.current_read is None:
                self.current_read = self.reader.read(4096).__await__()

            # Await on the pending read
            if self.current_read is not None:
                try:
                    return next(self.current_read)
                except StopIteration as e:
                    assert not self.buffer, "a read was pending even though data was available"
                    self.current_read.close()
                    self.current_read = None
                    self.buffer = e.value
                    self.eof = not e.value

            # Advance parsing
            record = self.try_parse()

        # Generate a row, or stop iteration altogether
        if record is None:
            raise StopAsyncIteration
        else:
            raise StopIteration(record)

    # Straightforward parser interface

    def try_parse(self) -> list[str] | None:
        decision = Decision.CONTINUE

        while decision is not Decision.DONE and self.buffer:
            decision = self.advance()
            if decision is Decision.CONTINUE:
                self.buffer = self.buffer[1:]

        if decision is Decision.DONE or self.eof:
            self.add_field_at_eof()
            return self.extract_record()
        else:
            return None

    def advance(self) -> Decision:
        c = self.buffer[0]
        match self.state:
            case ParserState.AFTER_RECORD:
                return self.advance_after_record(c)
            case ParserState.AFTER_DELIMITER:
                return self.advance_after_delimiter(c)
            case ParserState.IN_FIELD:
                return self.advance_in_field(c)
            case ParserState.ESCAPE:
                return self.advance_escape(c)
            case ParserState.IN_QUOTED_FIELD:
                return self.advance_in_quoted_field(c)
            case ParserState.ESCAPE_IN_QUOTED:
                return self.advance_escape_in_quoted(c)
            case ParserState.QUOTE_IN_QUOTED:
                return self.advance_quote_in_quoted(c)
            case ParserState.EAT_NEWLINE:
                return self.advance_eat_newline(c)

    def advance_after_record(self, c: str) -> Decision:
        match c:
            case "\r" | "\n":
                self.state = ParserState.EAT_NEWLINE
                return Decision.CONTINUE
            case _:
                return self.advance_after_delimiter(c)

    def advance_after_delimiter(self, c: str) -> Decision:
        match c:
            case "\r" | "\n":
                self.add_field()
                self.state = ParserState.EAT_NEWLINE
            case self.dialect.quotechar if self.dialect.quoting != QUOTE_NONE:
                self.field_was_quoted = True
                self.state = ParserState.IN_QUOTED_FIELD
            case self.dialect.escapechar:
                self.state = ParserState.ESCAPE
            case self.dialect.delimiter:
                self.add_field()
                self.state = ParserState.AFTER_DELIMITER
            case _:
                self.field_was_numeric = self.dialect.quoting == QUOTE_NONNUMERIC
                self.field_so_far.append(c)
                self.state = ParserState.IN_FIELD
        return Decision.CONTINUE

    def advance_in_field(self, c: str) -> Decision:
        match c:
            case "\r" | "\n":
                self.add_field()
                self.state = ParserState.EAT_NEWLINE
            case self.dialect.escapechar:
                self.state = ParserState.ESCAPE
            case self.dialect.delimiter:
                self.add_field()
                self.state = ParserState.AFTER_DELIMITER
            case _:
                self.field_so_far.append(c)
        return Decision.CONTINUE

    def advance_escape(self, c: str) -> Decision:
        self.field_so_far.append(c)
        self.state = ParserState.IN_FIELD
        return Decision.CONTINUE

    def advance_in_quoted_field(self, c: str) -> Decision:
        match c:
            case self.dialect.escapechar:
                self.state = ParserState.ESCAPE_IN_QUOTED
            case self.dialect.quotechar if self.dialect.quoting != QUOTE_NONE:
                if self.dialect.doublequote:
                    self.state = ParserState.QUOTE_IN_QUOTED
                else:
                    self.state = ParserState.IN_FIELD
            case _:
                self.field_so_far.append(c)
        return Decision.CONTINUE

    def advance_escape_in_quoted(self, c: str) -> Decision:
        self.field_so_far.append(c)
        self.state = ParserState.IN_QUOTED_FIELD
        return Decision.CONTINUE

    def advance_quote_in_quoted(self, c: str) -> Decision:
        match c:
            case self.dialect.quotechar if self.dialect.quoting != QUOTE_NONE:
                self.field_so_far.append(c)  # type: ignore | wtf
                self.state = ParserState.IN_QUOTED_FIELD
            case self.dialect.delimiter:
                self.add_field()
                self.state = ParserState.AFTER_DELIMITER
            case "\r" | "\n":
                self.add_field()
                self.state = ParserState.EAT_NEWLINE
            case _ if not self.dialect.strict:
                self.field_so_far.append(c)
                self.state = ParserState.IN_FIELD
            case _:
                raise csv.Error(
                    f"{self.dialect.delimiter!r} expected after {self.dialect.quotechar!r}"
                )
        return Decision.CONTINUE

    def advance_eat_newline(self, c: str) -> Decision:
        match c:
            case "\r" | "\n":
                return Decision.CONTINUE
            case _:
                self.state = ParserState.AFTER_RECORD
                return Decision.DONE

    def add_field(self) -> None:
        field: str | float | None
        if self.dialect.skipinitialspace:
            field = "".join(self.field_so_far[self.find_first_non_space(self.field_so_far):])
        else:
            field = "".join(self.field_so_far)

        # Convert the field depending on dialect.quoting and field_was_quoted:
        # For QUOTE_NONNUMERIC: to float if not field_was_quoted
        if self.dialect.quoting == QUOTE_NONNUMERIC and field and self.field_was_numeric:
            self.field_was_numeric = False
            field = float(field)
        # TODO: For QUOTE_NOTNULL: to None if len(field) == 0 and not field_was_quoted
        # TODO: For QUOTE_STRINGS: to None if len(field) == 0 and not field_was_quoted,
        #                    to float else if not field_was_quoted
        # (No conversion otherwise)

        self.record_so_far.append(field)  # type: ignore
        self.field_so_far.clear()
        self.field_was_quoted = False

    def add_field_at_eof(self) -> None:
        # Decide if self.record_so_far needs to be added at an EOF
        if self.state not in (ParserState.AFTER_RECORD, ParserState.EAT_NEWLINE):
            self.add_field()

    def extract_record(self) -> list[str]:
        r = self.record_so_far.copy()
        self.record_so_far.clear()
        return r

    @staticmethod
    def find_first_non_space(x: Sequence[str]) -> int:
        for i, c in enumerate(x):
            if not c.isspace():
                return i
        return len(x)
