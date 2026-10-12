"""
JSGenerator：把 Matha MIR 编译为 JavaScript/TypeScript 代码（可 Node.js/Deno/浏览器运行）。
支持：函数、算术、控制流、向量、异步通道、Promise。
"""

from __future__ import annotations

from src.codegen.base import CodegenResult, Generator
from src.mir import MIRFunction, MIRInstrType, MIRProgram


class JSGenerator(Generator):
    """JavaScript/TypeScript 代码生成器：MIRProgram → .js/.ts 文件。"""

    def __init__(self, mir_program: MIRProgram, out_dir: str, use_typescript: bool = True):
        self.mir = mir_program
        self.out_dir = out_dir
        self.use_ts = use_typescript
        class DummyApp:
            kind = "JavaScript程序"
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
            ext = ".ts" if self.use_ts else ".js"

            # package.json
            pkg_content = self._build_package_json()
            files.append(self._write("package.json", pkg_content))

            # tsconfig.json (仅 TS)
            if self.use_ts:
                tsconfig = self._build_tsconfig()
                files.append(self._write("tsconfig.json", tsconfig))

            # lib.ts / lib.js
            lib_content = self._build_lib()
            files.append(self._write(f"lib{ext}", lib_content))

            # main.ts / main.js
            main_content = self._build_main()
            files.append(self._write(f"main{ext}", main_content))

        except Exception as e:
            return CodegenResult(成功=False, 类型="JavaScript程序", 名称=self.app.name, 错误=str(e))

        return CodegenResult(
            成功=True, 类型="JavaScript程序", 名称=self.app.name,
            文件=files, 入口=f"main{ext}",
        )

    def _build_package_json(self) -> str:
        name = self.app.name.lower().replace(" ", "-")
        return (
            '{\n'
            f'  "name": "{name}",\n'
            '  "version": "1.0.0",\n'
            '  "description": "Matha 生成的 JS/TS 项目",\n'
            '  "main": "main.js",\n'
            '  "scripts": {\n'
            '    "start": "node main.js",\n'
            '    "dev": "ts-node main.ts",\n'
            '    "build": "tsc",\n'
            '    "test": "jest"\n'
            '  },\n'
            '  "dependencies": {\n'
            '    "nalgebra": "^1.0.0",\n'
            '    "async-mutex": "^0.4.0"\n'
            '  },\n'
            '  "devDependencies": {\n'
            '    "@types/node": "^20.0.0",\n'
            '    "typescript": "^5.0.0",\n'
            '    "ts-node": "^10.9.0",\n'
            '    "jest": "^29.0.0"\n'
            '  }\n'
            '}\n'
        )

    def _build_tsconfig(self) -> str:
        return (
            '{\n'
            '  "compilerOptions": {\n'
            '    "target": "ES2022",\n'
            '    "module": "commonjs",\n'
            '    "lib": ["ES2022"],\n'
            '    "outDir": "./dist",\n'
            '    "rootDir": ".",\n'
            '    "strict": true,\n'
            '    "esModuleInterop": true,\n'
            '    "skipLibCheck": true,\n'
            '    "forceConsistentCasingInFileNames": true,\n'
            '    "declaration": true,\n'
            '    "declarationMap": true,\n'
            '    "sourceMap": true\n'
            '  },\n'
            '  "include": ["*.ts"],\n'
            '  "exclude": ["node_modules", "dist"]\n'
            '}\n'
        )

    def _build_lib(self) -> str:
        lines = [
            "// 由 Matha 生成的数学/并发库",
            "",
            "// ===== 向量/矩阵运算 =====",
            "",
            "export class Vec {",
            "  constructor(public data: number[]) {}",
            "",
            "  static zeros(n: number): Vec {",
            "    return new Vec(new Float64Array(n));",
            "  }",
            "",
            "  static from(arr: number[]): Vec {",
            "    return new Vec(new Float64Array(arr));",
            "  }",
            "",
            "  get len(): number { return this.data.length; }",
            "",
            "  add(other: Vec): Vec {",
            "    const r = new Float64Array(this.len);",
            "    for (let i = 0; i < this.len; ++i) r[i] = this.data[i] + other.data[i];",
            "    return new Vec(r);",
            "  }",
            "",
            "  sub(other: Vec): Vec {",
            "    const r = new Float64Array(this.len);",
            "    for (let i = 0; i < this.len; ++i) r[i] = this.data[i] - other.data[i];",
            "    return new Vec(r);",
            "  }",
            "",
            "  mul(other: Vec): Vec {",
            "    const r = new Float64Array(this.len);",
            "    for (let i = 0; i < this.len; ++i) r[i] = this.data[i] * other.data[i];",
            "    return new Vec(r);",
            "  }",
            "",
            "  div(other: Vec): Vec {",
            "    const r = new Float64Array(this.len);",
            "    for (let i = 0; i < this.len; ++i) r[i] = other.data[i] !== 0 ? this.data[i] / other.data[i] : 0;",
            "    return new Vec(r);",
            "  }",
            "",
            "  dot(other: Vec): number {",
            "    let sum = 0;",
            "    for (let i = 0; i < this.len; ++i) sum += this.data[i] * other.data[i];",
            "    return sum;",
            "  }",
            "",
            "  reduceSum(): number {",
            "    let sum = 0; for (let i = 0; i < this.len; ++i) sum += this.data[i]; return sum;",
            "  }",
            "",
            "  reduceMax(): number {",
            "    let m = this.data[0]; for (let i = 1; i < this.len; ++i) if (this.data[i] > m) m = this.data[i]; return m;",
            "  }",
            "",
            "  reduceMin(): number {",
            "    let m = this.data[0]; for (let i = 1; i < this.len; ++i) if (this.data[i] < m) m = this.data[i]; return m;",
            "  }",
            "",
            "  reduceMean(): number {",
            "    return this.reduceSum() / this.len;",
            "  }",
            "",
            "  toArray(): number[] { return Array.from(this.data); }",
            "}",
            "",
            "// 矩阵类",
            "export class Mat {",
            "  constructor(public rows: number, public cols: number, public data: Float64Array) {}",
            "",
            "  static zeros(rows: number, cols: number): Mat {",
            "    return new Mat(rows, cols, new Float64Array(rows * cols));",
            "  }",
            "",
            "  get(i: number, j: number): number { return this.data[i * this.cols + j]; }",
            "  set(i: number, j: number, v: number): void { this.data[i * this.cols + j] = v; }",
            "",
            "  mul(other: Mat): Mat {",
            "    if (this.cols !== other.rows) throw new Error('维度不匹配');",
            "    const r = Mat.zeros(this.rows, other.cols);",
            "    for (let i = 0; i < this.rows; ++i) {",
            "      for (let j = 0; j < other.cols; ++j) {",
            "        let sum = 0;",
            "        for (let k = 0; k < this.cols; ++k) sum += this.get(i, k) * other.get(k, j);",
            "        r.set(i, j, sum);",
            "      }",
            "    }",
            "    return r;",
            "  }",
            "",
            "  transpose(): Mat {",
            "    const r = Mat.zeros(this.cols, this.rows);",
            "    for (let i = 0; i < this.rows; ++i) {",
            "      for (let j = 0; j < this.cols; ++j) r.set(j, i, this.get(i, j));",
            "    }",
            "    return r;",
            "  }",
            "}",
            "",
            "// ===== 并发通道 =====",
            "",
            "export class Channel<T> {",
            "  private queue: T[] = [];",
            "  private waiting: Array<(v: T) => void> = [];",
            "  private closed = false;",
            "",
            "  send(v: T): void {",
            "    if (this.waiting.length > 0) {",
            "      const resolve = this.waiting.shift()!;",
            "      resolve(v);",
            "    } else {",
            "      this.queue.push(v);",
            "    }",
            "  }",
            "",
            "  recv(): Promise<T> {",
            "    if (this.queue.length > 0) return Promise.resolve(this.queue.shift()!);",
            "    return new Promise(resolve => this.waiting.push(resolve));",
            "  }",
            "",
            "  close(): void { this.closed = true; }",
            "  isClosed(): boolean { return this.closed; }",
            "}",
            "",
            "export function makeChannel<T>(): Channel<T> { return new Channel<T>(); }",
            "",
            "// ===== 同步原语 =====",
            "",
            "export class Mutex {",
            "  private locked = false;",
            "  private waiters: Array<() => void> = [];",
            "",
            "  async lock(): Promise<void> {",
            "    if (!this.locked) { this.locked = true; return; }",
            "    return new Promise(resolve => this.waiters.push(resolve));",
            "  }",
            "",
            "  unlock(): void {",
            "    if (this.waiters.length > 0) this.waiters.shift()!();",
            "    else this.locked = false;",
            "  }",
            "}",
            "",
            "export class Condvar {",
            "  private waiters: Array<() => void> = [];",
            "",
            "  async wait(mutex: Mutex): Promise<void> {",
            "    await mutex.unlock();",
            "    return new Promise(resolve => {",
            "      this.waiters.push(() => { mutex.lock().then(resolve); });",
            "    });",
            "  }",
            "",
            "  signal(): void {",
            "    if (this.waiters.length > 0) this.waiters.shift()!();",
            "  }",
            "",
            "  broadcast(): void {",
            "    this.waiters.forEach(w => w());",
            "    this.waiters = [];",
            "  }",
            "}",
            "",
            "// ===== 异步工具 =====",
            "",
            "export async function sleep(ms: number): Promise<void> {",
            "  return new Promise(r => setTimeout(r, ms));",
            "}",
            "",
            "export async function select<T>(cases: Array<[Channel<T>, (v: T) => Promise<void>]>): Promise<void> {",
            "  // 简化实现：轮询",
            "  while (true) {",
            "    for (const [ch, handler] of cases) {",
            "      if (!ch.queue.length) continue;",
            "      const v = ch.queue.shift()!;",
            "      await handler(v);",
            "      return;",
            "    }",
            "    await sleep(1);",
            "  }",
            "}",
        ]
        return "\n".join(lines)

    def _build_main(self) -> str:
        ext = ".ts" if self.use_ts else ".js"
        lines = [
            f"// 由 Matha 生成的主程序 ({ext})",
            "",
            "import { Vec, Mat, Channel, Mutex, Condvar, sleep, select, makeChannel } from './lib';",
            "",
        ]

        for func_name, func in self.mir.functions.items():
            if func_name == "main":
                lines.append("async function main() {")
            else:
                params = ", ".join(func.params)
                lines.append(f"async function {func_name}({params}) {{")

            for instr in func.instructions:
                lines.append(f"  // {instr.instr_type.name if hasattr(instr, 'instr_type') else 'instr'}")
                if hasattr(instr, 'result') and instr.result:
                    if instr.instr_type == MIRInstrType.VLOAD:
                        lines.append(f"  const {instr.result} = Vec.zeros({instr.metadata.get('len', '0')});")
                    elif instr.instr_type in (MIRInstrType.VADD, MIRInstrType.VSUB, MIRInstrType.VMUL, MIRInstrType.VDIV):
                        op_map = {MIRInstrType.VADD: "add", MIRInstrType.VSUB: "sub",
                                 MIRInstrType.VMUL: "mul", MIRInstrType.VDIV: "div"}
                        op = op_map.get(instr.instr_type, "add")
                        lines.append(f"  const {instr.result} = {instr.operands[0]}.{op}({instr.operands[1]});")
                    elif instr.instr_type == MIRInstrType.VDOT:
                        lines.append(f"  const {instr.result} = {instr.operands[0]}.dot({instr.operands[1]});")
                    elif instr.instr_type == MIRInstrType.VMATMUL:
                        lines.append(f"  const {instr.result} = {instr.operands[0]}.mul({instr.operands[1]});")
                    elif instr.instr_type in (MIRInstrType.VREDUCE_SUM, MIRInstrType.VREDUCE_MAX,
                                             MIRInstrType.VREDUCE_MIN, MIRInstrType.VREDUCE_MEAN):
                        op_map = {MIRInstrType.VREDUCE_SUM: "reduceSum",
                                 MIRInstrType.VREDUCE_MAX: "reduceMax",
                                 MIRInstrType.VREDUCE_MIN: "reduceMin",
                                 MIRInstrType.VREDUCE_MEAN: "reduceMean"}
                        op = op_map.get(instr.instr_type, "reduceSum")
                        lines.append(f"  const {instr.result} = {instr.operands[0]}.{op}();")
                    elif instr.instr_type == MIRInstrType.ADD:
                        lines.append(f"  const {instr.result} = {instr.operands[0]} + {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.SUB:
                        lines.append(f"  const {instr.result} = {instr.operands[0]} - {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.MUL:
                        lines.append(f"  const {instr.result} = {instr.operands[0]} * {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.DIV:
                        lines.append(f"  const {instr.result} = {instr.operands[0]} / {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.RETURN:
                        if func_name == "main":
                            lines.append("  return;")
                        else:
                            lines.append(f"  return {instr.value or 0};")
                    elif instr.instr_type == MIRInstrType.CALL:
                        args = ", ".join(instr.operands)
                        lines.append(f"  const {instr.result} = await {instr.metadata.get('func_name', 'unknown')}({args});")
                    elif instr.instr_type == MIRInstrType.SPAWN:
                        func = instr.metadata.get('func_name', 'unknown')
                        lines.append(f"  // spawn {func}")
                        lines.append(f"  (async () => {{ await {func}(); }})();")
                    elif instr.instr_type == MIRInstrType.SEND:
                        ch = instr.metadata.get('channel')
                        lines.append(f"  {ch}.send({instr.operands[0] if instr.operands else 0});")
                    elif instr.instr_type == MIRInstrType.RECV:
                        ch = instr.metadata.get('channel')
                        lines.append(f"  const {instr.result} = await {ch}.recv();")
                    elif instr.instr_type == MIRInstrType.CHANNEL_CREATE:
                        lines.append(f"  const {instr.result} = makeChannel();")
                    elif instr.instr_type == MIRInstrType.MUTEX_LOCK:
                        lines.append(f"  await {instr.metadata.get('mutex')}.lock();")
                    elif instr.instr_type == MIRInstrType.MUTEX_UNLOCK:
                        lines.append(f"  {instr.metadata.get('mutex')}.unlock();")

            lines.append("}")
            lines.append("")

        if self.mir.functions.get("main"):
            lines.append("// 启动主程序")
            lines.append("main().catch(console.error);")

        return "\n".join(lines)


# 便捷函数
def generate_js(mir_program: MIRProgram, out_dir: str, use_typescript: bool = True) -> CodegenResult:
    gen = JSGenerator(mir_program, out_dir, use_typescript)
    return gen.generate()
