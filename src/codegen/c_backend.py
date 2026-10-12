"""
CGenerator：把 Matha MIR 编译为 C 代码（可 GCC/Clang 编译）。
支持：函数、算术、控制流、向量、内存管理。
"""

from __future__ import annotations

from src.codegen.base import CodegenResult, Generator
from src.mir import MIRFunction, MIRInstrType, MIRProgram


class CGenerator(Generator):
    """C 代码生成器：MIRProgram → .c/.h 文件。"""

    def __init__(self, mir_program: MIRProgram, out_dir: str):
        # 兼容基类接口
        self.mir = mir_program
        self.out_dir = out_dir
        # 创建一个虚拟 AppSpec 兼容基类
        class DummyApp:
            kind = "C程序"
            name = mir_program.functions.get("main", MIRFunction(name="main")).name
            title = name
            elements = []
            styles = []
            scripts = []
            meta = {}
        self.app = DummyApp()

    def generate(self) -> CodegenResult:
        files = []
        try:
            # 生成头文件
            h_content = self._build_header()
            files.append(self._write(f"{self.app.name}.h", h_content))

            # 生成源文件
            c_content = self._build_source()
            files.append(self._write(f"{self.app.name}.c", c_content))

            # 生成 CMakeLists.txt
            cmake_content = self._build_cmake()
            files.append(self._write("CMakeLists.txt", cmake_content))

        except Exception as e:
            return CodegenResult(成功=False, 类型="C程序", 名称=self.app.name, 错误=str(e))

        return CodegenResult(
            成功=True, 类型="C程序", 名称=self.app.name,
            文件=files, 入口=f"{self.app.name}.c",
        )

    def _build_header(self) -> str:
        guard = f"{self.app.name.upper()}_H"
        lines = [
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            "#include <stddef.h>",
            "#include <stdint.h>",
            "#include <stdbool.h>",
            "#include <math.h>",
            "",
            "// 向量/矩阵类型",
            "typedef struct {",
            "    size_t len;",
            "    double* data;",
            "} Vec;",
            "",
            "typedef struct {",
            "    size_t rows, cols;",
            "    double* data;",
            "} Mat;",
            "",
            "// 内存管理",
            "void* matha_alloc(size_t size);",
            "void matha_free(void* ptr);",
            "void* matha_memcpy(void* dest, const void* src, size_t n);",
            "void* matha_memset(void* ptr, int value, size_t n);",
            "",
            "// 向量运算",
            "Vec vec_new(size_t len);",
            "void vec_free(Vec* v);",
            "Vec vec_add(const Vec* a, const Vec* b);",
            "Vec vec_sub(const Vec* a, const Vec* b);",
            "Vec vec_mul(const Vec* a, const Vec* b);",
            "Vec vec_div(const Vec* a, const Vec* b);",
            "double vec_dot(const Vec* a, const Vec* b);",
            "double vec_reduce_sum(const Vec* v);",
            "double vec_reduce_max(const Vec* v);",
            "double vec_reduce_min(const Vec* v);",
            "double vec_reduce_mean(const Vec* v);",
            "",
            "// 矩阵运算",
            "Mat mat_new(size_t rows, size_t cols);",
            "void mat_free(Mat* m);",
            "Mat mat_mul(const Mat* a, const Mat* b);",
            "Mat mat_transpose(const Mat* m);",
            "",
            "// 函数声明",
        ]

        for func_name, func in self.mir.functions.items():
            if func_name == "main":
                lines.append("int main(void);")
            else:
                params = ", ".join(f"double {p}" for p in func.params)
                lines.append(f"double {func_name}({params});")

        lines.extend(["", f"#endif // {guard}", ""])
        return "\n".join(lines)

    def _build_source(self) -> str:
        lines = [
            f'#include "{self.app.name}.h"',
            '#include <stdlib.h>',
            '#include <string.h>',
            '#include <stdio.h>',
            '#include <math.h>',
            "",
            "// 内存管理",
            "void* matha_alloc(size_t size) {",
            "    return malloc(size);",
            "}",
            "",
            "void matha_free(void* ptr) {",
            "    free(ptr);",
            "}",
            "",
            "void* matha_memcpy(void* dest, const void* src, size_t n) {",
            "    return memcpy(dest, src, n);",
            "}",
            "",
            "void* matha_memset(void* ptr, int value, size_t n) {",
            "    return memset(ptr, value, n);",
            "}",
            "",
            "// 向量运算",
            "Vec vec_new(size_t len) {",
            "    Vec v = {len, (double*)matha_alloc(len * sizeof(double))};",
            "    return v;",
            "}",
            "",
            "void vec_free(Vec* v) {",
            "    if (v && v->data) { matha_free(v->data); v->data = NULL; v->len = 0; }",
            "}",
            "",
            "Vec vec_add(const Vec* a, const Vec* b) {",
            "    Vec r = vec_new(a->len);",
            "    for (size_t i = 0; i < a->len; ++i) r.data[i] = a->data[i] + b->data[i];",
            "    return r;",
            "}",
            "",
            "Vec vec_sub(const Vec* a, const Vec* b) {",
            "    Vec r = vec_new(a->len);",
            "    for (size_t i = 0; i < a->len; ++i) r.data[i] = a->data[i] - b->data[i];",
            "    return r;",
            "}",
            "",
            "Vec vec_mul(const Vec* a, const Vec* b) {",
            "    Vec r = vec_new(a->len);",
            "    for (size_t i = 0; i < a->len; ++i) r.data[i] = a->data[i] * b->data[i];",
            "    return r;",
            "}",
            "",
            "Vec vec_div(const Vec* a, const Vec* b) {",
            "    Vec r = vec_new(a->len);",
            "    for (size_t i = 0; i < a->len; ++i) r.data[i] = b->data[i] != 0 ? a->data[i] / b->data[i] : 0.0;",
            "    return r;",
            "}",
            "",
            "double vec_dot(const Vec* a, const Vec* b) {",
            "    double sum = 0.0;",
            "    for (size_t i = 0; i < a->len; ++i) sum += a->data[i] * b->data[i];",
            "    return sum;",
            "}",
            "",
            "double vec_reduce_sum(const Vec* v) {",
            "    double sum = 0.0; for (size_t i = 0; i < v->len; ++i) sum += v->data[i]; return sum;",
            "}",
            "double vec_reduce_max(const Vec* v) {",
            "    double m = v->data[0]; for (size_t i = 1; i < v->len; ++i) if (v->data[i] > m) m = v->data[i]; return m;",
            "}",
            "double vec_reduce_min(const Vec* v) {",
            "    double m = v->data[0]; for (size_t i = 1; i < v->len; ++i) if (v->data[i] < m) m = v->data[i]; return m;",
            "}",
            "double vec_reduce_mean(const Vec* v) {",
            "    return vec_reduce_sum(v) / v->len;",
            "}",
            "",
            "// 矩阵运算",
            "Mat mat_new(size_t rows, size_t cols) {",
            "    Mat m = {rows, cols, (double*)matha_alloc(rows * cols * sizeof(double))};",
            "    return m;",
            "}",
            "",
            "void mat_free(Mat* m) {",
            "    if (m && m->data) { matha_free(m->data); m->data = NULL; m->rows = m->cols = 0; }",
            "}",
            "",
            "Mat mat_mul(const Mat* a, const Mat* b) {",
            "    if (a->cols != b->rows) return (Mat){0,0,NULL};",
            "    Mat r = mat_new(a->rows, b->cols);",
            "    for (size_t i = 0; i < a->rows; ++i) {",
            "        for (size_t j = 0; j < b->cols; ++j) {",
            "            double sum = 0;",
            "            for (size_t k = 0; k < a->cols; ++k) {",
            "                sum += a->data[i * a->cols + k] * b->data[k * b->cols + j];",
            "            }",
            "            r.data[i * r.cols + j] = sum;",
            "        }",
            "    }",
            "    return r;",
            "}",
            "",
            "Mat mat_transpose(const Mat* m) {",
            "    Mat r = mat_new(m->cols, m->rows);",
            "    for (size_t i = 0; i < m->rows; ++i) {",
            "        for (size_t j = 0; j < m->cols; ++j) {",
            "            r.data[j * r.cols + i] = m->data[i * m->cols + j];",
            "        }",
            "    }",
            "    return r;",
            "}",
            "",
        ]

        # 函数体
        for func_name, func in self.mir.functions.items():
            if func_name == "main":
                lines.append("int main(void) {")
            else:
                params = ", ".join(f"double {p}" for p in func.params)
                lines.append(f"double {func_name}({params}) {{")

            # 简单的指令翻译
            for instr in func.instructions:
                lines.append(f"    // {instr.instr_type.name if hasattr(instr, 'instr_type') else 'instr'}")
                if hasattr(instr, 'result') and instr.result:
                    if instr.instr_type == MIRInstrType.VLOAD:
                        lines.append(f"    Vec {instr.result} = vec_new({instr.metadata.get('len', '0')});")
                    elif instr.instr_type == MIRInstrType.VSTORE:
                        lines.append(f"    // vstore {instr.operands[0]} to {instr.metadata.get('target')}")
                    elif instr.instr_type in (MIRInstrType.VADD, MIRInstrType.VSUB, MIRInstrType.VMUL, MIRInstrType.VDIV):
                        op_map = {MIRInstrType.VADD: "vec_add", MIRInstrType.VSUB: "vec_sub",
                                 MIRInstrType.VMUL: "vec_mul", MIRInstrType.VDIV: "vec_div"}
                        op = op_map.get(instr.instr_type, "vec_add")
                        lines.append(f"    Vec {instr.result} = {op}(&{instr.operands[0]}, &{instr.operands[1]});")
                    elif instr.instr_type == MIRInstrType.VDOT:
                        lines.append(f"    double {instr.result} = vec_dot(&{instr.operands[0]}, &{instr.operands[1]});")
                    elif instr.instr_type == MIRInstrType.VMATMUL:
                        lines.append(f"    Mat {instr.result} = mat_mul(&{instr.operands[0]}, &{instr.operands[1]});")
                    elif instr.instr_type in (MIRInstrType.VREDUCE_SUM, MIRInstrType.VREDUCE_MAX,
                                             MIRInstrType.VREDUCE_MIN, MIRInstrType.VREDUCE_MEAN):
                        op_map = {MIRInstrType.VREDUCE_SUM: "vec_reduce_sum",
                                 MIRInstrType.VREDUCE_MAX: "vec_reduce_max",
                                 MIRInstrType.VREDUCE_MIN: "vec_reduce_min",
                                 MIRInstrType.VREDUCE_MEAN: "vec_reduce_mean"}
                        op = op_map.get(instr.instr_type, "vec_reduce_sum")
                        lines.append(f"    double {instr.result} = {op}(&{instr.operands[0]});")
                    elif instr.instr_type == MIRInstrType.ADD:
                        lines.append(f"    double {instr.result} = {instr.operands[0]} + {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.SUB:
                        lines.append(f"    double {instr.result} = {instr.operands[0]} - {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.MUL:
                        lines.append(f"    double {instr.result} = {instr.operands[0]} * {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.DIV:
                        lines.append(f"    double {instr.result} = {instr.operands[0]} / {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.RETURN:
                        lines.append(f"    return {instr.value or 0.0};")
                    elif instr.instr_type == MIRInstrType.CALL:
                        args = ", ".join(instr.operands)
                        lines.append(f"    double {instr.result} = {instr.metadata.get('c_func', instr.metadata.get('func_name', 'unknown'))}({args});")

            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def _build_cmake(self) -> str:
        return (
            f"cmake_minimum_required(VERSION 3.10)\n"
            f"project({self.app.name} LANGUAGES C)\n"
            f"\n"
            f"set(CMAKE_C_STANDARD 11)\n"
            f"set(CMAKE_C_STANDARD_REQUIRED ON)\n"
            f"\n"
            f"add_executable({self.app.name} {self.app.name}.c)\n"
            f"target_link_libraries({self.app.name} m)\n"
        )


# 便捷函数
def generate_c(mir_program: MIRProgram, out_dir: str) -> CodegenResult:
    gen = CGenerator(mir_program, out_dir)
    return gen.generate()
