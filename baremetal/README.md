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
  main.c                  最直 freestanding 入口（hal_init → uart_puts）
  include/hal/            HAL 契约头（对外只暴露这些）
    types.h  mmio.h  arch.h  boot.h  uart.h  mem.h  irq.h  hal.h(伞头)
  boot/                   启动与陷入（架构相关，汇编）
    crt0.S                栈/数据拷贝/BSS 清零 → call main
    vector.S              机器模式陷阱向量入口（第 3 步接管）
  hal/                    分层实现（可移植 C）
    drivers/uart.c        控制台串口（第 2 步落点）
    mem/allocator.c       内存分配器（第 3 步落点）
    trap/trap.c           中断/异常处理（第 3 步落点）
  tools/check_skeleton.py 骨架结构 + 宿主 gcc 语法门禁
```

## 分层依赖（自底向上）

`arch`（常量/内存映射）→ `mmio`（寄存器访问）→ `boot`（crt0 契约）→
`uart`（输出，第 2 步）→ `mem` / `irq`（接管内存与中断，第 3 步）。

## P5 路线（对应用户三步）

1. **搭建原生编译的 HAL 层目录骨架** —— 本目录（已完成）。
2. **实现串口等最基础输出** —— 校准 UART0 分频/FIFO，在实板或 QEMU 上打印
   `main.c` 的启动横幅（骨架已接通 API，尚未上板验证）。
3. **逐步接管内存与中断** —— `mem/allocator.c` 换成可回收分配器；`boot/vector.S`
   + `trap/trap.c` 接管 mtvec/mcause，接 CLINT 定时器与 PLIC 外设中断。

## 本机验证状态（诚实口径）

- **可验证**：`make check`（或 `python tools/check_skeleton.py`）——
  结构自洽 + 宿主 `gcc -fsyntax-only` 证明整套 freestanding C 地基能被编译器接受。
- **尚不可验证**：真正烧到 FE310 / 在 QEMU 上跑起来。本机**未安装** RISC-V 交叉
  工具链（`riscv64-unknown-elf-gcc`）与 QEMU，`make all` 会如实降级为「仅骨架校验」。
  需先安装交叉工具链（+ 可选 QEMU）后 `make firmware` 才产出 `matha_hal.elf/.bin`。
- 「原生编译」当前口径 = **freestanding C/asm HAL**（与既有 `link.ld`/`entry.S` 同源）。
  Matha 字节码 → RV 机器码的直发后端是更远目标（现有 `src/mbc/native.py` 仅出
  Windows PE / x86-64），不在本骨架范围。

## 与遗留裸机文件的关系

仓库根 `link.ld`、`src/entry.S`、`src/main.c` 等是**遗留散件**（其中 `src/main.c`
含模板双花括号与 libc 依赖，且根 `Makefile` 引用的 `scripts/riscv_embedded_demo.py`
等生成脚本已缺失）。P5 第 1 步遵循**只增不改**：本目录全新创建干净骨架，遗留文件
原样保留；待骨架在第 2、3 步跑通、验证全绿后，再统一 `git rm` 旧散件。
