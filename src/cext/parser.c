/*
 * matha-treesitter C 扩展 — 高性能树形解析器后端
 *
 * 提供 Rust/Go/JavaScript/C 的 tree-sitter C 绑定。
 * 自动 fallback 到纯 Python 解析器（当 C 扩展不可用时）。
 *
 * 构建依赖:
 *   - tree-sitter >= 0.23.0
 *   - tree-sitter-rust >= 0.21.0
 *   - tree-sitter-go >= 0.23.0
 *   - tree-sitter-javascript >= 0.21.0
 *   - tree-sitter-c >= 0.21.0
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* tree-sitter API */
#include <tree_sitter/api.h>

/* 语言注册表 */
typedef struct {
    const char *name;
    TSLanguage *(*language)(void);
} LangEntry;

/* 语言实现（由 tree-sitter 各语言包提供） */
extern TSLanguage *tree_sitter_rust(void);
extern TSLanguage *tree_sitter_go(void);
extern TSLanguage *tree_sitter_javascript(void);
extern TSLanguage *tree_sitter_c(void);

static LangEntry lang_entries[] = {
    {"rust",       tree_sitter_rust},
    {"go",         tree_sitter_go},
    {"javascript", tree_sitter_javascript},
    {"c",          tree_sitter_c},
    {NULL,         NULL}
};

/* ── 节点遍历 ─────────────────────────────────────────────────────────────── */

typedef struct {
    PyObject_HEAD
    char *type;
    char *value;
    PyObject *children;
    PyObject *fields;
} CSTNode;

static void
cst_node_dealloc(CSTNode *self) {
    Py_XDECREF(self->children);
    Py_XDECREF(self->fields);
    PyMem_Free(self->type);
    PyMem_Free(self->value);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
cst_node_new(TSNode node, TSTree *tree) {
    CSTNode *obj = (CSTNode *)PyType_GenericAlloc(&CSTNode_Type, 0);
    if (!obj) return NULL;

    obj->type = strdup(node.type);
    obj->value = strdup(ts_node_string(node));
    obj->children = PyList_New(0);
    obj->fields = PyDict_New();

    if (!obj->type || !obj->value || !obj->children || !obj->fields) {
        Py_DECREF(obj);
        return NULL;
    }

    /* 递归添加子节点 */
    uint32_t child_count = ts_node_child_count(node);
    for (uint32_t i = 0; i < child_count; i++) {
        TSNode child = ts_node_child(node, i);
        PyObject *child_obj = cst_node_new(child, tree);
        if (child_obj) {
            PyList_Append(obj->children, child_obj);
            Py_DECREF(child_obj);
        }
    }

    /* 添加命名字段 */
    uint32_t field_count;
    TSNode *field_nodes = ts_node_named_children(node, &field_count);
    for (uint32_t i = 0; i < field_count; i++) {
        const char *field_name = ts_node_field_name_for_child(node, i);
        if (field_name) {
            PyObject *field_obj = cst_node_new(field_nodes[i], tree);
            if (field_obj) {
                PyDict_SetItemString(obj->fields, field_name, field_obj);
                Py_DECREF(field_obj);
            }
        }
    }
    if (field_nodes) free(field_nodes);

    return (PyObject *)obj;
}

/* ── 解析函数 ─────────────────────────────────────────────────────────────── */

static PyObject *
parse_source(PyObject *self, PyObject *args) {
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

    /* 创建解析器并解析 */
    TSParser *parser = ts_parser_new();
    ts_parser_set_language(parser, lang_fn());

    TSTree *tree = ts_parser_parse_string(parser, NULL,
                                          (const uint8_t *)source_str,
                                          (uint32_t)source_len);
    if (!tree) {
        ts_parser_delete(parser);
        Py_RETURN_NONE;
    }

    TSNode root = ts_tree_root_node(tree);
    PyObject *result = cst_node_new(root, tree);

    ts_tree_delete(tree);
    ts_parser_delete(parser);

    return result;
}

/* ── 模块方法表 ───────────────────────────────────────────────────────────── */

static PyMethodDef MathaTSMethods[] = {
    {"parse", parse_source, METH_VARARGS,
     "Parse source code with tree-sitter.\n\n"
     "Args:\n"
     "    language (str): 'rust', 'go', 'javascript', or 'c'\n"
     "    source (str): Source code to parse\n"
     "Returns:\n"
     "    CSTNode: Root AST node\n"},
    {NULL, NULL, 0, NULL}
};

/* ── 模块定义 ─────────────────────────────────────────────────────────────── */

static struct PyModuleDef matha_tsmodule = {
    PyModuleDef_HEAD_INIT,
    "matha_treesitter._cext",
    "Tree-sitter C extension for matha-treesitter.",
    -1,
    MathaTSMethods
};

PyMODINIT_FUNC
PyInit__cext(void) {
    PyObject *m;

    /* 初始化 CSTNode 类型 */
    CSTNode_Type.ob_base.ob_size = 0;
    CSTNode_Type.tp_name = "matha_treesitter._cext.CSTNode";
    CSTNode_Type.tp_basicsize = sizeof(CSTNode);
    CSTNode_Type.tp_itemsize = 0;
    CSTNode_Type.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE;
    CSTNode_Type.tp_dealloc = (destructor)cst_node_dealloc;
    CSTNode_Type.tp_weaklistoffset = offsetof(CSTNode, ob_weakreflist);
    CSTNode_Type.tp_methods = NULL;
    CSTNode_Type.tp_getset = NULL;
    CSTNode_Type.tp_base = NULL;
    CSTNode_Type.tp_dict = NULL;
    CSTNode_Type.tp_descr_get = NULL;
    CSTNode_Type.tp_descr_set = NULL;
    CSTNode_Type.tp_init = NULL;
    CSTNode_Type.tp_alloc = PyType_GenericAlloc;
    CSTNode_Type.tp_new = PyType_GenericNew;
    CSTNode_Type.tp_free = PyType_GenericFree;
    CSTNode_Type.tp_is_gc = NULL;
    CSTNode_Type.tp_bases = NULL;
    CSTNode_Type.tp_mro = NULL;
    CSTNode_Type.tp_cache = NULL;
    CSTNode_Type.tp_subclasses = NULL;
    CSTNode_Type.tp_weaklist = NULL;
    CSTNode_Type.tp_del = NULL;
    CSTNode_Type.tp_version_tag = 0;
    CSTNode_Type.tp_finalize = NULL;

    if (PyType_Ready(&CSTNode_Type) < 0)
        return NULL;

    m = PyModule_Create(&matha_tsmodule);
    if (m == NULL)
        return NULL;

    Py_INCREF(&CSTNode_Type);
    if (PyModule_AddObject(m, "CSTNode", (PyObject *)&CSTNode_Type) < 0) {
        Py_DECREF(&CSTNode_Type);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
