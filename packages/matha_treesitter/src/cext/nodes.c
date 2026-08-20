/*
 * 节点辅助函数 — matha-treesitter C 扩展
 */
#include <Python.h>
#include <tree_sitter/api.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* CSTNode 类型声明（在 parser.c 中定义） */
extern PyTypeObject CSTNode_Type;

/* 将 TSNode 转换为 Python 字符串 */
char *ts_node_string(TSNode node) {
    TSStringEncoder *encoder = ts_string_encoder_new();
    TSTree *tree = ts_node_tree(node);
    uint32_t len = ts_node_end_byte(node) - ts_node_start_byte(node);
    char *buf = (char *)malloc(len + 1);
    if (buf) {
        ts_string_encoder_encode(encoder, tree, node,
                                 (uint8_t *)buf, len + 1);
    }
    ts_string_encoder_delete(encoder);
    return buf;
}
