/*
 * tree-sitter C 扩展 — matha-auth 高性能解析器后端
 *
 * 提供 Rust/Go/JS/C 的树形解析 C 绑定。
 * 构建: pip install -e . --config-settings editable-verbose=true
 * 降级: 构建失败时自动回退到纯 Python 解析器
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <tree_sitter/api.h>

/* 语言注册表 */
typedef struct {
    const char *name;
    TSLanguage *(*language)(void);
} LangEntry;

static LangEntry lang_entries[] = {
    {"rust",   tree_sitter_rust},
    {"go",     tree_sitter_go},
    {"javascript", tree_sitter_javascript},
    {"c",      tree_sitter_c},
    {NULL,     NULL}
};

/* 解析函数 */
static PyObject *parse_source(PyObject *self, PyObject *args) {
    const char *lang_name;
    const char *source_str;
    Py_ssize_t source_len;

    if (!PyArg_ParseTuple(args, "ss#", &lang_name, &source_str, &source_len)) {
        return NULL;
    }

    /* 查找语言 */
    TSLanguage *(*lang_fn)(void) = NULL;
    for (int i = 0; lang_entries[i].name; i++) {
        if (strcmp(lang_entries[i].name, lang_name) == 0) {
            lang_fn = lang_entries[i].language;
            break;
        }
    }
    if (!lang_fn) {
        PyErr_SetString(PyExc_ValueError, "Unknown language");
        return NULL;
    }

    TSParser *parser = ts_parser_new();
    TSLanguage *lang = lang_fn();
    ts_parser_set_language(parser, lang);

    TSTree *tree = ts_parser_parse_string(parser, NULL, (const uint8_t *)source_str, source_len);
    if (!tree) {
        ts_parser_delete(parser);
        Py_RETURN_NONE;
    }

    /* 转换为 Python 字典（简化表示） */
    TSNode root = ts_tree_root_node(tree);
    PyObject *result = PyDict_New();
    PyDict_SetItemString(result, "type", PyUnicode_FromString(root.type));
    PyDict_SetItemString(result, "child_count", PyLong_FromSize_t(ts_node_child_count(root)));

    ts_tree_delete(tree);
    ts_parser_delete(parser);
    return result;
}

/* 模块方法表 */
static PyMethodDef MathaTSMethods[] = {
    {"parse", parse_source, METH_VARARGS, "Parse source code with tree-sitter."},
    {NULL, NULL, 0, NULL}
};

/* 模块定义 */
static struct PyModuleDef matha_tsmodule = {
    PyModuleDef_HEAD_INIT,
    "matha_auth._tree_sitter_ext",
    NULL,
    -1,
    MathaTSMethods
};

PyMODINIT_FUNC PyInit__tree_sitter_ext(void) {
    return PyModule_Create(&matha_tsmodule);
}
