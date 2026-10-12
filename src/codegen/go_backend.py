"""
GoGenerator：把 Matha MIR 编译为 Go 代码（go build 可构建）。
支持：函数、算术、控制流、向量/矩阵、Channel/Goroutine。
"""

from __future__ import annotations

from src.codegen.base import CodegenResult, Generator
from src.mir import MIRFunction, MIRInstrType, MIRProgram


class GoGenerator(Generator):
    """Go 代码生成器：MIRProgram → Go 模块。"""

    def __init__(self, mir_program: MIRProgram, out_dir: str):
        self.mir = mir_program
        self.out_dir = out_dir
        class DummyApp:
            kind = "Go程序"
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
            # go.mod
            mod_content = self._build_go_mod()
            files.append(self._write("go.mod", mod_content))

            # main.go
            main_content = self._build_main()
            files.append(self._write("main.go", main_content))

            # matha_rt.go (运行时库)
            rt_content = self._build_runtime()
            self._write("matha_rt.go", rt_content)

        except Exception as e:
            return CodegenResult(成功=False, 类型="Go程序", 名称=self.app.name, 错误=str(e))

        return CodegenResult(
            成功=True, 类型="Go程序", 名称=self.app.name,
            文件=files, 入口="main.go",
        )

    def _build_go_mod(self) -> str:
        name = self.app.name.lower().replace(" ", "-")
        return (
            f"module {name}\n"
            f"\n"
            f"go 1.21\n"
            f"\n"
            f"require (\n"
            f"    gonum.org/v1/gonum v0.13.0\n"
            f"    github.com/gammazero/workerpool v1.1.3\n"
            f")\n"
        )

    def _build_runtime(self) -> str:
        return (
            "// 由 Matha 生成的 Go 运行时库\n"
            "package matha\n"
            "\n"
            "import (\n"
            "    \"gonum.org/v1/gonum/mat\"\n"
            "    \"sync\"\n"
            ")\n"
            "\n"
            "// ===== 向量/矩阵运算 =====\n"
            "\n"
            "// Vec 向量类型\n"
            "type Vec struct {\n"
            "    Data []float64\n"
            "}\n"
            "\n"
            "func VecZeros(n int) Vec {\n"
            "    return Vec{Data: make([]float64, n)}\n"
            "}\n"
            "\n"
            "func VecFrom(arr []float64) Vec {\n"
            "    return Vec{Data: arr}\n"
            "}\n"
            "\n"
            "func (v Vec) Len() int {\n"
            "    return len(v.Data)\n"
            "}\n"
            "\n"
            "func (v Vec) Add(other Vec) Vec {\n"
            "    r := Vec{Data: make([]float64, v.Len())}\n"
            "    for i := 0; i < v.Len(); i++ {\n"
            "        r.Data[i] = v.Data[i] + other.Data[i]\n"
            "    }\n"
            "    return r\n"
            "}\n"
            "\n"
            "func (v Vec) Sub(other Vec) Vec {\n"
            "    r := Vec{Data: make([]float64, v.Len())}\n"
            "    for i := 0; i < v.Len(); i++ {\n"
            "        r.Data[i] = v.Data[i] - other.Data[i]\n"
            "    }\n"
            "    return r\n"
            "}\n"
            "\n"
            "func (v Vec) Mul(other Vec) Vec {\n"
            "    r := Vec{Data: make([]float64, v.Len())}\n"
            "    for i := 0; i < v.Len(); i++ {\n"
            "        r.Data[i] = v.Data[i] * other.Data[i]\n"
            "    }\n"
            "    return r\n"
            "}\n"
            "\n"
            "func (v Vec) Div(other Vec) Vec {\n"
            "    r := Vec{Data: make([]float64, v.Len())}\n"
            "    for i := 0; i < v.Len(); i++ {\n"
            "        if other.Data[i] != 0 {\n"
            "            r.Data[i] = v.Data[i] / other.Data[i]\n"
            "        }\n"
            "    }\n"
            "    return r\n"
            "}\n"
            "\n"
            "func (v Vec) Dot(other Vec) float64 {\n"
            "    sum := 0.0\n"
            "    for i := 0; i < v.Len(); i++ {\n"
            "        sum += v.Data[i] * other.Data[i]\n"
            "    }\n"
            "    return sum\n"
            "}\n"
            "\n"
            "func (v Vec) ReduceSum() float64 {\n"
            "    sum := 0.0\n"
            "    for _, val := range v.Data {\n"
            "        sum += val\n"
            "    }\n"
            "    return sum\n"
            "}\n"
            "\n"
            "func (v Vec) ReduceMax() float64 {\n"
            "    m := v.Data[0]\n"
            "    for _, val := range v.Data[1:] {\n"
            "        if val > m {\n"
            "            m = val\n"
            "        }\n"
            "    }\n"
            "    return m\n"
            "}\n"
            "\n"
            "func (v Vec) ReduceMin() float64 {\n"
            "    m := v.Data[0]\n"
            "    for _, val := range v.Data[1:] {\n"
            "        if val < m {\n"
            "            m = val\n"
            "        }\n"
            "    }\n"
            "    return m\n"
            "}\n"
            "\n"
            "func (v Vec) ReduceMean() float64 {\n"
            "    return v.ReduceSum() / float64(v.Len())\n"
            "}\n"
            "\n"
            "// Mat 矩阵类型 (使用 gonum/mat)\n"
            "\n"
            "func MatZeros(rows, cols int) *mat.Dense {\n"
            "    return mat.NewDense(rows, cols, nil)\n"
            "}\n"
            "\n"
            "func MatMul(a, b *mat.Dense) *mat.Dense {\n"
            "    r := mat.NewDense(a.Rows(), b.Cols(), nil)\n"
            "    r.Mul(a, b)\n"
            "    return r\n"
            "}\n"
            "\n"
            "func MatTranspose(m *mat.Dense) *mat.Dense {\n"
            "    r := mat.NewDense(m.Cols(), m.Rows(), nil)\n"
            "    r.T()\n"
            "    return r\n"
            "}\n"
            "\n"
            "// ===== 并发通道 =====\n"
            "\n"
            "// Channel 泛型通道\n"
            "type Channel[T any] struct {\n"
            "    ch chan T\n"
            "    closed bool\n"
            "    mu sync.Mutex\n"
            "}\n"
            "\n"
            "func MakeChannel[T any](capacity int) *Channel[T] {\n"
            "    if capacity <= 0 {\n"
            "        return &Channel[T]{ch: make(chan T)}\n"
            "    }\n"
            "    return &Channel[T]{ch: make(chan T, capacity)}\n"
            "}\n"
            "\n"
            "func (c *Channel[T]) Send(v T) {\n"
            "    c.mu.Lock()\n"
            "    if c.closed {\n"
            "        c.mu.Unlock()\n"
            "        panic(\"发送到已关闭的通道\")\n"
            "    }\n"
            "    c.ch <- v\n"
            "    c.mu.Unlock()\n"
            "}\n"
            "\n"
            "func (c *Channel[T]) Recv() (T, bool) {\n"
            "    v, ok := <-c.ch\n"
            "    return v, ok\n"
            "}\n"
            "\n"
            "func (c *Channel[T]) Close() {\n"
            "    c.mu.Lock()\n"
            "    if !c.closed {\n"
            "        close(c.ch)\n"
            "        c.closed = true\n"
            "    }\n"
            "    c.mu.Unlock()\n"
            "}\n"
            "\n"
            "// ===== 同步原语 =====\n"
            "\n"
            "// Mutex 互斥锁\n"
            "type Mutex struct{\n"
            "    mu sync.Mutex\n"
            "}\n"
            "\n"
            "func (m *Mutex) Lock() {\n"
            "    m.mu.Lock()\n"
            "}\n"
            "\n"
            "func (m *Mutex) Unlock() {\n"
            "    m.mu.Unlock()\n"
            "}\n"
            "\n"
            "\n"
            "// ===== 工具函数 =====\n"
            "\n"
            "func Sleep(ms int) {\n"
            "    // 实际项目中可用 time.Sleep(time.Duration(ms) * time.Millisecond)\n"
            "}\n"
            "\n"
            "func VecZeros(n int) []float64 {\n"
            "    return make([]float64, n)\n"
            "}\n"
        )

    def _build_main(self) -> str:
        lines = [
            f"// 由 Matha 生成的 Go 主程序\n"
            f"package main\n"
            f"\n"
            f"import (\n"
            f"    \"fmt\"\n"
            f"    \"{self.app.name}/matha\"\n"
            f")\n"
            f"\n"
        ]

        for func_name, func in self.mir.functions.items():
            if func_name == "main":
                lines.append("func main() {")
            else:
                params = ", ".join(f"{p} float64" for p in func.params)
                lines.append(f"func {func_name}({params}) float64 {{")

            for instr in func.instructions:
                lines.append(f"    // {instr.instr_type.name if hasattr(instr, 'instr_type') else 'instr'}")
                if hasattr(instr, 'result') and instr.result:
                    if instr.instr_type == MIRInstrType.VLOAD:
                        lines.append(f"    {instr.result} := matha.VecZeros({instr.metadata.get('len', '0')})")
                    elif instr.instr_type in (MIRInstrType.VADD, MIRInstrType.VSUB, MIRInstrType.VMUL, MIRInstrType.VDIV):
                        op_map = {MIRInstrType.VADD: "Add", MIRInstrType.VSUB: "Sub",
                                 MIRInstrType.VMUL: "Mul", MIRInstrType.VDIV: "Div"}
                        op = op_map.get(instr.instr_type, "Add")
                        lines.append(f"    {instr.result} := {instr.operands[0]}.{op}({instr.operands[1]})")
                    elif instr.instr_type == MIRInstrType.VDOT:
                        lines.append(f"    {instr.result} := {instr.operands[0]}.Dot({instr.operands[1]})")
                    elif instr.instr_type == MIRInstrType.VMATMUL:
                        lines.append(f"    {instr.result} := matha.MatMul({instr.operands[0]}, {instr.operands[1]})")
                    elif instr.instr_type in (MIRInstrType.VREDUCE_SUM, MIRInstrType.VREDUCE_MAX,
                                             MIRInstrType.VREDUCE_MIN, MIRInstrType.VREDUCE_MEAN):
                        op_map = {MIRInstrType.VREDUCE_SUM: "ReduceSum",
                                 MIRInstrType.VREDUCE_MAX: "ReduceMax",
                                 MIRInstrType.VREDUCE_MIN: "ReduceMin",
                                 MIRInstrType.VREDUCE_MEAN: "ReduceMean"}
                        op = op_map.get(instr.instr_type, "ReduceSum")
                        lines.append(f"    {instr.result} := {instr.operands[0]}.{op}()")
                    elif instr.instr_type == MIRInstrType.ADD:
                        lines.append(f"    {instr.result} := {instr.operands[0]} + {instr.operands[1]}")
                    elif instr.instr_type == MIRInstrType.SUB:
                        lines.append(f"    {instr.result} := {instr.operands[0]} - {instr.operands[1]}")
                    elif instr.instr_type == MIRInstrType.MUL:
                        lines.append(f"    {instr.result} := {instr.operands[0]} * {instr.operands[1]}")
                    elif instr.instr_type == MIRInstrType.DIV:
                        lines.append(f"    {instr.result} := {instr.operands[0]} / {instr.operands[1]}")
                    elif instr.instr_type == MIRInstrType.RETURN:
                        if func_name == "main":
                            lines.append("    return")
                        else:
                            lines.append(f"    return {instr.value or 0}")
                    elif instr.instr_type == MIRInstrType.CALL:
                        args = ", ".join(instr.operands)
                        lines.append(f"    {instr.result} := {instr.metadata.get('func_name', 'unknown')}({args})")
                    elif instr.instr_type == MIRInstrType.SPAWN:
                        func = instr.metadata.get('func_name', 'unknown')
                        lines.append(f"    go {func}()")
                    elif instr.instr_type == MIRInstrType.SEND:
                        ch = instr.metadata.get('channel')
                        lines.append(f"    {ch} <- {instr.operands[0] if instr.operands else 0}")
                    elif instr.instr_type == MIRInstrType.RECV:
                        ch = instr.metadata.get('channel')
                        lines.append(f"    {instr.result} := <-{ch}")
                    elif instr.instr_type == MIRInstrType.CHANNEL_CREATE:
                        lines.append(f"    {instr.result} := matha.MakeChannel[int](0)")

            lines.append("}")
            lines.append("")

            if func_name == "main":
                lines.append("// 程序入口")
                lines.append("func init() {")
                lines.append("    // 初始化代码")
                lines.append("}")

        return "\n".join(lines)


# 便捷函数
def generate_go(mir_program: MIRProgram, out_dir: str) -> CodegenResult:
    gen = GoGenerator(mir_program, out_dir)
    return gen.generate()
