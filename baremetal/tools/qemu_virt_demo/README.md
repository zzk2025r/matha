# qemu_virt_demo — stock QEMU 上实跑的「中断接管」常驻样例

真实固件 `matha_hal.elf`（FE310：FLASH@0x20000000 取指 + SiFive UART@0x10013000）
跑不进 stock QEMU——标准 QEMU 没有 FE310 机器。但 `-machine virt` 的 **CLINT 基址
0x02000000 与 FE310 一致**，于是这里做一个 **board-matched 变体**：只把 UART 换成
ns16550@0x10000000、内存换成 virt RAM@0x80000000，其余中断接管链路与生产 HAL 同构：

```
装 mtvec → 开 MTIE + MSTATUS.MIE → CLINT mtimecmp 定时器中断
→ trap 入口判 mcause=0x80000007 → 调 C ISR 打印 tick → 重装 mtimecmp → mret
```

这在 QEMU 上**真跑 RV32 指令**（软件模拟 CPU），区别于 `../sim/` 那种用宿主 gcc 编译
真实 HAL C 源再跑的 C 行为模拟。

## 文件

- `virt_demo.c`        演示主体（ns16550 打印 + CLINT 定时器 + 精简 trap 汇编 + 两阶段验证）
- `virt_start.S`       极简入口：设栈顶 → `call main`
- `virt.ld`            virt 内存映射（text/data/bss 全落 RAM，栈顶 0x80100000）
- `run_qemu_virt_demo.py`  交叉编译 + 跑 QEMU + 断言三信号的运行器

## 运行

```bash
python run_qemu_virt_demo.py
# 工具链 / QEMU 不在 PATH 时手动指定（也可用环境变量 RISCV_CC / QEMU）：
python run_qemu_virt_demo.py --cc <riscv-none-elf-gcc> --qemu <qemu-system-riscv32>
```

预期串口输出：`mie=...0080`（MTIE 已置）、`mip=... MTIP?Y`（定时器 pending）、
`armed, waiting IRQ`、随后持续 `tick N`。运行器断言三信号齐备则 `PASS`。

退出码：`0` 通过 / `1` 失败 / `2` 缺交叉工具链或缺 QEMU 时**如实 SKIP**（不算失败）。
产物 ELF 落在 `baremetal/build/qemu_virt_demo/`（已 gitignore）。

## 诚实口径

证明的是「中断接管路径可被真 RV32 指令集在 QEMU 上执行」，**不等于在真 FE310 板上
实测**；CSR 访问一律用符号名（数值 + `"i"` 约束在本工具链上会静默不生效）。
