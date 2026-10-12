"""
PythonGenerator：把 Matha MIR 编译为 Python 代码（可直接运行/作为模块导入）。
支持：函数、算术、控制流、向量/矩阵（NumPy）、异步、类型注解。
"""

from __future__ import annotations

from src.codegen.base import CodegenResult, Generator
from src.mir import MIRFunction, MIRInstrType, MIRProgram


class PythonGenerator(Generator):
    """Python 代码生成器：MIRProgram → .py 文件。"""

    def __init__(self, mir_program: MIRProgram, out_dir: str):
        self.mir = mir_program
        self.out_dir = out_dir
        class DummyApp:
            kind = "Python程序"
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
            # main.py
            main_content = self._build_main()
            files.append(self._write("main.py", main_content))

            # matha_rt.py (运行时库)
            rt_content = self._build_runtime()
            self._write("matha_rt.py", rt_content)

            # pyproject.toml
            pyproject = self._build_pyproject()
            files.append(self._write("pyproject.toml", pyproject))

        except Exception as e:
            return CodegenResult(成功=False, 类型="Python程序", 名称=self.app.name, 错误=str(e))

        return CodegenResult(
            成功=True, 类型="Python程序", 名称=self.app.name,
            文件=files, 入口="main.py",
        )

    def _build_pyproject(self) -> str:
        name = self.app.name.lower().replace(" ", "-")
        return (
            f'[project]\n'
            f'name = "{name}"\n'
            f'version = "1.0.0"\n'
            f'description = "Matha 生成的 Python 项目"\n'
            f'readme = "README.md"\n'
            f'requires-python = ">=3.10"\n'
            f'dependencies = [\n'
            f'    "numpy>=1.24",\n'
            f'    "async-mutex>=0.4",\n'
            f']\n'
            f'\n'
            f'[project.optional-dependencies]\n'
            f'dev = [\n'
            f'    "pytest>=7.0",\n'
            f'    "black>=23.0",\n'
            f'    "mypy>=1.0",\n'
            f']\n'
            f'\n'
            f'[build-system]\n'
            f'requires = ["setuptools>=68", "wheel"]\n'
            f'build-backend = "setuptools.build_meta"\n'
        )

    def _build_runtime(self) -> str:
        return (
            '# -*- coding: utf-8 -*-\n'
            '"""Matha Python 运行时库。"""\n'
            'from __future__ import annotations\n'
            'import asyncio\n'
            'import numpy as np\n'
            'from typing import List, Dict, Any, Optional\n'
            'from async_mutex import Mutex as AsyncMutex\n'
            'from contextlib import asynccontextmanager\n'
            '\n'
            '# ===== 向量/矩阵运算 =====\n'
            '\n'
            'class Vec:\n'
            '    """向量类，封装 numpy.ndarray。"""\n'
            '    def __init__(self, data: np.ndarray):\n'
            '        self.data = np.asarray(data, dtype=np.float64)\n'
            '    \n'
            '    @classmethod\n'
            '    def zeros(cls, n: int) -> "Vec":\n'
            '        return cls(np.zeros(n, dtype=np.float64))\n'
            '    \n'
            '    @classmethod\n'
            '    def from_list(cls, arr: List[float]) -> "Vec":\n'
            '        return cls(np.array(arr, dtype=np.float64))\n'
            '    \n'
            '    @property\n'
            '    def len(self) -> int:\n'
            '        return len(self.data)\n'
            '    \n'
            '    def add(self, other: "Vec") -> "Vec":\n'
            '        return Vec(self.data + other.data)\n'
            '    \n'
            '    def sub(self, other: "Vec") -> "Vec":\n'
            '        return Vec(self.data - other.data)\n'
            '    \n'
            '    def mul(self, other: "Vec") -> "Vec":\n'
            '        return Vec(self.data * other.data)\n'
            '    \n'
            '    def div(self, other: "Vec") -> "Vec":\n'
            '        with np.errstate(divide="ignore", invalid="ignore"):\n'
            '            result = np.divide(self.data, other.data, where=other.data!=0)\n'
            '        return Vec(result)\n'
            '    \n'
            '    def dot(self, other: "Vec") -> float:\n'
            '        return float(np.dot(self.data, other.data))\n'
            '    \n'
            '    def reduce_sum(self) -> float:\n'
            '        return float(np.sum(self.data))\n'
            '    \n'
            '    def reduce_max(self) -> float:\n'
            '        return float(np.max(self.data))\n'
            '    \n'
            '    def reduce_min(self) -> float:\n'
            '        return float(np.min(self.data))\n'
            '    \n'
            '    def reduce_mean(self) -> float:\n'
            '        return float(np.mean(self.data))\n'
            '    \n'
            '    def to_list(self) -> List[float]:\n'
            '        return self.data.tolist()\n'
            '\n'
            '\n'
            'class Mat:\n'
            '    """矩阵类，封装 numpy.ndarray。"""\n'
            '    def __init__(self, rows: int, cols: int, data: Optional[np.ndarray] = None):\n'
            '        self.rows = rows\n'
            '        self.cols = cols\n'
            '        if data is not None:\n'
            '            self.data = np.asarray(data, dtype=np.float64).reshape(rows, cols)\n'
            '        else:\n'
            '            self.data = np.zeros((rows, cols), dtype=np.float64)\n'
            '    \n'
            '    @classmethod\n'
            '    def zeros(cls, rows: int, cols: int) -> "Mat":\n'
            '        return cls(rows, cols, np.zeros((rows, cols), dtype=np.float64))\n'
            '    \n'
            '    def get(self, i: int, j: int) -> float:\n'
            '        return float(self.data[i, j])\n'
            '    \n'
            '    def set(self, i: int, j: int, v: float) -> None:\n'
            '        self.data[i, j] = v\n'
            '    \n'
            '    def mul(self, other: "Mat") -> "Mat":\n'
            '        if self.cols != other.rows:\n'
            '            raise ValueError(f"维度不匹配: {self.cols} != {other.rows}")\n'
            '        result = Mat(self.rows, other.cols)\n'
            '        result.data = self.data @ other.data\n'
            '        return result\n'
            '    \n'
            '    def transpose(self) -> "Mat":\n'
            '        result = Mat(self.cols, self.rows)\n'
            '        result.data = self.data.T\n'
            '        return result\n'
            '\n'
            '\n'
            '# ===== 异步通道 =====\n'
            '\n'
            'class Channel:\n'
            '    """异步通道。"""\n'
            '    def __init__(self):\n'
            '        self._queue: asyncio.Queue = asyncio.Queue()\n'
            '        self._closed = False\n'
            '    \n'
            '    async def send(self, value: Any) -> None:\n'
            '        if self._closed:\n'
            '            raise RuntimeError("通道已关闭")\n'
            '        await self._queue.put(value)\n'
            '    \n'
            '    async def recv(self) -> Any:\n'
            '        return await self._queue.get()\n'
            '    \n'
            '    def close(self) -> None:\n'
            '        self._closed = True\n'
            '    \n'
            '    @property\n'
            '    def is_closed(self) -> bool:\n'
            '        return self._closed\n'
            '\n'
            '\n'
            'def make_channel() -> Channel:\n'
            '    return Channel()\n'
            '\n'
            '\n'
            '# ===== 同步原语 =====\n'
            '\n'
            'class Mutex:\n'
            '    """异步互斥锁。"""\n'
            '    def __init__(self):\n'
            '        self._lock = AsyncMutex()\n'
            '    \n'
            '    async def lock(self) -> None:\n'
            '        await self._lock.acquire()\n'
            '    \n'
            '    def unlock(self) -> None:\n'
            '        self._lock.release()\n'
            '    \n'
            '    @asynccontextmanager\n'
            '    async def locked(self):\n'
            '        await self.lock()\n'
            '        try:\n'
            '            yield\n'
            '        finally:\n'
            '            self.unlock()\n'
            '\n'
            '\n'
            '# ===== 工具函数 =====\n'
            '\n'
            'async def sleep(ms: int) -> None:\n'
            '    await asyncio.sleep(ms / 1000.0)\n'
            '\n'
            '\n'
            'async def select(channels: List[Channel]) -> Any:\n'
            '    """简化的多路选择：返回第一个就绪通道的值。"""\n'
            '    tasks = [asyncio.create_task(ch.recv()) for ch in channels]\n'
            '    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)\n'
            '    for t in pending:\n'
            '        t.cancel()\n'
            '    return done.pop().result()\n'
            '\n'
            '\n'
            'def vec_zeros(n: int):\n'
            '    return Vec.zeros(n)\n'
            '\n'
            '\n'
            'def vec_from(arr: List[float]):\n'
            '    return Vec.from_list(arr)\n'
        )

    def _build_main(self) -> str:
        lines = [
            '# -*- coding: utf-8 -*-\n'
            '"""由 Matha 生成的 Python 主程序。"""\n'
            'from __future__ import annotations\n'
            'import asyncio\n'
            'import numpy as np\n'
            'from typing import List\n'
            'from matha_rt import (\n'
            '    Vec, Mat, Channel, Mutex, sleep, select, make_channel,\n'
            '    vec_zeros, vec_from\n'
            ')\n'
            '',
        ]

        for func_name, func in self.mir.functions.items():
            if func_name == "main":
                lines.append("async def main() -> None:")
            else:
                params = ", ".join(func.params)
                lines.append(f"async def {func_name}({params}) -> float:")

            for instr in func.instructions:
                lines.append(f"    # {instr.instr_type.name if hasattr(instr, 'instr_type') else 'instr'}")
                if hasattr(instr, 'result') and instr.result:
                    if instr.instr_type == MIRInstrType.VLOAD:
                        lines.append(f"    {instr.result} = vec_zeros({instr.metadata.get('len', '0')})")
                    elif instr.instr_type in (MIRInstrType.VADD, MIRInstrType.VSUB, MIRInstrType.VMUL, MIRInstrType.VDIV):
                        op_map = {MIRInstrType.VADD: "add", MIRInstrType.VSUB: "sub",
                                 MIRInstrType.VMUL: "mul", MIRInstrType.VDIV: "div"}
                        op = op_map.get(instr.instr_type, "add")
                        lines.append(f"    {instr.result} = {instr.operands[0]}.{op}({instr.operands[1]})")
                    elif instr.instr_type == MIRInstrType.VDOT:
                        lines.append(f"    {instr.result} = {instr.operands[0]}.dot({instr.operands[1]})")
                    elif instr.instr_type == MIRInstrType.VMATMUL:
                        lines.append(f"    {instr.result} = {instr.operands[0]}.mul({instr.operands[1]})")
                    elif instr.instr_type in (MIRInstrType.VREDUCE_SUM, MIRInstrType.VREDUCE_MAX,
                                             MIRInstrType.VREDUCE_MIN, MIRInstrType.VREDUCE_MEAN):
                        op_map = {MIRInstrType.VREDUCE_SUM: "reduce_sum",
                                 MIRInstrType.VREDUCE_MAX: "reduce_max",
                                 MIRInstrType.VREDUCE_MIN: "reduce_min",
                                 MIRInstrType.VREDUCE_MEAN: "reduce_mean"}
                        op = op_map.get(instr.instr_type, "reduce_sum")
                        lines.append(f"    {instr.result} = {instr.operands[0]}.{op}()")
                    elif instr.instr_type == MIRInstrType.ADD:
                        lines.append(f"    {instr.result} = {instr.operands[0]} + {instr.operands[1]}")
                    elif instr.instr_type == MIRInstrType.SUB:
                        lines.append(f"    {instr.result} = {instr.operands[0]} - {instr.operands[1]}")
                    elif instr.instr_type == MIRInstrType.MUL:
                        lines.append(f"    {instr.result} = {instr.operands[0]} * {instr.operands[1]}")
                    elif instr.instr_type == MIRInstrType.DIV:
                        lines.append(f"    {instr.result} = {instr.operands[0]} / {instr.operands[1]}")
                    elif instr.instr_type == MIRInstrType.RETURN:
                        if func_name == "main":
                            lines.append("    return")
                        else:
                            lines.append(f"    return {instr.value or 0}")
                    elif instr.instr_type == MIRInstrType.CALL:
                        args = ", ".join(instr.operands)
                        lines.append(f"    {instr.result} = await {instr.metadata.get('func_name', 'unknown')}({args})")
                    elif instr.instr_type == MIRInstrType.SPAWN:
                        func = instr.metadata.get('func_name', 'unknown')
                        lines.append(f"    asyncio.create_task({func}())")
                    elif instr.instr_type == MIRInstrType.SEND:
                        ch = instr.metadata.get('channel')
                        lines.append(f"    await {ch}.send({instr.operands[0] if instr.operands else 0})")
                    elif instr.instr_type == MIRInstrType.RECV:
                        ch = instr.metadata.get('channel')
                        lines.append(f"    {instr.result} = await {ch}.recv()")
                    elif instr.instr_type == MIRInstrType.CHANNEL_CREATE:
                        lines.append(f"    {instr.result} = make_channel()")
                    elif instr.instr_type == MIRInstrType.MUTEX_LOCK:
                        lines.append(f"    await {instr.metadata.get('mutex')}.lock()")
                    elif instr.instr_type == MIRInstrType.MUTEX_UNLOCK:
                        lines.append(f"    {instr.metadata.get('mutex')}.unlock()")

            lines.append("")

            if func_name == "main":
                lines.append("if __name__ == '__main__':")
                lines.append("    asyncio.run(main())")
                lines.append("")

        return "\n".join(lines)


# 便捷函数
def generate_python(mir_program: MIRProgram, out_dir: str) -> CodegenResult:
    gen = PythonGenerator(mir_program, out_dir)
    return gen.generate()
