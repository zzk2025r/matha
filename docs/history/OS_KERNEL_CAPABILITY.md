# Matha 操作系统内核构建能力

## 现状分析

Matha 此前已具备 OS **理论建模**能力（进程调度、内存管理、文件系统、死锁检测等数学公式），
但**缺少内核代码生成能力**——无法生成实际可编译的操作系统内核汇编代码。

## 新增能力

### 1. KernelGenerator（内核代码生成器）
**文件**: [src/codegen/kernel.py](file:///D:/trae/src/codegen/kernel.py)

生成完整的 x86 32-bit 操作系统内核汇编代码：
- **boot.asm**: 512 字节引导扇区（MBR 兼容），实模式 → 保护模式切换
  - GDT 初始化（代码段 + 数据段）
  - A20 地址线开启
  - CR0.PE 置位切换保护模式
  - 32 位段寄存器设置 + 栈指针
- **kernel.asm**: 内核核心骨架
  - IDT 初始化（异常 0x00、IRQ0 定时器、IRQ1 键盘、int 0x80 系统调用门）
  - Syscall 处理程序（跳转表）
  - VFS 根目录结构
  - TCB 任务表
  - 中断处理程序（irq0_handler, irq1_handler）
- **Makefile**: NASM + LD 构建脚本，支持 QEMU 运行

### 2. Kernel Math 领域模块
**文件**: [src/domains/kernel_math.py](file:///D:/trae/src/domains/kernel_math.py)

17 个数学函数，覆盖内核设计关键计算：

| 类别 | 函数 | 说明 |
|---|---|---|
| Syscall | `syscall_号` | Linux x86 32-bit syscall 号映射（40+ 个） |
| | `syscall_表大小` | syscall 表内存占用 |
| | `syscall_开销` | 用户态/kernel 态切换延迟 |
| PCB | `pcb_大小` | PCB 结构体大小（含寄存器快照） |
| | `pcb_分配` | 多任务 PCB 总内存 |
| | `pcb_切换周期` | 上下文切换时钟周期 |
| 内存 | `页表项数` | 两级页表总项数 |
| | `页表开销` | 页表结构自身内存 |
| | `线性地址` | 页号 × 页大小 + 偏移 |
| | `虚拟到物理` | 虚拟地址分解 |
| 中断 | `中断延迟` | IRQ 响应延迟（μs） |
| | `异常向量` | 25 种异常/中断名称 |
| 调度 | `调度滴答` | 时钟滴答开销 |
| | `切换开销` | 上下文切换总时间 |
| | `吞吐任务数` | 最大可调度任务数 |
| 布局 | `内核内存布局` | text/data/bss/stack 地址 |
| | `内核总内存` | 内核内存总量 |

### 3. 资源模块
**文件**: `matha/resource/os/`
- [boot_sector.matha](file:///D:/trae/matha/resource/os/boot_sector.matha) — 引导扇区公式
- [kernel_syscall.matha](file:///D:/trae/matha/resource/os/kernel_syscall.matha) — syscall 表和异常向量
- [kernel_process.matha](file:///D:/trae/matha/resource/os/kernel_process.matha) — PCB 和调度公式
- [kernel_memory.matha](file:///D:/trae/matha/resource/os/kernel_memory.matha) — 页表和内存管理公式

### 4. 测试覆盖
**文件**: [tests/test_kernel_codegen.py](file:///D:/trae/tests/test_kernel_codegen.py) — 39 个测试用例全部通过

## 使用方式

### Matha 脚本生成内核
```matha
【*/构建内核/*】生成 x86 32-bit 教学操作系统
内核规格 = ["内核", "MyOS", "MyOS", [
    ["系统名", "MyOS", [], []],
    ["内核版本", "0.1", [], []],
    ["系统调用", "write,read,exit,fork,mmap", [], []],
    ["页大小", "4096", [], []],
]]
#1：{#：[生成_内核 内核规格]}
```

生成产物：
- `boot.asm` — 引导扇区（2.8KB）
- `kernel.asm` — 内核核心（5.8KB）
- `Makefile` — 构建脚本（支持 nasm + ld + qemu）

### 构建为可运行内核
```bash
nasm -f bin boot.asm -o boot.bin
nasm -f elf32 kernel.asm -o kernel.o
ld -m elf_i386 -Ttext 0x10000 kernel.o -o kernel.bin
qemu-system-i386 -drive format=raw,file=boot.bin -m 64M
```

## 全量回归

- **测试套件**: 52/52 通过 ✓（+1 新增 kernel 测试）
- **性能基准**: 4/4 通过 ✓
- **零新增失败**
