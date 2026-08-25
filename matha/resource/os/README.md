# Matha 操作系统内核资源库

## 概述

本目录包含操作系统内核开发相关的数学模型和代码模板，
用于辅助学习和生成 x86 操作系统内核汇编代码。

## 资源文件说明

### boot_sector.matha
引导扇区设计公式：
- 512 字节 MBR 布局（boot code + signature）
- 实模式 → 保护模式切换步骤
- GDT 描述符结构（代码段/数据段）

### kernel_syscall.matha
系统调用表设计：
- syscall number 映射（Linux x86 32-bit 约定）
- syscall table 大小估算
- 系统调用延迟模型（用户态→内核态切换开销）

### kernel_process.matha
进程管理数学模型：
- PCB（进程控制块）大小计算
- 上下文切换时钟周期估算
- 最大吞吐任务数

### kernel_memory.matha
内存管理数学模型：
- 页表项数计算（两级页表）
- 页表结构自身内存开销
- 虚拟地址 → 物理地址转换
- 内核内存布局（text/data/bss/stack）

## 使用方式

在 Matha 脚本中引用：
```
# 加载资源
加载 "resource/os/boot_sector.matha"
加载 "resource/os/kernel_syscall.matha"

# 使用公式
syscall_num("write")  → 返回 4
pcb_大小(18, 4096)    → 返回 PCB 字节数
页表项数(4096, 64MB)  → 返回所需页表项数
```

或通过代码生成器：
```
["内核", "MyOS", "MyOS", [
  ["系统名", "MyOS", [], []],
  ["内核版本", "0.1", [], []],
  ["系统调用", "write,read,exit,fork", [], []],
]]
#：{#：[生成_内核 MyOS]}
```
