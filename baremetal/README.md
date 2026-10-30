# baremetal — Matha P5「脱离宿主 OS」裸机 HAL

本目录是 Matha 走向**自持裸机运行**的地基骨架：一条不依赖 Python 宿主、不依赖
任何操作系统 libc/运行时、直接面向 SiFive FE310（RISC-V rv32imac）的最直路径。

> 本目录与仓库 Python 主线（`src/`、`scripts/check.py` 六项门禁）**完全隔离**：
> 不进入 `repo_facts` 任何统计口径，不被 `dep_audit` / `kernel_purity` 扫描，
> 不新增 `tests/` 用例。现有门禁逐字节不受影响。

## 目录骨架

```
baremetal/
  link.ld                 FE310 内存映射 + 段/堆栈符号（FLASH 取指、RAM 数据）
  Makefile                独立构建：make check（本机可跑）/ make firmware（需交叉工具链）
  build.ps1               Windows/PowerShell 一键构建入口（无 make 时产出 matha_hal.elf）
  main.c                  最直 freestanding 入口（hal_init → uart_puts）
  include/hal/            HAL 契约头（对外只暴露这些）
    types.h  mmio.h  arch.h  boot.h  uart.h  mem.h  irq.h  csr.h  hal.h(伞头)
  boot/                   启动与陷入（架构相关，汇编）
    crt0.S                栈/数据拷贝/BSS 清零 → call main
    vector.S              机器模式陷阱向量入口（真 trapframe 保存/恢复 → call hal_trap_handler → mret；仅交叉编译验证）
  hal/                    分层实现（可移植 C）
    drivers/uart.c        控制台串口驱动（第 2 步：分频校准 + 收发，已完成）
    mem/allocator.c       内存分配器（第 3 步：可回收 first-fit + 分裂 + 相邻合并，已完成）
    trap/trap.c           中断/异常处理（第 3 步：mtvec/mie/mstatus + 定时器重装 + PLIC claim/complete，已完成）
  tools/                  宿主侧验证工具（非裸机、非门禁 C 源）
    check_skeleton.py     骨架结构 + 宿主 gcc 语法门禁 + 触发全部寄存器级/行为模拟
    run_uart_sim.py       用宿主 gcc 编译真实 uart.c + 模拟后端并跑寄存器级测试
    run_mem_sim.py        用宿主 gcc 编译真实 allocator.c + 测试驱动跑回收行为断言
    run_trap_sim.py       用宿主 gcc 编译真实 trap.c + CSR/MMIO 后端跑中断接管断言
    sim/hal_mmio_sim.c    FE310 SiFive UART 寄存器堆模型（MMIO 接缝后端）
    sim/uart_sim_main.c   分频/发送/接收逐字节断言
    sim/hal_platform_sim.c FE310 CSR + CLINT + PLIC 模型（CSR/MMIO 接缝后端）
    sim/trap_sim_main.c   mtvec/mie/mstatus + 定时器重装 + PLIC claim/complete 断言
    sim/allocator_sim_main.c first-fit/对齐/复用/合并/超大返回 NULL 断言
```

## 分层依赖（自底向上）

`arch`（常量/内存映射）→ `mmio`（寄存器访问）→ `boot`（crt0 契约）→
`uart`（输出，第 2 步）→ `mem` / `irq`（接管内存与中断，第 3 步）。

## P5 路线（对应用户三步）

1. **搭建原生编译的 HAL 层目录骨架** —— 本目录（已完成）。
2. **实现串口等最基础输出** —— 已完成：`hal/drivers/uart.c` 是完整可用的 FE310
   SiFive UART 驱动（分频校准 + txdata/rxdata 轮询收发，putc/puts/getc/read/write）。
   关键事实：SiFive UART 块内**无** divisor 寄存器，波特率 = `uart_clk/16`（PRCI 产生
   uart_clk），故「分频校准」据 CPU_FREQ_HZ 算出整数分频值供板级写 PRCI，不臆测字段
   偏移写硬件。行为已在**宿主寄存器级模拟**（`tools/run_uart_sim.py`）逐字节验证通过。
3. **逐步接管内存与中断** —— 已完成：`mem/allocator.c` 换成可回收分配器（first-fit +
   块分裂 + 相邻空闲块双向合并，free 后内存可复用）；`boot/vector.S` + `trap/trap.c`
   接管 mtvec/mcause，按 mcause 分派机器模式软件/定时器/外部中断，接 CLINT 定时器（写
   mtimecmp 重装清 MTIP）与 PLIC 外设中断（claim 取源号→路由 ISR→complete 写回）。CSR
   访问走 `include/hal/csr.h` 的 `HAL_CSR_SIM` 接缝（对称于 mmio.h）；行为已在宿主寄存器级
   模拟（`tools/run_mem_sim.py` 回收 9 项、`tools/run_trap_sim.py` 中断 13 项）逐条验证通过。

## 构建

产出裸机固件有两条等价入口，编译/链接参数逐字一致
（`-march=rv32imac_zicsr -mabi=ilp32 -Os -ffreestanding -nostdlib -Wall -Wextra -Iinclude`；
链接走交叉 gcc 驱动、`-T link.ld -Wl,--nmagic`）：

- **make（类 Unix / 已装 make 时）**，在 `baremetal/` 下：
  - `make check` —— 结构校验 + 宿主 `gcc -fsyntax-only`（本机无需交叉工具链）。
  - `make sim` —— 跑 `tools/` 下 uart/mem/trap 三套宿主模拟。
  - `make firmware` —— 有交叉工具链时真正链出 `build/matha_hal.elf` + `.bin`。
  - `make all` / `make clean` —— 校验+（降级或）产固件 / 清理 `build/`。

- **PowerShell（Windows：无 make、系统默认 gcc 编不了 RISC-V 时）**，在 `baremetal\` 下：

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\build.ps1
  ```

  自动收集源码并交叉编译链接，一键产出 `build\matha_hal.elf`（并 `objcopy` 出 `.bin`）。
  可选参数：
  - `-CrossGcc <路径>` —— 自动探测（先 PATH 再常见安装目录）失败时手动指定交叉编译器；
    `objcopy`/`size` 由编译器同目录按前缀推导。
  - `-SkipBin` —— 只出 ELF，不生成 `.bin`。

  > 脚本**刻意排除 `tools/`**：那里是宿主侧 UART/内存/中断模拟（用本机 gcc 跑、非裸机
  > C 源），绝不能混进 RV32 固件，否则链接必炸；同时排除 `build/`（编译产物）。它自动
  > 收集 baremetal 根下全部 `.c` 与 `boot\*.S`，对象保留相对子路径避免同名冲突，每次
  > 全量重建前清空 `obj\`。与 `make firmware` 产出逐字节等价。

## 本机验证状态（诚实口径）

- **已通过**：
  - `python tools/check_skeleton.py`（或 `make check`）——结构自洽 + 宿主
    `gcc -fsyntax-only` 证明整套 freestanding C 地基可被编译器接受。
  - `python tools/run_uart_sim.py`（或 `make sim`）——**真实 `uart.c`** 接模拟寄存器堆，
    分频校准 + TX/RX 逐字节断言全过（无真硬件、不依赖 QEMU）。
  - `python tools/run_mem_sim.py`——**真实 `allocator.c`**（`-DHAL_MEM_SIM_HEAP`）接静态堆
    驱动，first-fit / 8 字节对齐 / 释放复用 / 相邻合并后 avail 复原 / 超大返回 NULL 共 9 项全过。
  - `python tools/run_trap_sim.py`——**真实 `trap.c`**（`-DHAL_MMIO_SIM -DHAL_CSR_SIM`）接
    CSR/CLINT/PLIC 模型，mtvec/mie/mstatus 配置、定时器重装 mtimecmp、PLIC claim→路由→
    complete、未知源/软件中断不崩溃共 13 项全过（vector.S 为纯汇编不在此执行）。
  - 交叉编译产固件：xPack `riscv-none-elf-gcc` 15.2.0（rv32imac_zicsr/ilp32）零警告编译
    `main/uart/allocator/trap` + `crt0.S/vector.S`，由交叉 gcc 驱动链出 `matha_hal.elf`
    （ELF32 / RISC-V / EXEC / 入口 `_start`@0x20000000）并 `objcopy` 出 `.bin`。注：现代
    binutils 把 CSR 拆为独立扩展 `zicsr`，故 -march 需显式带 `_zicsr`（否则报 `csrr ... zicsr
    required`）；链接走 gcc 驱动而非裸 `ld`（裸 ld 的 `-m` 是仿真模式、不接受 -march/-mabi）。
- **未做（诚实）**：未在真 FE310 板上实测串口时序；未把固件跑进 QEMU 看串口输出——
  标准 QEMU 无 FE310 机器，`-machine virt` 的 UART 是 ns16550@0x10000000，与本驱动
  UART0@0x10013000 不匹配。上板/QEMU 串口回环属真硬件联调，另计。同样，`vector.S` 的
  trapframe 保存/恢复与 mret 仅靠交叉编译进 RV32 ELF 证明可汇编/链接，未在真硬件上跑过
  一次实际中断（宿主无法执行 RISC-V 汇编，已在 C 层 `hal_trap_handler` 验证行为）。
- 「原生编译」当前口径 = **freestanding C/asm HAL**。Matha 字节码 → RV 机器码的
  直发后端是更远目标（现有 `src/mbc/native.py` 仅出 Windows PE / x86-64），不在本骨架范围。

## 与遗留裸机文件的关系

仓库根 `link.ld`、`src/entry.S`、`src/main.c` 等是**遗留散件**（其中 `src/main.c`
含模板双花括号与 libc 依赖，且根 `Makefile` 引用的 `scripts/riscv_embedded_demo.py`
等生成脚本已缺失）。P5 第 1 步遵循**只增不改**：本目录全新创建干净骨架，遗留文件
原样保留；待骨架在第 2、3 步跑通、验证全绿后，再统一 `git rm` 旧散件。
