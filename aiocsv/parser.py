import enum
import csv
from typing import AsyncIterator, List

from .protocols import WithAsyncRead

# Amout of bytes to be read when consuming streams in Reader instances
READ_SIZE: int = 2048


class ParserState(enum.Enum):
    AFTER_ROW = enum.auto()
    AFTER_DELIM = enum.auto()
    IN_CELL = enum.auto()
    ESCAPE = enum.auto()
    IN_CELL_QUOTED = enum.auto()
    ESCAPE_QUOTED = enum.auto()
    QUOTE_IN_QUOTED = enum.auto()
    EAT_NEWLINE = enum.auto()


async def parser(reader: WithAsyncRead, dialect: csv.Dialect) -> AsyncIterator[List[str]]:
    state: ParserState = ParserState.AFTER_DELIM

    data = await reader.read(READ_SIZE)
    if not isinstance(data, str):
        raise TypeError("file wasn't opened in text mode")

    force_save_cell: bool = False
    numeric_cell: bool = False
    row: List[str] = []
    cell: str = ""

    # Iterate while the reader gives out data
    while data:

        # Iterate charachter-by-charachter over the input file
        # and update the parser state
        for char in data:

            # Switch case depedning on the state

            if state == ParserState.EAT_NEWLINE:
                if char == '\r' or char == '\n':
                    continue
                state = ParserState.AFTER_ROW
            # (fallthrough)

            if state == ParserState.AFTER_ROW:
                yield row
                row = []
                state = ParserState.AFTER_DELIM

            # (fallthrough)
            if state == ParserState.AFTER_DELIM:
                # -- After the end of a field or a row --

                # 1. We were asked to skip whitespace right after the delimiter
                if dialect.skipinitialspace and char == ' ':
                    force_save_cell = True

                # 2. Empty field + End of row
                elif char == '\r' or char == '\n':
                    if len(row) > 0 or force_save_cell:
                        row.append(cell)
                    state = ParserState.EAT_NEWLINE

                # 3. Empty field
                elif char == dialect.delimiter:
                    row.append(cell)
                    cell = ""
                    force_save_cell = False
                    # state stays unchanged (AFTER_DELIM)

                # 4. Start of a quoted cell
                elif char == dialect.quotechar and dialect.quoting != csv.QUOTE_NONE:
                    state = ParserState.IN_CELL_QUOTED

                # 5. Start of an escape in an unqoted field
                elif char == dialect.escapechar:
                    state = ParserState.ESCAPE

                # 6. Start of an unquoted field
                else:
                    cell += char
                    state = ParserState.IN_CELL
                    numeric_cell = dialect.quoting == csv.QUOTE_NONNUMERIC

            elif state == ParserState.IN_CELL:
                # -- Inside an unqouted cell --

                # 1. End of a row
                if char == '\r' or char == '\n':
                    row.append(float(cell) if numeric_cell else cell)  # type: ignore

                    cell = ""
                    force_save_cell = False
                    numeric_cell = False
                    state = ParserState.EAT_NEWLINE

                # 2. End of a cell
                elif char == dialect.delimiter:
                    row.append(float(cell) if numeric_cell else cell)  # type: ignore

                    cell = ""
                    force_save_cell = False
                    numeric_cell = False
                    state = ParserState.AFTER_DELIM

                # 3. Start of an espace
                elif char == dialect.escapechar:
                    state = ParserState.ESCAPE

                # 4. Normal char
                else:
                    cell += char

            elif state == ParserState.ESCAPE:
                cell += char
                state = ParserState.IN_CELL

            elif state == ParserState.IN_CELL_QUOTED:
                # -- Inside a quoted cell --

                # 1. Start of an escape
                if char == dialect.escapechar:
                    state = ParserState.ESCAPE_QUOTED

                # 2. Quotechar
                elif dialect.quoting != csv.QUOTE_NONE and char == dialect.quotechar \
                        and dialect.doublequote:
                    state = ParserState.QUOTE_IN_QUOTED

                # 3. Every other char
                else:
                    cell += char

            elif state == ParserState.ESCAPE_QUOTED:
                cell += char
                state = ParserState.IN_CELL_QUOTED

            elif state == ParserState.QUOTE_IN_QUOTED:
                # -- Quotechar in a quoted field --
                # This state can only be entered with doublequote on

                # 1. Double-quote
                if char == dialect.quotechar:
                    cell += char
                    state = ParserState.IN_CELL_QUOTED

                # 2. End of a row
                elif char == '\r' or char == '\n':
                    row.append(cell)
                    cell = ""
                    force_save_cell = False
                    state = ParserState.EAT_NEWLINE

                # 3. End of a cell
                elif char == dialect.delimiter:
                    row.append(cell)
                    cell = ""
                    force_save_cell = False
                    state = ParserState.AFTER_DELIM

                # 4. Unescaped quotechar
                else:
                    cell += char
                    state = ParserState.IN_CELL

                    if dialect.strict:
                        raise csv.Error(
                            f"'{dialect.delimiter}' expected after '{dialect.quotechar}'"
                        )

            else:
                raise RuntimeError("wtf")

        # Read more data
        data = await reader.read(READ_SIZE)
        if not isinstance(data, str):
            raise TypeError("file wasn't opened in text mode")

    if cell or force_save_cell:
        row.append(float(cell) if numeric_cell else cell)  # type: ignore
    if row:
        yield row
