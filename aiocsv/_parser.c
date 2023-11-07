#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>

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

typedef struct {
    PyObject_HEAD PyObject* reader;
    PyObject* current_read;
    unsigned int line_number;
    // TODO: Store dialect?
} Parser;

static PyObject* Parser_new(PyTypeObject* type, PyObject* args, PyObject* kwargs) {
    PyErr_SetString(PyExc_NotImplementedError, "TODO: Parser_new");
    return NULL;
}

static void Parser_dealloc(Parser* self) { return; }

static int Parser_init(Parser* self, PyObject* args, PyObject* kwargs) {
    PyErr_SetString(PyExc_NotImplementedError, "TODO: Parser_init");
    return -1;
}

static PyObject* Parser_anext(Parser* self) {
    PyErr_SetString(PyExc_NotImplementedError, "TODO: Parser_anext");
    return NULL;
}

static PyObject* Parser_next(Parser* self) {
    PyErr_SetString(PyExc_NotImplementedError, "TODO: Parser_next");
    return NULL;
}

static PyMemberDef ParserMembers[] = {
    {"reader", T_OBJECT_EX, offsetof(Parser, reader), 0,
     "Asynchronous reader provided in the constructor"},
    {"current_read", T_OBJECT_EX, offsetof(Parser, current_read), 0,
     "Generator returned by reader.read.__await__, used for waiting for data"},
    {"line_number", T_UINT, offsetof(Parser, line_number), 0,
     "Line number of the recently-returned row"},
    {NULL},
};

static PyAsyncMethods ParserAsyncMethods = {
    .am_aiter = Py_NewRef,  // Return "self" unchanged
    .am_anext = Parser_anext,
    .am_await = Py_NewRef,  // Return "self" unchanged
};

static PyTypeObject ParserType = {
    PyVarObject_HEAD_INIT(NULL, 0).tp_name = "_parser.parser",
    .tp_doc = PyDoc_STR("Asynchronous Iterator of CSV records from a reader"),
    .tp_basicsize = sizeof(Parser),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_members = ParserMembers,
    .tp_new = Parser_new,
    .tp_init = Parser_init,
    .tp_dealloc = Parser_dealloc,
    .tp_as_async = &ParserAsyncMethods,
    .tp_iter = Py_NewRef,  // Return "self" unchanged
    .tp_iternext = Parser_next,
};

static PyModuleDef ParserModule = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_parser",
    .m_doc = "_parser implements asynchronous CSV record parsing",
    .m_size = -1,
};

PyMODINIT_FUNC PyInit__parser(void) {
    PyObject* m;
    if (PyType_Ready(&ParserType) < 0) return NULL;

    m = PyModule_Create(&ParserModule);
    if (m == NULL) return NULL;

    Py_INCREF(&ParserType);
    if (PyModule_AddObject(m, "parser", (PyObject*)&ParserType) < 0) {
        Py_DECREF(&ParserType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
