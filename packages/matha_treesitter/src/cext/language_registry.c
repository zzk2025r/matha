/*
 * 语言注册表 — matha-treesitter C 扩展
 *
 * 包含所有支持语言的语言工厂函数。
 * 每个语言由对应的 tree-sitter-* 包提供。
 */
#include <tree_sitter/api.h>

/* 语言工厂函数声明（由各 tree-sitter-* 包提供） */
extern TSLanguage *tree_sitter_rust(void);
extern TSLanguage *tree_sitter_go(void);
extern TSLanguage *tree_sitter_javascript(void);
extern TSLanguage *tree_sitter_c(void);

/* 语言注册表（在 parser.c 中引用） */
typedef struct {
    const char *name;
    TSLanguage *(*language)(void);
} LangEntry;

LangEntry lang_entries[] = {
    {"rust",       tree_sitter_rust},
    {"go",         tree_sitter_go},
    {"javascript", tree_sitter_javascript},
    {"c",          tree_sitter_c},
    {NULL,         NULL}
};
