"""
CppGenerator：把 Matha MIR 编译为 C++17 代码（CMake/可直接 g++ 编译）。
支持：函数、算术、控制流、向量/矩阵（Eigen/xtensor）、线程/通道。
"""

from __future__ import annotations

from src.codegen.base import CodegenResult, Generator
from src.mir import MIRFunction, MIRInstrType, MIRProgram


class CppGenerator(Generator):
    """C++ 代码生成器：MIRProgram → .cpp/.h/CMakeLists.txt。"""

    def __init__(self, mir_program: MIRProgram, out_dir: str):
        self.mir = mir_program
        self.out_dir = out_dir
        class DummyApp:
            kind = "C++程序"
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
            # 头文件
            h_content = self._build_header()
            files.append(self._write(f"{self.app.name}.h", h_content))

            # 源文件
            cpp_content = self._build_source()
            files.append(self._write(f"{self.app.name}.cpp", cpp_content))

            # CMakeLists.txt
            cmake_content = self._build_cmake()
            files.append(self._write("CMakeLists.txt", cmake_content))

        except Exception as e:
            return CodegenResult(成功=False, 类型="C++程序", 名称=self.app.name, 错误=str(e))

        return CodegenResult(
            成功=True, 类型="C++程序", 名称=self.app.name,
            文件=files, 入口=f"{self.app.name}.cpp",
        )

    def _build_header(self) -> str:
        guard = f"{self.app.name.upper()}_H"
        lines = [
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            "#include <vector>",
            "#include <array>",
            "#include <memory>",
            "#include <thread>",
            "#include <mutex>",
            "#include <condition_variable>",
            "#include <queue>",
            "#include <functional>",
            "#include <cmath>",
            "",
            "// ===== 向量/矩阵运算 =====",
            "",
            "namespace matha {",
            "",
            "using Vec = std::vector<double>;",
            "",
            "inline Vec vec_zeros(size_t n) {",
            "    return Vec(n, 0.0);",
            "}",
            "",
            "inline Vec vec_from(const std::initializer_list<double>& lst) {",
            "    return Vec(lst);",
            "}",
            "",
            "inline Vec vec_add(const Vec& a, const Vec& b) {",
            "    Vec r(a.size());",
            "    for (size_t i = 0; i < a.size(); ++i) r[i] = a[i] + b[i];",
            "    return r;",
            "}",
            "",
            "inline Vec vec_sub(const Vec& a, const Vec& b) {",
            "    Vec r(a.size());",
            "    for (size_t i = 0; i < a.size(); ++i) r[i] = a[i] - b[i];",
            "    return r;",
            "}",
            "",
            "inline Vec vec_mul(const Vec& a, const Vec& b) {",
            "    Vec r(a.size());",
            "    for (size_t i = 0; i < a.size(); ++i) r[i] = a[i] * b[i];",
            "    return r;",
            "}",
            "",
            "inline Vec vec_div(const Vec& a, const Vec& b) {",
            "    Vec r(a.size());",
            "    for (size_t i = 0; i < a.size(); ++i) r[i] = (b[i] != 0) ? a[i] / b[i] : 0;",
            "    return r;",
            "}",
            "",
            "inline double vec_dot(const Vec& a, const Vec& b) {",
            "    double sum = 0;",
            "    for (size_t i = 0; i < a.size(); ++i) sum += a[i] * b[i];",
            "    return sum;",
            "}",
            "",
            "inline double vec_reduce_sum(const Vec& v) {",
            "    double sum = 0; for (double x : v) sum += x; return sum;",
            "}",
            "inline double vec_reduce_max(const Vec& v) {",
            "    return *std::max_element(v.begin(), v.end());",
            "}",
            "inline double vec_reduce_min(const Vec& v) {",
            "    return *std::min_element(v.begin(), v.end());",
            "}",
            "inline double vec_reduce_mean(const Vec& v) {",
            "    return vec_reduce_sum(v) / v.size();",
            "}",
            "",
            "// 矩阵类型 (使用 std::vector<std::vector<double>> 简化版)",
            "using Mat = std::vector<std::vector<double>>;",
            "",
            "inline Mat mat_zeros(size_t rows, size_t cols) {",
            "    return Mat(rows, std::vector<double>(cols, 0.0));",
            "}",
            "",
            "inline Mat mat_mul(const Mat& a, const Mat& b) {",
            "    size_t rows = a.size(), cols = b[0].size(), k = a[0].size();",
            "    Mat r = mat_zeros(rows, cols);",
            "    for (size_t i = 0; i < rows; ++i) {",
            "        for (size_t j = 0; j < cols; ++j) {",
            "            double sum = 0;",
            "            for (size_t k = 0; k < k; ++k) sum += a[i][k] * b[k][j];",
            "            r[i][j] = sum;",
            "        }",
            "    }",
            "    return r;",
            "}",
            "",
            "inline Mat mat_transpose(const Mat& m) {",
            "    size_t rows = m.size(), cols = m[0].size();",
            "    Mat r = mat_zeros(cols, rows);",
            "    for (size_t i = 0; i < rows; ++i) {",
            "        for (size_t j = 0; j < cols; ++j) r[j][i] = m[i][j];",
            "    }",
            "    return r;",
            "}",
            "",
            "// ===== 并发通道 =====",
            "",
            "template<typename T>",
            "class Channel {",
            "    std::queue<T> q;",
            "    std::mutex mtx;",
            "    std::condition_variable cv;",
            "    bool closed = false;",
            "public:",
            "    void send(T value) {",
            "        std::unique_lock<std::mutex> lock(mtx);",
            "        q.push(std::move(value));",
            "        cv.notify_one();",
            "    }",
            "    bool recv(T& value) {",
            "        std::unique_lock<std::mutex> lock(mtx);",
            "        cv.wait(lock, [this]{ return !q.empty(); });",
            "        if (q.empty()) return false;",
            "        value = std::move(q.front());",
            "        q.pop();",
            "        return true;",
            "    }",
            "    void close() {",
            "        std::lock_guard<std::mutex> lock(mtx);",
            "        // 标记关闭，实际可扩展",
            "    }",
            "};",
            "",
            "template<typename T>",
            "std::shared_ptr<Channel<T>> make_channel() {",
            "    return std::make_shared<Channel<T>>();",
            "}",
            "",
            "// ===== 同步原语 =====",
            "",
            "class Mutex {",
            "    std::mutex mtx;",
            "public:",
            "    void lock() { mtx.lock(); }",
            "    void unlock() { mtx.unlock(); }",
            "    std::unique_lock<std::mutex> lock() { return std::unique_lock<std::mutex>(mtx); }",
            "};",
            "",
            "// ===== 工具函数 =====",
            "",
            "inline std::vector<double> vec_zeros(size_t n) {",
            "    return std::vector<double>(n, 0.0);",
            "}",
            "",
            "} // namespace matha",
            "",
            f"#endif // {guard}",
            "",
        ]
        return "\n".join(lines)

    def _build_source(self) -> str:
        lines = [
            f'#include "{self.app.name}.h"',
            "#include <iostream>",
            "#include <thread>",
            "#include <future>",
            "",
            "using namespace matha;",
            "",
        ]

        for func_name, func in self.mir.functions.items():
            if func_name == "main":
                lines.append("int main() {")
            else:
                params = ", ".join(f"double {p}" for p in func.params)
                lines.append(f"double {func_name}({params}) {{")

            for instr in func.instructions:
                lines.append(f"    // {instr.instr_type.name if hasattr(instr, 'instr_type') else 'instr'}")
                if hasattr(instr, 'result') and instr.result:
                    if instr.instr_type == MIRInstrType.VLOAD:
                        lines.append(f"    auto {instr.result} = vec_zeros({instr.metadata.get('len', '0')});")
                    elif instr.instr_type in (MIRInstrType.VADD, MIRInstrType.VSUB, MIRInstrType.VMUL, MIRInstrType.VDIV):
                        op_map = {MIRInstrType.VADD: "vec_add", MIRInstrType.VSUB: "vec_sub",
                                 MIRInstrType.VMUL: "vec_mul", MIRInstrType.VDIV: "vec_div"}
                        op = op_map.get(instr.instr_type, "vec_add")
                        lines.append(f"    auto {instr.result} = {op}({instr.operands[0]}, {instr.operands[1]});")
                    elif instr.instr_type == MIRInstrType.VDOT:
                        lines.append(f"    double {instr.result} = vec_dot({instr.operands[0]}, {instr.operands[1]});")
                    elif instr.instr_type == MIRInstrType.VMATMUL:
                        lines.append(f"    auto {instr.result} = mat_mul({instr.operands[0]}, {instr.operands[1]});")
                    elif instr.instr_type in (MIRInstrType.VREDUCE_SUM, MIRInstrType.VREDUCE_MAX,
                                             MIRInstrType.VREDUCE_MIN, MIRInstrType.VREDUCE_MEAN):
                        op_map = {MIRInstrType.VREDUCE_SUM: "vec_reduce_sum",
                                 MIRInstrType.VREDUCE_MAX: "vec_reduce_max",
                                 MIRInstrType.VREDUCE_MIN: "vec_reduce_min",
                                 MIRInstrType.VREDUCE_MEAN: "vec_reduce_mean"}
                        op = op_map.get(instr.instr_type, "vec_reduce_sum")
                        lines.append(f"    double {instr.result} = {op}({instr.operands[0]});")
                    elif instr.instr_type == MIRInstrType.ADD:
                        lines.append(f"    double {instr.result} = {instr.operands[0]} + {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.SUB:
                        lines.append(f"    double {instr.result} = {instr.operands[0]} - {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.MUL:
                        lines.append(f"    double {instr.result} = {instr.operands[0]} * {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.DIV:
                        lines.append(f"    double {instr.result} = {instr.operands[0]} / {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.RETURN:
                        if func_name == "main":
                            lines.append("    return 0;")
                        else:
                            lines.append(f"    return {instr.value or 0.0};")
                    elif instr.instr_type == MIRInstrType.CALL:
                        args = ", ".join(instr.operands)
                        lines.append(f"    auto {instr.result} = {instr.metadata.get('func_name', 'unknown')}({args});")
                    elif instr.instr_type == MIRInstrType.SPAWN:
                        func = instr.metadata.get('func_name', 'unknown')
                        lines.append(f"    std::thread([=]() {{ {func}(); }}).detach();")
                    elif instr.instr_type == MIRInstrType.SEND:
                        ch = instr.metadata.get('channel')
                        lines.append(f"    {ch}->send({instr.operands[0] if instr.operands else 0});")
                    elif instr.instr_type == MIRInstrType.RECV:
                        ch = instr.metadata.get('channel')
                        lines.append(f"    double {instr.result}; {ch}->recv({instr.result});")
                    elif instr.instr_type == MIRInstrType.CHANNEL_CREATE:
                        lines.append(f"    auto {instr.result} = make_channel<double>();")
                    elif instr.instr_type == MIRInstrType.MUTEX_LOCK:
                        lines.append(f"    {instr.metadata.get('mutex')}.lock();")
                    elif instr.instr_type == MIRInstrType.MUTEX_UNLOCK:
                        lines.append(f"    {instr.metadata.get('mutex')}.unlock();")

            lines.append("}")
            lines.append("")

        # main 函数入口
        if "main" in self.mir.functions:
            lines.append("// 程序入口")
            lines.append("int main() {")
            lines.append("    // 初始化")
            lines.append("    return 0;")
            lines.append("}")

        return "\n".join(lines)

    def _build_cmake(self) -> str:
        return (
            f"cmake_minimum_required(VERSION 3.10)\n"
            f"project({self.app.name} LANGUAGES CXX)\n"
            f"\n"
            f"set(CMAKE_CXX_STANDARD 17)\n"
            f"set(CMAKE_CXX_STANDARD_REQUIRED ON)\n"
            f"set(CMAKE_CXX_EXTENSIONS OFF)\n"
            f"\n"
            f"add_executable({self.app.name} {self.app.name}.cpp)\n"
            f"target_compile_options({self.app.name} PRIVATE -Wall -Wextra -O2)\n"
        )


# 便捷函数
def generate_cpp(mir_program: MIRProgram, out_dir: str) -> CodegenResult:
    gen = CppGenerator(mir_program, out_dir)
    return gen.generate()
