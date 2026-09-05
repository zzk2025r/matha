/*
 * ============================================================
 * Matha C 原生前端（C → Matha IR）
 * ============================================================
 * 编译：gcc -o matha_c_frontend.exe frontend.c
 * 使用：./matha_c_frontend "int foo(int x) { return x + 1; }"
 * 输出 JSON
 * ============================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#define MAX_TOKENS 4096
#define MAX_STRING 8192

typedef struct {
    char type[32];
    char value[256];
} Token;

typedef struct {
    char name[128];
    char ret_type[32];
    char params[512];
    char body[MAX_STRING];
} FuncDef;

typedef struct {
    char language[32];
    char source[MAX_STRING];
    FuncDef functions[256];
    int func_count;
    char errors[10][256];
    int error_count;
} CompileResult;

/* 类型映射 */
const char* c_type_to_matha(const char* ty) {
    if (strcmp(ty, "int") == 0 || strcmp(ty, "long") == 0 ||
        strcmp(ty, "short") == 0 || strcmp(ty, "char") == 0 ||
        strcmp(ty, "unsigned") == 0) return "Int";
    if (strcmp(ty, "float") == 0 || strcmp(ty, "double") == 0) return "Float";
    if (strcmp(ty, "bool") == 0 || strcmp(ty, "_Bool") == 0) return "Bool";
    if (strcmp(ty, "string") == 0 || strcmp(ty, "char*") == 0) return "String";
    return "Any";
}

/* Token 化 */
int tokenize(const char* source, Token tokens[]) {
    int count = 0;
    const char* p = source;
    while (*p && count < MAX_TOKENS) {
        while (*p && isspace(*p)) p++;
        if (!*p) break;

        if (isdigit(*p) || (*p == '.' && isdigit(*(p+1)))) {
            strcpy(tokens[count].type, "literal");
            int i = 0;
            while (*p && (isdigit(*p) || *p == '.')) tokens[count].value[i++] = *p++;
            tokens[count].value[i] = '\0';
            count++;
        } else if (*p == '"') {
            p++;
            int i = 0;
            while (*p && *p != '"') {
                if (*p == '\\' && *(p+1)) { i++; p++; }
                tokens[count].value[i++] = *p++;
            }
            tokens[count].value[i] = '\0';
            strcpy(tokens[count].type, "string");
            count++;
            if (*p) p++;
        } else if (isalpha(*p) || *p == '_') {
            int i = 0;
            while (*p && (isalnum(*p) || *p == '_')) tokens[count].value[i++] = *p++;
            tokens[count].value[i] = '\0';
            strcpy(tokens[count].type, "ident");
            count++;
        } else {
            char buf[4] = {0};
            buf[0] = *p++;
            if (*p == '=' && buf[0] == '=') { buf[1] = '='; p++; }
            else if (*p == '=' && buf[0] == '!') { buf[1] = '='; p++; }
            else if (*p == '>' && buf[0] == '-') { buf[1] = '>'; p++; }
            else if (*p == '>' && buf[0] == '<') { buf[1] = '>'; p++; }
            strcpy(tokens[count].type, "symbol");
            strcpy(tokens[count].value, buf);
            count++;
        }
    }
    return count;
}

/* escape JSON 字符串 */
void escape_json(char* out, int out_size, const char* s) {
    int j = 0;
    if (j >= out_size - 1) return;
    out[j++] = '"';
    for (int i = 0; s[i] && j < out_size - 2; i++) {
        if (s[i] == '"') { if (j+2 >= out_size) break; out[j++] = '\\'; out[j++] = '"'; }
        else if (s[i] == '\\') { if (j+2 >= out_size) break; out[j++] = '\\'; out[j++] = '\\'; }
        else if (s[i] == '\n') { if (j+2 >= out_size) break; out[j++] = '\\'; out[j++] = 'n'; }
        else if (s[i] == '\r') { if (j+2 >= out_size) break; out[j++] = '\\'; out[j++] = 'r'; }
        else if (s[i] == '\t') { if (j+2 >= out_size) break; out[j++] = '\\'; out[j++] = 't'; }
        else { out[j++] = s[i]; }
    }
    if (j >= out_size - 1) return;
    out[j++] = '"';
    out[j] = '\0';
}

/* 主编译（堆分配避免栈溢出） */
CompileResult* compile(const char* source) {
    CompileResult* result = (CompileResult*)malloc(sizeof(CompileResult));
    if (!result) return NULL;
    memset(result, 0, sizeof(*result));
    strncpy(result->language, "c", sizeof(result->language)-1);
    strncpy(result->source, source, sizeof(result->source)-1);

    Token tokens[MAX_TOKENS];
    int count = tokenize(source, tokens);

    int pos = 0;
    while (pos < count && result->func_count < 256) {
        // C函数模式: type name(params) { body }
        // 找到 ident 后跟着 ident( 或 ident) 的情况
        if (pos + 1 < count &&
            strcmp(tokens[pos].type, "ident") == 0 &&
            strcmp(tokens[pos+1].type, "ident") == 0 &&
            pos + 2 < count &&
            strcmp(tokens[pos+2].value, "(") == 0) {

            FuncDef func;
            memset(&func, 0, sizeof(func));
            strncpy(func.ret_type, tokens[pos].value, sizeof(func.ret_type)-1);
            strncpy(func.name, tokens[pos+1].value, sizeof(func.name)-1);
            pos += 3; // skip ret_type, name, (

            /* skip opening ( if still there */
            if (pos < count && strcmp(tokens[pos].value, "(") == 0) pos++;

            /* parse params until ) */
            while (pos < count && strcmp(tokens[pos].value, ")") != 0) {
                if (tokens[pos].value[0] != '\0' && strcmp(tokens[pos].value, "{") != 0) {
                    if (func.params[0] != '\0') strcat(func.params, ", ");
                    strcat(func.params, tokens[pos].value);
                }
                pos++;
            }
            if (pos < count) pos++; /* skip ) */

            /* parse body until } */
            if (pos < count && strcmp(tokens[pos].value, "{") == 0) {
                pos++;
                int body_len = 0;
                while (pos < count && strcmp(tokens[pos].value, "}") != 0 && body_len < 800) {
                    if (tokens[pos].value[0] != '\0') {
                        if (body_len > 0) strcat(func.body, " ");
                        strcat(func.body, tokens[pos].value);
                        body_len++;
                    }
                    pos++;
                }
                if (pos < count) pos++;

                strncpy(result->functions[result->func_count].name, func.name, 127);
                strncpy(result->functions[result->func_count].ret_type,
                        c_type_to_matha(func.ret_type), 31);
                strncpy(result->functions[result->func_count].params, func.params, 511);
                strncpy(result->functions[result->func_count].body, func.body, 8191);
                result->func_count++;
            }
        } else {
            pos++;
        }
    }
    return result;
}

/* JSON 输出 */
void print_json(const CompileResult* r) {
    char buf[4096];
    printf("{\n");
    printf("  \"language\": \"c\",\n");
    escape_json(buf, sizeof(buf), r->source);
    printf("  \"source\": %s,\n", buf);
    printf("  \"functions\": {\n");
    for (int i = 0; i < r->func_count; i++) {
        escape_json(buf, sizeof(buf), r->functions[i].name);
        printf("    %s: {\n", buf);
        escape_json(buf, sizeof(buf), r->functions[i].ret_type);
        printf("      \"return_type\": %s,\n", buf);
        escape_json(buf, sizeof(buf), r->functions[i].params);
        printf("      \"params\": %s,\n", buf);
        escape_json(buf, sizeof(buf), r->functions[i].body);
        printf("      \"body\": %s\n", buf);
        printf("    }%s\n", i < r->func_count - 1 ? "," : "");
    }
    printf("  },\n");
    printf("  \"errors\": []\n");
    printf("}\n");
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: matha_c_frontend <source.c>\n");
        return 1;
    }
    CompileResult* result = compile(argv[1]);
    if (!result) {
        fprintf(stderr, "Memory allocation failed\n");
        return 1;
    }
    print_json(result);
    free(result);
    return 0;
}
