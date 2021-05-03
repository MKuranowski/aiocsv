import csv

DEF READ_SIZE = 2048


cdef enum ParserState:
    AFTER_ROW
    AFTER_DELIM
    IN_CELL
    ESCAPE
    IN_CELL_QUOTED
    ESCAPE_QUOTED
    QUOTE_IN_QUOTED
    EAT_NEWLINE


cdef enum ReadQuoting:
    NONE
    NONNUMERIC
    OTHER


cdef struct CDialect:
    bint skipinitialspace
    bint doublequote
    bint strict
    ReadQuoting quoting
    Py_UCS4 delimiter
    Py_UCS4 quotechar
    Py_UCS4 escapechar


cdef CDialect get_dialect(object pydialect):
    cdef CDialect d

    # Bools
    d.skipinitialspace = <bint?>pydialect.skipinitialspace
    d.doublequote = <bint?>pydialect.doublequote
    d.strict = <bint?>pydialect.strict

    # Quoting
    if pydialect.quoting == csv.QUOTE_NONE:
        d.quoting = ReadQuoting.NONE
    elif pydialect.quoting == csv.QUOTE_NONNUMERIC:
        d.quoting = ReadQuoting.NONNUMERIC
    else:
        d.quoting = ReadQuoting.OTHER

    # Chars
    d.delimiter = <Py_UCS4?>pydialect.delimiter[0]
    d.quotechar = <Py_UCS4?>pydialect.quotechar[0] \
        if pydialect.quotechar is not None else u'\0'
    d.escapechar = <Py_UCS4?>pydialect.escapechar[0] \
        if pydialect.escapechar is not None else u'\0'

    return d


async def parser(reader, pydialect):
    cdef unicode data = <unicode?>(await reader.read(READ_SIZE))
    cdef CDialect dialect = get_dialect(pydialect)

    cdef ParserState state = ParserState.AFTER_DELIM

    cdef list row = []
    cdef unicode cell = u""
    cdef bint force_save_cell = False
    cdef bint numeric_cell = False
    cdef Py_UCS4 char

    # Iterate while the reader gives out data
    while data:

        # Iterate charachter-by-charachter over the input file
        # and update the parser state
        for char in data:

            # Switch case depedning on the state

            if state == ParserState.EAT_NEWLINE:
                if char == u'\r' or char == u'\n':
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
                if dialect.skipinitialspace and char == u' ':
                    force_save_cell = True

                # 2. Empty field + End of row
                elif char == u'\r' or char == u'\n':
                    if len(row) > 0 or force_save_cell:
                        row.append(cell)
                    state = ParserState.EAT_NEWLINE

                # 3. Empty field
                elif char == dialect.delimiter:
                    row.append(cell)
                    cell = u""
                    force_save_cell = False
                    # state stays unchanged (AFTER_DELIM)

                # 4. Start of a quoted cell
                elif char == dialect.quotechar and dialect.quoting != ReadQuoting.NONE:
                    state = ParserState.IN_CELL_QUOTED

                # 5. Start of an escape in an unqoted field
                elif char == dialect.escapechar:
                    state = ParserState.ESCAPE

                # 6. Start of an unquoted field
                else:
                    cell += char
                    state = ParserState.IN_CELL
                    numeric_cell = dialect.quoting == ReadQuoting.NONNUMERIC

            elif state == ParserState.IN_CELL:
                # -- Inside an unqouted cell --

                # 1. End of a row
                if char == u'\r' or char == u'\n':
                    row.append(float(cell) if numeric_cell else cell)

                    cell = u""
                    force_save_cell = False
                    numeric_cell = False
                    state = ParserState.EAT_NEWLINE

                # 2. End of a cell
                elif char == dialect.delimiter:
                    row.append(float(cell) if numeric_cell else cell)  # type: ignore

                    cell = u""
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
                elif dialect.quoting != ReadQuoting.NONE and char == dialect.quotechar and \
                        dialect.doublequote:
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
                elif char == u'\r' or char == u'\n':
                    row.append(cell)
                    cell = u""
                    force_save_cell = False
                    state = ParserState.EAT_NEWLINE

                # 3. End of a cell
                elif char == dialect.delimiter:
                    row.append(cell)
                    cell = u""
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
        data = <unicode?>(await reader.read(READ_SIZE))

    if cell or force_save_cell:
        row.append(float(cell) if numeric_cell else cell)
    if row:
        yield row

