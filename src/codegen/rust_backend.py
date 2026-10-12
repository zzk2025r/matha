"""
RustGenerator：把 Matha MIR 编译为 Rust 代码（cargo 可构建）。
支持：函数、算术、控制流、向量、并发通道。
"""

from __future__ import annotations

from src.codegen.base import CodegenResult, Generator
from src.mir import MIRFunction, MIRInstrType, MIRProgram


class RustGenerator(Generator):
    """Rust 代码生成器：MIRProgram → Cargo 项目。"""

    def __init__(self, mir_program: MIRProgram, out_dir: str):
        self.mir = mir_program
        self.out_dir = out_dir
        class DummyApp:
            kind = "Rust程序"
            name = mir_program.functions.get("main", MIRFunction(name="main")).name.replace("-", "_")
            title = name
            elements = []
            styles = []
            scripts = []
            meta = {}
        self.app = DummyApp()

    def _build_cargo_toml(self) -> str:
        name = self.app.name
        return (
            f'[package]\n'
            f'name = "{name}"\n'
            f'version = "0.1.0"\n'
            f'edition = "2021"\n'
            f'\n'
            f'[dependencies]\n'
            f'nalgebra = "0.32"\n'
            f'crossbeam-channel = "0.5"\n'
            f'parking_lot = "0.12"\n'
            f'num-cpus = "1.16"\n'
        )

    def _build_lib_rs(self) -> str:
        lines = [
            "// 由 Matha 生成的 Rust 库",
            "",
            "// 向量/矩阵运算模块",
            "pub mod math {",
            "    use nalgebra::{DVector, DMatrix};",
            "",
            "    /// 向量加法",
            "    pub fn vec_add(a: &DVector<f64>, b: &DVector<f64>) -> DVector<f64> {",
            "        a + b",
            "    }",
            "",
            "    /// 向量减法",
            "    pub fn vec_sub(a: &DVector<f64>, b: &DVector<f64>) -> DVector<f64> {",
            "        a - b",
            "    }",
            "",
            "    /// 向量点积",
            "    pub fn vec_dot(a: &DVector<f64>, b: &DVector<f64>) -> f64 {",
            "        a.dot(b)",
            "    }",
            "",
            "    /// 向量归约求和",
            "    pub fn vec_reduce_sum(v: &DVector<f64>) -> f64 {",
            "        v.sum()",
            "    }",
            "",
            "    /// 向量归约最大值",
            "    pub fn vec_reduce_max(v: &DVector<f64>) -> f64 {",
            "        v.max()",
            "    }",
            "",
            "    /// 向量归约最小值",
            "    pub fn vec_reduce_min(v: &DVector<f64>) -> f64 {",
            "        v.min()",
            "    }",
            "",
            "    /// 向量归约平均值",
            "    pub fn vec_reduce_mean(v: &DVector<f64>) -> f64 {",
            "        v.mean()",
            "    }",
            "",
            "    /// 矩阵乘法",
            "    pub fn mat_mul(a: &DMatrix<f64>, b: &DMatrix<f64>) -> DMatrix<f64> {",
            "        a * b",
            "    }",
            "",
            "    /// 矩阵转置",
            "    pub fn mat_transpose(m: &DMatrix<f64>) -> DMatrix<f64> {",
            "        m.transpose()",
            "    }",
            "",
            "}",
            "",
            "// 并发通道模块",
            "pub mod channel {",
            "    use crossbeam_channel::{bounded, unbounded, Receiver, Sender, Select};",
            "",
            "    /// 创建有界通道",
            "    pub fn bounded<T>(cap: usize) -> (Sender<T>, Receiver<T>) {",
            "        bounded(cap)",
            "    }",
            "",
            "    /// 创建无界通道",
            "    pub fn unbounded<T>() -> (Sender<T>, Receiver<T>) {",
            "        unbounded()",
            "    }",
            "",
            "    /// 多路选择",
            "    pub fn select<T>(cases: Vec<(&Receiver<T>, Box<dyn FnOnce(T) + Send>)>) {",
            "        let sel = Select::new();",
            "        for (rx, _) in &cases {",
            "            sel.recv(rx);",
            "        }",
            "        let oper = sel.select();",
            "        let idx = oper.index();",
            "        if let Ok(msg) = oper.recv(&cases[idx].0) {",
            "            cases[idx].1(msg);",
            "        }",
            "    }",
            "}",
            "",
            "// 同步原语",
            "pub mod sync {",
            "    use parking_lot::{Mutex, Condvar, RwLock};",
            "    use std::sync::Arc;",
            "",
            "    /// 互斥锁",
            "    pub type Mutex<T> = Mutex<T>;",
            "",
            "    /// 条件变量",
            "    pub type Condvar = Condvar;",
            "",
            "    /// 读写锁",
            "    pub type RwLock<T> = RwLock<T>;",
            "",
            "    /// 原子引用计数",
            "    pub type Arc<T> = Arc<T>;",
            "",
            "}",
        ]
        return "\n".join(lines)

    def _build_main_rs(self) -> str:
        lines = [
            "// 由 Matha 生成的 Rust 主程序",
            "",
            "use crate::math;",
            "use crate::channel;",
            "use crate::sync;",
            "",
        ]

        for func_name, func in self.mir.functions.items():
            if func_name == "main":
                lines.append("fn main() {")
            else:
                params = ", ".join(f"{p}: f64" for p in func.params)
                lines.append(f"fn {func_name}({params}) -> f64 {{")

            for instr in func.instructions:
                lines.append(f"    // {instr.instr_type.name if hasattr(instr, 'instr_type') else 'instr'}")
                if hasattr(instr, 'result') and instr.result:
                    if instr.instr_type == MIRInstrType.VLOAD:
                        lines.append(f"    let {instr.result} = DVector::zeros({instr.metadata.get('len', '0')});")
                    elif instr.instr_type in (MIRInstrType.VADD, MIRInstrType.VSUB, MIRInstrType.VMUL, MIRInstrType.VDIV):
                        op_map = {MIRInstrType.VADD: "math::vec_add", MIRInstrType.VSUB: "math::vec_sub",
                                 MIRInstrType.VMUL: "math::vec_mul", MIRInstrType.VDIV: "math::vec_div"}
                        op = op_map.get(instr.instr_type, "math::vec_add")
                        lines.append(f"    let {instr.result} = {op}(&{instr.operands[0]}, &{instr.operands[1]});")
                    elif instr.instr_type == MIRInstrType.VDOT:
                        lines.append(f"    let {instr.result} = math::vec_dot(&{instr.operands[0]}, &{instr.operands[1]});")
                    elif instr.instr_type == MIRInstrType.VMATMUL:
                        lines.append(f"    let {instr.result} = math::mat_mul(&{instr.operands[0]}, &{instr.operands[1]});")
                    elif instr.instr_type in (MIRInstrType.VREDUCE_SUM, MIRInstrType.VREDUCE_MAX,
                                             MIRInstrType.VREDUCE_MIN, MIRInstrType.VREDUCE_MEAN):
                        op_map = {MIRInstrType.VREDUCE_SUM: "math::vec_reduce_sum",
                                 MIRInstrType.VREDUCE_MAX: "math::vec_reduce_max",
                                 MIRInstrType.VREDUCE_MIN: "math::vec_reduce_min",
                                 MIRInstrType.VREDUCE_MEAN: "math::vec_reduce_mean"}
                        op = op_map.get(instr.instr_type, "math::vec_reduce_sum")
                        lines.append(f"    let {instr.result} = {op}(&{instr.operands[0]});")
                    elif instr.instr_type == MIRInstrType.ADD:
                        lines.append(f"    let {instr.result} = {instr.operands[0]} + {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.SUB:
                        lines.append(f"    let {instr.result} = {instr.operands[0]} - {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.MUL:
                        lines.append(f"    let {instr.result} = {instr.operands[0]} * {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.DIV:
                        lines.append(f"    let {instr.result} = {instr.operands[0]} / {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.RETURN:
                        if func_name == "main":
                            lines.append("    return;")
                        else:
                            lines.append(f"    return {instr.value or 0.0};")
                    elif instr.instr_type == MIRInstrType.CALL:
                        args = ", ".join(instr.operands)
                        lines.append(f"    let {instr.result} = {instr.metadata.get('func_name', 'unknown')}({args});")
                    elif instr.instr_type == MIRInstrType.SPAWN:
                        lines.append(f"    std::thread::spawn(move || {{ {instr.metadata.get('func_name', 'unknown')}() }});")
                    elif instr.instr_type == MIRInstrType.SEND:
                        lines.append(f"    channel::send(&{instr.metadata.get('channel')}, {instr.operands[0] if instr.operands else 0});")
                    elif instr.instr_type == MIRInstrType.RECV:
                        lines.append(f"    let {instr.result} = channel::recv(&{instr.metadata.get('channel')}).unwrap();")
                    elif instr.instr_type == MIRInstrType.CHANNEL_CREATE:
                        lines.append(f"    let ({instr.result}, _) = channel::unbounded();")

            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def generate(self) -> CodegenResult:
        files = []
        try:
            cargo_content = self._build_cargo_toml()
            files.append(self._write("Cargo.toml", cargo_content))

            # 确保 src 目录存在
            import os
            os.makedirs(os.path.join(self.out_dir, "src"), exist_ok=True)

            lib_content = self._build_lib_rs()
            self._write("src/lib.rs", lib_content)

            main_content = self._build_main_rs()
            files.append(self._write("src/main.rs", main_content))

        except Exception as e:
            return CodegenResult(成功=False, 类型="Rust程序", 名称=self.app.name, 错误=str(e))

        return CodegenResult(
            成功=True, 类型="Rust程序", 名称=self.app.name,
            文件=files, 入口="src/main.rs",
        )


# 便捷函数
def generate_rust(mir_program: MIRProgram, out_dir: str) -> CodegenResult:
    gen = RustGenerator(mir_program, out_dir)
    return gen.generate()
