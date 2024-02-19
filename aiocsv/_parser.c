#include <assert.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>

#define FINISH_WITH(new_result) \
    do {                        \
        result = (new_result);  \
        goto ret;               \
    } while (0)

#if PY_VERSION_HEX < 0x03090000

static inline PyObject* PyObject_CallMethodOneArg(PyObject* self, PyObject* name, PyObject* arg) {
    return PyObject_CallMethodObjArgs(self, name, arg, NULL);
}

#endif

#if PY_VERSION_HEX < 0x030A0000

static inline PyObject* Py_NewRef(PyObject* o) {
    Py_INCREF(o);
    return o;
}

#endif

typedef struct {
    /// csv.Error exception class
    PyObject* csv_error;

    /// csv.field_size_limit `() -> int` function
    PyObject* csv_field_size_limit;

    /// io.DEFAULT_BUFFER_SIZE number
    long io_default_buffer_size;

    /// Parser class exposed by this module
    PyTypeObject* parser_type;
} ModuleState;

#define module_get_state(m) ((ModuleState*)PyModule_GetState(m))

static int module_clear(PyObject* module) {
    ModuleState* state = module_get_state(module);
    if (state) {
        Py_CLEAR(state->csv_error);
        Py_CLEAR(state->csv_field_size_limit);
    }
    return 0;
}

static int module_traverse(PyObject* module, visitproc visit, void* arg) {
    ModuleState* state = module_get_state(module);
    if (state) {
        Py_VISIT(state->csv_error);
        Py_VISIT(state->csv_field_size_limit);
    }
    return 0;
}

static void module_free(void* module) { module_clear((PyObject*)module); }

// Parser implements the outer AsyncIterator[List[str]] protocol (__aiter__ + __anext__),
// but, to avoid allocating new object on each call to __anext__, Parser returns itself from
// __anext__. So, Parser also implements Awaitable[list[str]] (which also returns itself) and
// Generator[Any, None, List[str]].
//
// The full interface looks like this:
// ```py
// class Parser:
//     reader: WithAsyncRead
//     current_read: Generator[Any, None, str] | None: ...
//     line_number: int
//
//     def __init__(self, __r: WithAsyncRead, __d: DialectLike) -> None: ...
//     def __aiter__(self) -> Self: ...
//     def __anext__(self) -> Self: ...
//     def __await__(self) -> Self: ...
//     def __iter__(self) -> Self: ...
//     def __next__(self) -> list[str]: ...
// ```

/// A character which can't appear in a string
#define NO_CHAR (Py_UCS4) - 1

typedef enum {
    QUOTE_MINIMAL = 0,
    QUOTE_ALL = 1,
    QUOTE_NON_NUMERIC = 2,
    QUOTE_NONE = 3,
} Quoting;

typedef enum {
    STATE_START_RECORD = 0,
    STATE_START_FIELD,
    STATE_IN_FIELD,
    STATE_ESCAPE,
    STATE_IN_QUOTED_FIELD,
    STATE_ESCAPE_IN_QUOTED,
    STATE_QUOTE_IN_QUOTED,
    STATE_EAT_NEWLINE,
} ParserState;

static inline bool state_is_end_of_record(ParserState s) {
    switch (s) {
        case STATE_START_RECORD:
        case STATE_EAT_NEWLINE:
            return true;

        default:
            return false;
    }
}

typedef enum {
    /// Parsing should continue - row is not ready
    DECISION_CONTINUE,

    /// Parsing should stop - a row is ready
    DECISION_DONE,

    /// Parsing should stop - a row is ready.
    /// Current char should not be removed from the buffer.
    DECISION_DONE_WITHOUT_CONSUMING,

    /// An error was encountered - parsing must halt immediately
    DECISION_ERROR,
} Decision;

typedef struct {
    Py_UCS4 delimiter;
    Py_UCS4 quotechar;
    Py_UCS4 escapechar;
    unsigned char quoting;
    bool doublequote;
    bool skipinitialspace;
    bool strict;
} Dialect;

#define dialect_init_char(d, o, attr_name)                                                  \
    PyObject* attr_name = PyObject_GetAttrString((o), #attr_name);                          \
    if (attr_name) {                                                                        \
        (d)->attr_name = PyUnicode_ReadChar(attr_name, 0);                                  \
        if (PyErr_Occurred()) {                                                             \
            Py_DECREF(attr_name);                                                           \
            return 0;                                                                       \
        }                                                                                   \
    } else {                                                                                \
        PyErr_SetString(PyExc_AttributeError, "dialect has no attribute '" #attr_name "'"); \
        return 0;                                                                           \
    }                                                                                       \
    Py_DECREF(attr_name);

#define dialect_init_optional_char(d, o, attr_name)                                         \
    PyObject* attr_name = PyObject_GetAttrString((o), #attr_name);                          \
    if (attr_name == Py_None) {                                                             \
        (d)->attr_name = NO_CHAR;                                                           \
    } else if (attr_name) {                                                                 \
        (d)->attr_name = PyUnicode_ReadChar(attr_name, 0);                                  \
        if (PyErr_Occurred()) {                                                             \
            Py_DECREF(attr_name);                                                           \
            return 0;                                                                       \
        }                                                                                   \
    } else {                                                                                \
        PyErr_SetString(PyExc_AttributeError, "dialect has no attribute '" #attr_name "'"); \
        return 0;                                                                           \
    }                                                                                       \
    Py_DECREF(attr_name);

#define dialect_init_bool(d, o, attr_name)                                                  \
    PyObject* attr_name = PyObject_GetAttrString((o), #attr_name);                          \
    if (attr_name == NULL) {                                                                \
        PyErr_SetString(PyExc_AttributeError, "dialect has no attribute '" #attr_name "'"); \
        return 0;                                                                           \
    }                                                                                       \
    (d)->attr_name = PyObject_IsTrue(attr_name);                                            \
    Py_DECREF(attr_name);

#define dialect_init_quoting(d, o)                                                              \
    PyObject* quoting = PyObject_GetAttrString(o, "quoting");                                   \
    if (quoting == NULL) {                                                                      \
        PyErr_SetString(PyExc_AttributeError, "dialect has no attribute 'quoting'");            \
        return 0;                                                                               \
    }                                                                                           \
    Py_ssize_t quoting_value = PyNumber_AsSsize_t(quoting, NULL);                               \
    Py_DECREF(quoting);                                                                         \
    if (PyErr_Occurred()) {                                                                     \
        return 0;                                                                               \
    }                                                                                           \
    if (quoting_value < (Py_ssize_t)QUOTE_MINIMAL || quoting_value > (Py_ssize_t)QUOTE_NONE) {  \
        PyErr_Format(PyExc_ValueError, "dialect.quoting: unexpected value %zd", quoting_value); \
        return 0;                                                                               \
    }                                                                                           \
    d->quoting = (unsigned char)quoting_value;

int Dialect_init(Dialect* d, PyObject* o) {
    dialect_init_char(d, o, delimiter);
    dialect_init_optional_char(d, o, quotechar);
    dialect_init_optional_char(d, o, escapechar);
    dialect_init_quoting(d, o);
    dialect_init_bool(d, o, doublequote);
    dialect_init_bool(d, o, skipinitialspace);
    dialect_init_bool(d, o, strict);
    return 1;
}

#define PARSER_BUFFER_CAPACITY 4096
static_assert(
    PARSER_BUFFER_CAPACITY <= USHRT_MAX,
    "Parser buffer is indexed by unsigned short - capacity must be smaller than USHRT_MAX");

typedef struct {
    // clang-format off
    PyObject_HEAD

    /// Pointer to the _parser module. Required for 3.8 compatibility.
    ///
    /// TODO: Drop field once support for 3.8 is dropped.
    ///       PyType_GetModuleState(Py_TYPE(self)) should be used instead.
    PyObject* module;

    /// Anything with a `async def read(self, n: int) -> str` method.
    PyObject* reader;

    /// Generator[Any, None, str] if waiting for a read, NULL otherwise.
    PyObject* current_read;

    /// Data returned by the latest read
    Py_UCS4 buffer[PARSER_BUFFER_CAPACITY];

    /// list[str] with parsed fields from the current record. Lazily allocated, may be NULL.
    PyObject* record_so_far;

    /// PyMem-allocated buffer for characters of the current field.
    Py_UCS4* field_so_far;

    /// Capacity of `field_so_far`.
    Py_ssize_t field_so_far_capacity;

    /// Number of characters in `field_so_far`.
    Py_ssize_t field_so_far_len;

    /// C-friendly representation of the csv dialect.
    Dialect dialect;

    /// Limit for the field size
    long field_size_limit;

    /// Zero-based line number of the current position, which is equivalent to
    /// a one-based line number of the last-encountered line.
    unsigned int line_num;

    /// Number of valid characters in buffer
    unsigned short buffer_len;

    /// Offset into buffer to the first valid character
    unsigned short buffer_idx;

    /// ParserState for the parser state machine.
    unsigned char state;

    /// True if current field should be interpreted as a float.
    bool field_was_numeric;

    /// True if last returned character was a CR, used to avoid counting CR-LF as two separate lines.
    bool last_char_was_cr;

    /// True if eof has been hit in the underlying reader.
    bool eof;

    // clang-format on
} Parser;

static void Parser_dealloc(Parser* self) {
    PyTypeObject* tp = Py_TYPE(self);
    PyObject_GC_UnTrack(self);
    tp->tp_clear((PyObject*)self);
    if (self->field_so_far) {
        PyMem_Free(self->field_so_far);
        self->field_so_far = NULL;
    }
    PyObject_GC_Del(self);
    Py_DECREF(tp);
}

static int Parser_traverse(Parser* self, visitproc visit, void* arg) {
    Py_VISIT(self->module);
    Py_VISIT(self->reader);
    Py_VISIT(self->current_read);
    Py_VISIT(self->record_so_far);
#if PY_VERSION_HEX >= 0x03090000
    Py_VISIT(Py_TYPE(self));
#endif
    return 0;
}

static int Parser_clear(Parser* self) {
    Py_CLEAR(self->module);
    Py_CLEAR(self->reader);
    Py_CLEAR(self->current_read);
    Py_CLEAR(self->record_so_far);
    return 0;
}

static PyObject* Parser_new(PyObject* module, PyObject* args, PyObject* kwargs) {
    ModuleState* state = module_get_state(module);

    Parser* self = PyObject_GC_New(Parser, state->parser_type);
    if (!self) return NULL;

    PyObject* reader;
    PyObject* dialect;
    static char* kw_list[] = {"reader", "dialect", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO", kw_list, &reader, &dialect)) {
        Py_DECREF(self);
        return NULL;
    }

    if (!Dialect_init(&self->dialect, dialect)) {
        Py_DECREF(self);
        return NULL;
    }

    self->module = Py_NewRef(module);
    self->reader = Py_NewRef(reader);

    PyObject* field_size_limit_obj =
        PyObject_CallObject(module_get_state(module)->csv_field_size_limit, NULL);
    if (!field_size_limit_obj) {
        Py_DECREF(self);
        return NULL;
    }

    self->field_size_limit = PyLong_AsLong(field_size_limit_obj);
    Py_DECREF(field_size_limit_obj);
    if (PyErr_Occurred()) {
        Py_DECREF(self);
        return NULL;
    }

    self->current_read = NULL;
    self->record_so_far = NULL;
    self->field_so_far = NULL;
    self->field_so_far_capacity = 0;
    self->field_so_far_len = 0;
    self->line_num = 0;
    self->buffer_len = 0;
    self->buffer_idx = 0;
    self->state = STATE_START_RECORD;
    self->field_was_numeric = false;
    self->last_char_was_cr = false;
    self->eof = false;

    PyObject_GC_Track(self);
    return (PyObject*)self;
}

static int Parser_add_char(Parser* self, Py_UCS4 c) {
    if (self->field_so_far_len == self->field_size_limit) {
        PyObject* err = module_get_state(self->module)->csv_error;
        PyErr_Format(err, "field larger than field limit (%ld)", self->field_size_limit);
        return 0;
    } else if (self->field_so_far_len >= self->field_so_far_capacity) {
        Py_ssize_t new_capacity =
            self->field_so_far_capacity ? self->field_so_far_capacity * 2 : 4096;
        Py_UCS4* new_buffer = self->field_so_far;
        PyMem_Resize(new_buffer, Py_UCS4, new_capacity);
        if (new_buffer == NULL) {
            PyErr_NoMemory();
            return 0;
        }
        self->field_so_far = new_buffer;
        self->field_so_far_capacity = new_capacity;
    }

    assert(self->field_so_far_len < self->field_so_far_capacity);
    self->field_so_far[self->field_so_far_len] = c;
    ++self->field_so_far_len;
    return 1;
}

static Py_ssize_t find_first_non_space(Py_UCS4* str, Py_ssize_t len) {
    Py_ssize_t i = 0;
    while (i < len && Py_UNICODE_ISSPACE(str[i])) ++i;
    return i;
}

static int Parser_save_field(Parser* self) {
    // Ensure parser has a list
    if (!self->record_so_far) {
        self->record_so_far = PyList_New(0);
        if (!self->record_so_far) return 0;
    }

    // Convert field_so_far to a PyUnicode object
    PyObject* field = NULL;
    if (self->dialect.skipinitialspace) {
        Py_ssize_t offset = find_first_non_space(self->field_so_far, self->field_so_far_len);
        field = PyUnicode_FromKindAndData(PyUnicode_4BYTE_KIND, self->field_so_far + offset,
                                          self->field_so_far_len - offset);
    } else {
        field = PyUnicode_FromKindAndData(PyUnicode_4BYTE_KIND, self->field_so_far,
                                          self->field_so_far_len);
    }
    if (!field) return 0;

    self->field_so_far_len = 0;

    // Cast the field to a float, if applicable
    if (self->field_was_numeric) {
        self->field_was_numeric = false;

        PyObject* field_as_float = PyFloat_FromString(field);
        Py_DECREF(field);
        if (!field_as_float) return 0;
        field = field_as_float;
    }

    // Append the field to the record
    int failed = PyList_Append(self->record_so_far, field);
    Py_DECREF(field);

    // because fuck consistent error handling
    // sometimes Python returns 0 on success (PyList_Append),
    // sometimes Python returns 0 on failure (PyArg_*)
    return !failed;
}

static inline int Parser_add_field_at_eof(Parser* self) {
    if (!state_is_end_of_record(self->state)) return Parser_save_field(self);
    return 1;
}

static inline PyObject* Parser_extract_record(Parser* self) {
    PyObject* lst = self->record_so_far;
    self->record_so_far = NULL;
    return lst ? lst : PyList_New(0);
}

static Py_UCS4 Parser_get_char_and_increment_line_num(Parser* self) {
    assert(self->buffer_idx < self->buffer_len);
    Py_UCS4 c = self->buffer[self->buffer_idx];

    if (c == '\r') {
        ++self->line_num;
        self->last_char_was_cr = true;
    } else if (c == '\n') {
        self->line_num += !self->last_char_was_cr;  // increment if not part of a CRLF
        self->last_char_was_cr = false;
    } else {
        self->last_char_was_cr = false;
    }

    return c;
}

static Decision Parser_process_char_in_eat_newline(Parser* self, Py_UCS4 c) {
    self->state = STATE_START_RECORD;
    return c == '\n' ? DECISION_DONE : DECISION_DONE_WITHOUT_CONSUMING;
}

static Decision Parser_process_char_in_quote_in_quoted(Parser* self, Py_UCS4 c) {
    if (c == self->dialect.quotechar && self->dialect.quoting != QUOTE_NONE) {
        if (!Parser_add_char(self, c)) return DECISION_ERROR;
        self->state = STATE_IN_QUOTED_FIELD;
        return DECISION_CONTINUE;
    } else if (c == self->dialect.delimiter) {
        if (!Parser_save_field(self)) return DECISION_ERROR;
        self->state = STATE_START_FIELD;
        return DECISION_CONTINUE;
    } else if (c == '\r') {
        if (!Parser_save_field(self)) return DECISION_ERROR;
        self->state = STATE_EAT_NEWLINE;
        return DECISION_CONTINUE;
    } else if (c == '\n') {
        if (!Parser_save_field(self)) return DECISION_ERROR;
        self->state = STATE_START_RECORD;
        return DECISION_DONE;
    } else if (!self->dialect.strict) {
        if (!Parser_add_char(self, c)) return DECISION_ERROR;
        self->state = STATE_IN_FIELD;
        return DECISION_CONTINUE;
    } else {
        PyObject* csv_error = module_get_state(self->module)->csv_error;
        PyErr_Format(csv_error, "'%c' expected after '%c'", self->dialect.delimiter,
                     self->dialect.quotechar);
        return DECISION_ERROR;
    }
}

static Decision Parser_process_char_in_escape_in_quoted(Parser* self, Py_UCS4 c) {
    if (!Parser_add_char(self, c)) return DECISION_ERROR;
    self->state = STATE_IN_QUOTED_FIELD;
    return DECISION_CONTINUE;
}

static Decision Parser_process_char_in_quoted_field(Parser* self, Py_UCS4 c) {
    if (c == self->dialect.escapechar) {
        self->state = STATE_ESCAPE_IN_QUOTED;
        return DECISION_CONTINUE;
    } else if (c == self->dialect.quotechar && self->dialect.quoting != QUOTE_NONE) {
        self->state = self->dialect.doublequote ? STATE_QUOTE_IN_QUOTED : STATE_IN_FIELD;
        return DECISION_CONTINUE;
    } else {
        if (!Parser_add_char(self, c)) return DECISION_ERROR;
        return DECISION_CONTINUE;
    }
}

static Decision Parser_process_char_in_escape(Parser* self, Py_UCS4 c) {
    if (!Parser_add_char(self, c)) return DECISION_ERROR;
    self->state = STATE_IN_FIELD;
    return DECISION_CONTINUE;
}

static Decision Parser_process_char_in_field(Parser* self, Py_UCS4 c) {
    if (c == '\r') {
        if (!Parser_save_field(self)) return DECISION_ERROR;
        self->state = STATE_EAT_NEWLINE;
        return DECISION_CONTINUE;
    } else if (c == '\n') {
        if (!Parser_save_field(self)) return DECISION_ERROR;
        self->state = STATE_START_RECORD;
        return DECISION_DONE;
    } else if (c == self->dialect.escapechar) {
        self->state = STATE_ESCAPE;
        return DECISION_CONTINUE;
    } else if (c == self->dialect.delimiter) {
        if (!Parser_save_field(self)) return DECISION_ERROR;
        self->state = STATE_START_FIELD;
        return DECISION_CONTINUE;
    } else {
        if (!Parser_add_char(self, c)) return DECISION_ERROR;
        // self->state = STATE_IN_FIELD; // already is STATE_IN_FIELD
        return DECISION_CONTINUE;
    }
}

static Decision Parser_process_char_in_start_field(Parser* self, Py_UCS4 c) {
    if (c == '\r') {
        if (!Parser_save_field(self)) return DECISION_ERROR;
        self->state = STATE_EAT_NEWLINE;
        return DECISION_CONTINUE;
    } else if (c == '\n') {
        if (!Parser_save_field(self)) return DECISION_ERROR;
        self->state = STATE_START_RECORD;
        return DECISION_DONE;
    } else if (c == self->dialect.quotechar && self->dialect.quoting != QUOTE_NONE) {
        self->state = STATE_IN_QUOTED_FIELD;
        return DECISION_CONTINUE;
    } else if (c == self->dialect.escapechar) {
        self->state = STATE_ESCAPE;
        return DECISION_CONTINUE;
    } else if (c == self->dialect.delimiter) {
        if (!Parser_save_field(self)) return DECISION_ERROR;
        self->state = STATE_START_FIELD;
        return DECISION_CONTINUE;
    } else {
        self->field_was_numeric = self->dialect.quoting == QUOTE_NON_NUMERIC;
        if (!Parser_add_char(self, c)) return DECISION_ERROR;
        self->state = STATE_IN_FIELD;
        return DECISION_CONTINUE;
    }
}

static Decision Parser_process_char_in_start_record(Parser* self, Py_UCS4 c) {
    if (c == '\r') {
        self->state = STATE_EAT_NEWLINE;
        return DECISION_CONTINUE;
    } else if (c == '\n') {
        self->state = STATE_START_RECORD;
        return DECISION_DONE;
    } else {
        return Parser_process_char_in_start_field(self, c);
    }
}

static Decision Parser_process_char(Parser* self, Py_UCS4 c) {
    switch ((ParserState)self->state) {
        case STATE_START_RECORD:
            return Parser_process_char_in_start_record(self, c);
        case STATE_START_FIELD:
            return Parser_process_char_in_start_field(self, c);
        case STATE_IN_FIELD:
            return Parser_process_char_in_field(self, c);
        case STATE_ESCAPE:
            return Parser_process_char_in_escape(self, c);
        case STATE_IN_QUOTED_FIELD:
            return Parser_process_char_in_quoted_field(self, c);
        case STATE_ESCAPE_IN_QUOTED:
            return Parser_process_char_in_escape_in_quoted(self, c);
        case STATE_QUOTE_IN_QUOTED:
            return Parser_process_char_in_quote_in_quoted(self, c);
        case STATE_EAT_NEWLINE:
            return Parser_process_char_in_eat_newline(self, c);
    }
    Py_UNREACHABLE();
}

static PyObject* Parser_try_parse(Parser* self) {
    Decision decision = DECISION_CONTINUE;
    while (decision == DECISION_CONTINUE && self->buffer_idx < self->buffer_len) {
        Py_UCS4 c = Parser_get_char_and_increment_line_num(self);
        decision = Parser_process_char(self, c);

        if (decision == DECISION_ERROR) {
            if (!PyErr_Occurred()) {
                PyErr_Format(PyExc_SystemError,
                             "Parser_process_char (state %d) returned DECISION_ERROR without "
                             "setting an exception",
                             (int)self->state);
            }
            return NULL;
        }

        if (decision != DECISION_DONE_WITHOUT_CONSUMING) ++self->buffer_idx;
    }

    if (decision != DECISION_CONTINUE || (self->eof && !state_is_end_of_record(self->state))) {
        Parser_add_field_at_eof(self);
        return Parser_extract_record(self);
    }
    return NULL;
}

static int Parser_initiate_read(Parser* self) {
    assert(!self->current_read);

    PyObject* name = NULL;
    PyObject* len = NULL;
    PyObject* read_coro = NULL;
    int result = 1;

    name = PyUnicode_FromStringAndSize("read", 4);
    if (!name) FINISH_WITH(0);

    len = PyLong_FromLong(PARSER_BUFFER_CAPACITY);
    if (!len) FINISH_WITH(0);

    read_coro = PyObject_CallMethodOneArg(self->reader, name, len);
    if (!read_coro) FINISH_WITH(0);

    PyAsyncMethods* coro_async_methods = Py_TYPE(read_coro)->tp_as_async;
    if (!coro_async_methods || !coro_async_methods->am_await) {
        PyErr_Format(PyExc_TypeError, "reader.read returned %R, which is not awaitable",
                     read_coro);
        FINISH_WITH(0);
    }

    self->current_read = coro_async_methods->am_await(read_coro);
    result = self->current_read ? 1 : 0;

ret:
    if (name) Py_DECREF(name);
    if (len) Py_DECREF(len);
    if (read_coro) Py_DECREF(read_coro);
    return result;
}

// TODO: Simplify once support for 3.8 and 3.9 is dropped

typedef enum {
    AR_COMPLETE = 0,
    AR_ERROR = -1,
    AR_YIELD = 1,
} AdvanceReadResult;

// #if PY_VERSION_HEX < 0x030A0000
#if 1

static PyObject* PyErr_FetchStopIterationValue(void) {
    PyObject* exc_type;
    PyObject* exc_value;
    PyObject* exc_traceback;
    PyErr_Fetch(&exc_type, &exc_value, &exc_traceback);

    assert(exc_type);
    assert(PyErr_ExceptionMatches(PyExc_StopIteration));

    PyErr_NormalizeException(&exc_type, &exc_value, &exc_traceback);
    assert(PyObject_TypeCheck(exc_value, (PyTypeObject*)PyExc_StopIteration));

    PyErr_Clear();

    PyObject* value = ((PyStopIterationObject*)exc_value)->value;
    Py_INCREF(value);
    Py_XDECREF(exc_type);
    Py_XDECREF(exc_value);
    Py_XDECREF(exc_traceback);
    return value;
}

static inline AdvanceReadResult Parser_advance_read(Parser* self, PyObject** str_or_yield) {
    *str_or_yield = (Py_TYPE(self->current_read)->tp_iternext)(self->current_read);
    if (*str_or_yield) return AR_YIELD;
    if (!PyErr_ExceptionMatches(PyExc_StopIteration)) return AR_ERROR;
    *str_or_yield = PyErr_FetchStopIterationValue();
    return AR_COMPLETE;
}

#else

static inline AdvanceReadResult Parser_advance_read(Parser* self, PyObject** str_or_yield) {
    switch (PyIter_Send(self->current_read, Py_None, str_or_yield)) {
        case PYGEN_RETURN:
            return AR_COMPLETE;
        case PYGEN_ERROR:
            return AR_ERROR;
        case PYGEN_NEXT:
            return AR_YIELD;
        default:
            Py_UNREACHABLE();
    }
}

#endif

static int Parser_copy_to_buffer(Parser* self, PyObject* unicode) {
    int result = 1;

    if (!PyUnicode_Check(unicode)) {
        PyErr_Format(PyExc_TypeError, "reader.read() returned %R, expected str", Py_TYPE(unicode));
        FINISH_WITH(0);
    }

    Py_ssize_t len = PyUnicode_GetLength(unicode);
    if (len < 0) {
        FINISH_WITH(0);
    } else if (len == 0) {
        self->buffer_len = 0;
        self->buffer_idx = 0;
        self->eof = true;
    } else if (len <= PARSER_BUFFER_CAPACITY) {
        if (!PyUnicode_AsUCS4(unicode, self->buffer, PARSER_BUFFER_CAPACITY, false))
            FINISH_WITH(0);
        self->buffer_len = (unsigned short)len;
        self->buffer_idx = 0;
    } else {
        PyErr_Format(PyExc_ValueError,
                     "reader has read %zi bytes, which is more than the requested %i bytes", len,
                     PARSER_BUFFER_CAPACITY);
        FINISH_WITH(0);
    }

ret:
    Py_DECREF(unicode);
    return result;
}

static PyObject* Parser_next(Parser* self) {
    // Loop until a record has been successfully parsed or EOF has been hit
    PyObject* record = NULL;
    while (!record && (self->buffer_len > 0 || !self->eof)) {
        // No pending read and no data available - initiate a read
        if (self->buffer_idx == self->buffer_len && self->current_read == NULL) {
            if (!Parser_initiate_read(self)) return NULL;
        }

        // Await on the pending read
        if (self->current_read) {
            PyObject* read_str;
            switch (Parser_advance_read(self, &read_str)) {
                case AR_COMPLETE:
                    break;
                case AR_ERROR:
                    return NULL;
                case AR_YIELD:
                    return read_str;
            }

            Py_DECREF(self->current_read);
            self->current_read = NULL;

            if (!Parser_copy_to_buffer(self, read_str)) return NULL;
        }

        // Advance parsing
        record = Parser_try_parse(self);
        if (PyErr_Occurred()) return NULL;
    }

    // Generate a row or stop iteration altogether
    if (record) {
        PyErr_SetObject(PyExc_StopIteration, record);
    } else {
        PyErr_SetNone(PyExc_StopAsyncIteration);
    }
    return NULL;
}

// TODO: Once support 3.8 is dropped, the "Parser" function can be replaced by
//       normal .tp_new and .tp_init members on the "_Parser" type.
//       Starting with 3.9 it's possible to access modules state from the _Parser type
//       with PyType_GetModuleState, but on 3.8 the module needs to be passed around directly
//       from the fake constructor-function.

static PyMethodDef ParserMethods[] = {{NULL, NULL}};

static PyMemberDef ParserMembers[] = {
    {"line_num", T_UINT, offsetof(Parser, line_num), 0,
     "Line number of the recently-returned row"},
    {NULL},
};

static PyType_Slot ParserSlots[] = {
    {Py_tp_doc, "Asynchronous Iterator of CSV records from a reader"},
    {Py_tp_traverse, Parser_traverse},
    {Py_tp_clear, Parser_clear},
    {Py_tp_dealloc, Parser_dealloc},
    {Py_tp_members, ParserMembers},
    {Py_tp_methods, ParserMethods},
    {Py_am_await, Py_NewRef},  // Return "self" unchanged
    {Py_am_aiter, Py_NewRef},  // Return "self" unchanged
    {Py_am_anext, Py_NewRef},  // Return "self" unchanged
    {Py_tp_iter, Py_NewRef},   // Return "self" unchanged
    {Py_tp_iternext, Parser_next},
    {0, NULL},
};

static PyType_Spec ParserSpec = {
    .name = "_parser._Parser",
    .basicsize = sizeof(Parser),
    .itemsize = 0,
    .flags = (Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_IMMUTABLETYPE |
              Py_TPFLAGS_DISALLOW_INSTANTIATION),
    .slots = ParserSlots,
};

static int module_exec(PyObject* module) {
    int result = 0;
    PyObject* csv_module = NULL;
    PyObject* io_module = NULL;
    PyObject* io_default_buffer_size_obj = NULL;

    ModuleState* state = module_get_state(module);

    csv_module = PyImport_ImportModule("csv");
    if (!csv_module) FINISH_WITH(-1);

    state->csv_error = PyObject_GetAttrString(csv_module, "Error");
    if (!state->csv_error) FINISH_WITH(-1);

    state->csv_field_size_limit = PyObject_GetAttrString(csv_module, "field_size_limit");
    if (!state->csv_field_size_limit) FINISH_WITH(-1);

    io_module = PyImport_ImportModule("io");
    if (!io_module) FINISH_WITH(-1);

    io_default_buffer_size_obj = PyObject_GetAttrString(io_module, "DEFAULT_BUFFER_SIZE");
    if (!io_default_buffer_size_obj) FINISH_WITH(-1);

    state->io_default_buffer_size = PyLong_AsLong(io_default_buffer_size_obj);
    if (PyErr_Occurred()) FINISH_WITH(-1);
    if (state->io_default_buffer_size <= 0) {
        PyErr_Format(PyExc_ValueError,
                     "io.DEFAULT_BUFFER_SIZE is %ld, expected a positive integer",
                     state->io_default_buffer_size);
        FINISH_WITH(-1);
    }

    state->parser_type = (PyTypeObject*)PyType_FromSpec(&ParserSpec);
    if (!state->parser_type) FINISH_WITH(-1);

ret:
    Py_XDECREF(csv_module);
    Py_XDECREF(io_module);
    Py_XDECREF(io_default_buffer_size_obj);
    return result;
}

static PyMethodDef ModuleMethods[] = {
    {"Parser", _PyCFunction_CAST(Parser_new), METH_VARARGS | METH_KEYWORDS,
     "Creates a new Parser instance"},
    {NULL, NULL},
};

static PyModuleDef_Slot ModuleSlots[] = {
    {Py_mod_exec, module_exec},
#if PY_VERSION_HEX >= 0x030C0000
    {Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
#endif
    {0, NULL},
};

static PyModuleDef Module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "_parser",
    .m_doc = "_parser implements asynchronous CSV record parsing",
    .m_size = sizeof(ModuleState),
    .m_slots = ModuleSlots,
    .m_methods = ModuleMethods,
    .m_traverse = module_traverse,
    .m_clear = module_clear,
    .m_free = module_free,
};

PyMODINIT_FUNC PyInit__parser(void) { return PyModuleDef_Init(&Module); }
