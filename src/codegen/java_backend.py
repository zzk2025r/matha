"""
JavaGenerator：把 Matha MIR 编译为 Java 代码（Maven/Gradle 可构建）。
支持：函数、算术、控制流、向量/矩阵、并发 Channel。
"""

from __future__ import annotations

from src.codegen.base import CodegenResult, Generator
from src.mir import MIRFunction, MIRInstrType, MIRProgram


class JavaGenerator(Generator):
    """Java 代码生成器：MIRProgram → .java 文件。"""

    def __init__(self, mir_program: MIRProgram, out_dir: str):
        self.mir = mir_program
        self.out_dir = out_dir
        class DummyApp:
            kind = "Java程序"
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
            # pom.xml
            pom_content = self._build_pom()
            files.append(self._write("pom.xml", pom_content))

            # 主类
            main_content = self._build_main()
            files.append(self._write(f"{self.app.name}.java", main_content))

            # MathaRT.java (运行时库)
            rt_content = self._build_runtime()
            self._write("MathaRT.java", rt_content)

        except Exception as e:
            return CodegenResult(成功=False, 类型="Java程序", 名称=self.app.name, 错误=str(e))

        return CodegenResult(
            成功=True, 类型="Java程序", 名称=self.app.name,
            文件=files, 入口=f"{self.app.name}.java",
        )

    def _build_pom(self) -> str:
        name = self.app.name.lower().replace(" ", "-")
        class_name = self.app.name
        return (
            f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            f"<project xmlns=\"http://maven.apache.org/POM/4.0.0\"\n"
            f"         xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"\n"
            f"         xsi:schemaLocation=\"http://maven.apache.org/POM/4.0.0\n"
            f"         http://maven.apache.org/xsd/maven-4.0.0.xsd\">\n"
            f"    <modelVersion>4.0.0</modelVersion>\n"
            f"\n"
            f"    <groupId>com.matha.generated</groupId>\n"
            f"    <artifactId>{name}</artifactId>\n"
            f"    <version>1.0.0</version>\n"
            f"    <packaging>jar</packaging>\n"
            f"\n"
            f"    <name>{class_name}</name>\n"
            f"    <description>Matha 生成的 Java 项目</description>\n"
            f"\n"
            f"    <properties>\n"
            f"        <maven.compiler.source>17</maven.compiler.source>\n"
            f"        <maven.compiler.target>17</maven.compiler.target>\n"
            f"        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>\n"
            f"    </properties>\n"
            f"\n"
            f"    <dependencies>\n"
            f"        <!-- 向量/矩阵运算 -->\n"
            f"        <dependency>\n"
            f"            <groupId>org.apache.commons</groupId>\n"
            f"            <artifactId>commons-math3</artifactId>\n"
            f"            <version>3.6.1</version>\n"
            f"        </dependency>\n"
            f"        <!-- 并发工具 -->\n"
            f"        <dependency>\n"
            f"            <groupId>com.google.guava</groupId>\n"
            f"            <artifactId>guava</artifactId>\n"
            f"            <version>32.1.2-jre</version>\n"
            f"        </dependency>\n"
            f"    </dependencies>\n"
            f"\n"
            f"    <build>\n"
            f"        <plugins>\n"
            f"            <plugin>\n"
            f"                <groupId>org.apache.maven.plugins</groupId>\n"
            f"                <artifactId>maven-compiler-plugin</artifactId>\n"
            f"                <version>3.11.0</version>\n"
            f"                <configuration>\n"
            f"                    <source>17</source>\n"
            f"                    <target>17</target>\n"
            f"                </configuration>\n"
            f"            </plugin>\n"
            f"            <plugin>\n"
            f"                <groupId>org.codehaus.mojo</groupId>\n"
            f"                <artifactId>exec-maven-plugin</artifactId>\n"
            f"                <version>3.1.0</version>\n"
            f"                <configuration>\n"
            f"                    <mainClass>{class_name}</mainClass>\n"
            f"                </configuration>\n"
            f"            </plugin>\n"
            f"        </plugins>\n"
            f"    </build>\n"
            f"</project>\n"
        )

    def _build_runtime(self) -> str:
        return (
            "// 由 Matha 生成的 Java 运行时库\n"
            "package matha;\n"
            "\n"
            "import org.apache.commons.math3.linear.*;\n"
            "import java.util.concurrent.*;\n"
            "import java.util.*;\n"
            "\n"
            "/**\n"
            " * Matha Java 运行时库\n"
            " */\n"
            "public class MathaRT {\n"
            "\n"
            "    // ===== 向量运算 =====\n"
            "\n"
            "    /** 创建零向量 */\n"
            "    public static double[] vecZeros(int n) {\n"
            "        return new double[n];\n"
            "    }\n"
            "\n"
            "    /** 从数组创建向量 */\n"
            "    public static double[] vecFrom(double... arr) {\n"
            "        return arr.clone();\n"
            "    }\n"
            "\n"
            "    /** 向量加法 */\n"
            "    public static double[] vecAdd(double[] a, double[] b) {\n"
            "        double[] r = new double[a.length];\n"
            "        for (int i = 0; i < a.length; i++) r[i] = a[i] + b[i];\n"
            "        return r;\n"
            "    }\n"
            "\n"
            "    /** 向量减法 */\n"
            "    public static double[] vecSub(double[] a, double[] b) {\n"
            "        double[] r = new double[a.length];\n"
            "        for (int i = 0; i < a.length; i++) r[i] = a[i] - b[i];\n"
            "        return r;\n"
            "    }\n"
            "\n"
            "    /** 向量点乘 */\n"
            "    public static double[] vecMul(double[] a, double[] b) {\n"
            "        double[] r = new double[a.length];\n"
            "        for (int i = 0; i < a.length; i++) r[i] = a[i] * b[i];\n"
            "        return r;\n"
            "    }\n"
            "\n"
            "    /** 向量点除 */\n"
            "    public static double[] vecDiv(double[] a, double[] b) {\n"
            "        double[] r = new double[a.length];\n"
            "        for (int i = 0; i < a.length; i++) r[i] = (b[i] != 0) ? a[i] / b[i] : 0;\n"
            "        return r;\n"
            "    }\n"
            "\n"
            "    /** 向量点积 */\n"
            "    public static double vecDot(double[] a, double[] b) {\n"
            "        double sum = 0;\n"
            "        for (int i = 0; i < a.length; i++) sum += a[i] * b[i];\n"
            "        return sum;\n"
            "    }\n"
            "\n"
            "    /** 向量求和 */\n"
            "    public static double vecReduceSum(double[] v) {\n"
            "        double sum = 0; for (double x : v) sum += x; return sum;\n"
            "    }\n"
            "\n"
            "    /** 向量最大值 */\n"
            "    public static double vecReduceMax(double[] v) {\n"
            "        double m = v[0]; for (int i = 1; i < v.length; i++) if (v[i] > m) m = v[i]; return m;\n"
            "    }\n"
            "\n"
            "    /** 向量最小值 */\n"
            "    public static double vecReduceMin(double[] v) {\n"
            "        double m = v[0]; for (int i = 1; i < v.length; i++) if (v[i] < m) m = v[i]; return m;\n"
            "    }\n"
            "\n"
            "    /** 向量平均值 */\n"
            "    public static double vecReduceMean(double[] v) {\n"
            "        return vecReduceSum(v) / v.length;\n"
            "    }\n"
            "\n"
            "    // ===== 矩阵运算 (使用 Apache Commons Math) =====\n"
            "\n"
            "    /** 创建零矩阵 */\n"
            "    public static RealMatrix matZeros(int rows, int cols) {\n"
            "        return new Array2DRowRealMatrix(rows, cols);\n"
            "    }\n"
            "\n"
            "    /** 矩阵乘法 */\n"
            "    public static RealMatrix matMul(RealMatrix a, RealMatrix b) {\n"
            "        return a.multiply(b);\n"
            "    }\n"
            "\n"
            "    /** 矩阵转置 */\n"
            "    public static RealMatrix matTranspose(RealMatrix m) {\n"
            "        return m.transpose();\n"
            "    }\n"
            "\n"
            "    // ===== 并发通道 =====\n"
            "\n"
            "    /**\n"
            "     * 泛型通道实现\n"
            "     * @param <T> 元素类型\n"
            "     */\n"
            "    public static class Channel<T> {\n"
            "        private final BlockingQueue<T> queue;\n"
            "        private volatile boolean closed = false;\n"
            "\n"
            "        public Channel() {\n"
            "            this.queue = new LinkedBlockingQueue<>();\n"
            "        }\n"
            "\n"
            "        public Channel(int capacity) {\n"
            "            this.queue = new ArrayBlockingQueue<>(capacity);\n"
            "        }\n"
            "\n"
            "        /** 发送元素 */\n"
            "        public void send(T value) throws InterruptedException {\n"
            "            if (closed) throw new IllegalStateException(\"Channel closed\");\n"
            "            queue.put(value);\n"
            "        }\n"
            "\n"
            "        /** 接收元素 */\n"
            "        public T recv() throws InterruptedException {\n"
            "            return queue.take();\n"
            "        }\n"
            "\n"
            "        /** 尝试接收（非阻塞） */\n"
            "        public T tryRecv() {\n"
            "            return queue.poll();\n"
            "        }\n"
            "\n"
            "        /** 关闭通道 */\n"
            "        public void close() {\n"
            "            closed = true;\n"
            "        }\n"
            "\n"
            "        public boolean isClosed() {\n"
            "            return closed;\n"
            "        }\n"
            "    }\n"
            "\n"
            "    /** 创建无界通道 */\n"
            "    public static <T> Channel<T> makeChannel() {\n"
            "        return new Channel<>();\n"
            "    }\n"
            "\n"
            "    /** 创建有界通道 */\n"
            "    public static <T> Channel<T> makeChannel(int capacity) {\n"
            "        return new Channel<>(capacity);\n"
            "    }\n"
            "\n"
            "    // ===== 同步原语 =====\n"
            "\n"
            "    /** 互斥锁 */\n"
            "    public static class Mutex {\n"
            "        private final ReentrantLock lock = new ReentrantLock();\n"
            "\n"
            "        public void lock() { lock.lock(); }\n"
            "        public void unlock() { lock.unlock(); }\n"
            "        public Lock getLock() { return lock; }\n"
            "    }\n"
            "\n"
            "    /** 条件变量 */\n"
            "    public static class CondVar {\n"
            "        private final Condition condition;\n"
            "        public CondVar(Mutex mutex) { this.condition = mutex.getLock().newCondition(); }\n"
            "        public void await() throws InterruptedException { condition.await(); }\n"
            "        public void signal() { condition.signal(); }\n"
            "        public void signalAll() { condition.signalAll(); }\n"
            "    }\n"
            "\n"
            "    // ===== 工具函数 =====\n"
            "\n"
            "    public static double[] vecZeros(int n) { return new double[n]; }\n"
            "\n"
            "    public static double[] vecFrom(double... arr) { return arr.clone(); }\n"
            "}\n"
        )

    def _build_main(self) -> str:
        class_name = self.app.name
        lines = [
            f"// 由 Matha 生成的 Java 主程序\n"
            f"import matha.MathaRT.*;\n"
            f"import org.apache.commons.math3.linear.*;\n"
            f"import java.util.concurrent.*;\n"
            f"\n"
            f"public class {class_name} {{\n"
        ]

        for func_name, func in self.mir.functions.items():
            if func_name == "main":
                lines.append("    public static void main(String[] args) {")
            else:
                params = ", ".join(f"double {p}" for p in func.params)
                lines.append(f"    public static double {func_name}({params}) {{")

            for instr in func.instructions:
                lines.append(f"        // {instr.instr_type.name if hasattr(instr, 'instr_type') else 'instr'}")
                if hasattr(instr, 'result') and instr.result:
                    if instr.instr_type == MIRInstrType.VLOAD:
                        lines.append(f"        double[] {instr.result} = vecZeros({instr.metadata.get('len', '0')});")
                    elif instr.instr_type in (MIRInstrType.VADD, MIRInstrType.VSUB, MIRInstrType.VMUL, MIRInstrType.VDIV):
                        op_map = {MIRInstrType.VADD: "vecAdd", MIRInstrType.VSUB: "vecSub",
                                 MIRInstrType.VMUL: "vecMul", MIRInstrType.VDIV: "vecDiv"}
                        op = op_map.get(instr.instr_type, "vecAdd")
                        lines.append(f"        double[] {instr.result} = {op}({instr.operands[0]}, {instr.operands[1]});")
                    elif instr.instr_type == MIRInstrType.VDOT:
                        lines.append(f"        double {instr.result} = vecDot({instr.operands[0]}, {instr.operands[1]});")
                    elif instr.instr_type == MIRInstrType.VMATMUL:
                        lines.append(f"        RealMatrix {instr.result} = matMul({instr.operands[0]}, {instr.operands[1]});")
                    elif instr.instr_type in (MIRInstrType.VREDUCE_SUM, MIRInstrType.VREDUCE_MAX,
                                             MIRInstrType.VREDUCE_MIN, MIRInstrType.VREDUCE_MEAN):
                        op_map = {MIRInstrType.VREDUCE_SUM: "vecReduceSum",
                                 MIRInstrType.VREDUCE_MAX: "vecReduceMax",
                                 MIRInstrType.VREDUCE_MIN: "vecReduceMin",
                                 MIRInstrType.VREDUCE_MEAN: "vecReduceMean"}
                        op = op_map.get(instr.instr_type, "vecReduceSum")
                        lines.append(f"        double {instr.result} = {op}({instr.operands[0]});")
                    elif instr.instr_type == MIRInstrType.ADD:
                        lines.append(f"        double {instr.result} = {instr.operands[0]} + {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.SUB:
                        lines.append(f"        double {instr.result} = {instr.operands[0]} - {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.MUL:
                        lines.append(f"        double {instr.result} = {instr.operands[0]} * {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.DIV:
                        lines.append(f"        double {instr.result} = {instr.operands[0]} / {instr.operands[1]};")
                    elif instr.instr_type == MIRInstrType.RETURN:
                        if func_name == "main":
                            lines.append("        return;")
                        else:
                            lines.append(f"        return {instr.value or 0.0};")
                    elif instr.instr_type == MIRInstrType.CALL:
                        args = ", ".join(instr.operands)
                        lines.append(f"        double {instr.result} = {instr.metadata.get('func_name', 'unknown')}({args});")
                    elif instr.instr_type == MIRInstrType.SPAWN:
                        func = instr.metadata.get('func_name', 'unknown')
                        lines.append(f"        // spawn {func}")
                        lines.append("        CompletableFuture.runAsync(() -> { try { " + func + "(); } catch (Exception e) {} });")
                    elif instr.instr_type == MIRInstrType.SEND:
                        ch = instr.metadata.get('channel')
                        lines.append(f"        {ch}.send({instr.operands[0] if instr.operands else 0});")
                    elif instr.instr_type == MIRInstrType.RECV:
                        ch = instr.metadata.get('channel')
                        lines.append(f"        double {instr.result} = {ch}.recv();")
                    elif instr.instr_type == MIRInstrType.CHANNEL_CREATE:
                        lines.append(f"        Channel<Double> {instr.result} = makeChannel();")
                    elif instr.instr_type == MIRInstrType.MUTEX_LOCK:
                        lines.append(f"        {instr.metadata.get('mutex')}.lock();")
                    elif instr.instr_type == MIRInstrType.MUTEX_UNLOCK:
                        lines.append(f"        {instr.metadata.get('mutex')}.unlock();")

            lines.append("    }")
            lines.append("}")

        return "\n".join(lines)


# 便捷函数
def generate_java(mir_program: MIRProgram, out_dir: str) -> CodegenResult:
    gen = JavaGenerator(mir_program, out_dir)
    return gen.generate()
