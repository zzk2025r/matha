/* hal/csr.h — RISC-V 机器模式 CSR 访问原语 + 宿主模拟接缝（第 3 步「接管中断」）。
 *
 * 与 mmio.h 对称：裸机构建走内联 csrr/csrs/csrc/csrw（仅 __riscv 下展开为汇编）；
 * 宿主「寄存器级模拟」构建定义 HAL_CSR_SIM，则只声明 extern 原型，由测试后端
 * （tools/sim/hal_csr_sim.c）把 CSR 读写接到一个模拟 CSR 堆上，从而在无硬件时
 * 验证 mtvec/mie/mstatus 的配置与陷入分派逻辑。
 *
 * 说明：RISC-V 的 CSR 地址须为汇编期立即数，故非模拟路径用「已知 CSR 的 switch」
 * 把运行期编号映射到各自的定长汇编指令。
 */
#ifndef HAL_CSR_H
#define HAL_CSR_H

#include <hal/types.h>

/* ── 机器模式 CSR 编号 ─────────────────────────────────────── */
#define HAL_CSR_MSTATUS 0x300u
#define HAL_CSR_MIE     0x3C0u
#define HAL_CSR_MTVEC   0x305u
#define HAL_CSR_MSCRATCH 0x340u
#define HAL_CSR_MEPC    0x341u
#define HAL_CSR_MCAUSE  0x342u
#define HAL_CSR_MTVAL   0x343u
#define HAL_CSR_MIP     0x344u

/* ── 关键位 ────────────────────────────────────────────────── */
#define MSTATUS_MIE     (1u << 3)     /* 全局机器模式中断使能 */
#define MIE_MSIE        (1u << 3)     /* 软件中断使能 */
#define MIE_MTIE        (1u << 7)     /* 定时器中断使能（CLINT mtimecmp） */
#define MIE_MEIE        (1u << 11)    /* 外部中断使能（PLIC） */
#define MIP_MTIP        (1u << 7)
#define MIP_MEIP        (1u << 11)

#ifdef HAL_CSR_SIM
extern uint32_t hal_csr_read(uint16_t csr);
extern void     hal_csr_write(uint16_t csr, uint32_t val);
extern void     hal_csr_set(uint16_t csr, uint32_t mask);
extern void     hal_csr_clr(uint16_t csr, uint32_t mask);
#else
static inline uint32_t hal_csr_read(uint16_t csr)
{
    uint32_t v = 0u;
#if defined(__riscv)
    switch (csr) {
    case HAL_CSR_MSTATUS: __asm__ volatile("csrr %0, mstatus"  : "=r"(v)); break;
    case HAL_CSR_MIE:     __asm__ volatile("csrr %0, mie"      : "=r"(v)); break;
    case HAL_CSR_MTVEC:   __asm__ volatile("csrr %0, mtvec"    : "=r"(v)); break;
    case HAL_CSR_MSCRATCH:__asm__ volatile("csrr %0, mscratch" : "=r"(v)); break;
    case HAL_CSR_MEPC:    __asm__ volatile("csrr %0, mepc"     : "=r"(v)); break;
    case HAL_CSR_MCAUSE:  __asm__ volatile("csrr %0, mcause"   : "=r"(v)); break;
    case HAL_CSR_MTVAL:   __asm__ volatile("csrr %0, mtval"    : "=r"(v)); break;
    case HAL_CSR_MIP:     __asm__ volatile("csrr %0, mip"      : "=r"(v)); break;
    default: break;
    }
#else
    (void)csr;
#endif
    return v;
}

static inline void hal_csr_write(uint16_t csr, uint32_t val)
{
#if defined(__riscv)
    switch (csr) {
    case HAL_CSR_MSTATUS: __asm__ volatile("csrw mstatus,  %0" :: "r"(val)); break;
    case HAL_CSR_MIE:     __asm__ volatile("csrw mie,      %0" :: "r"(val)); break;
    case HAL_CSR_MTVEC:   __asm__ volatile("csrw mtvec,    %0" :: "r"(val)); break;
    case HAL_CSR_MSCRATCH:__asm__ volatile("csrw mscratch, %0" :: "r"(val)); break;
    case HAL_CSR_MEPC:    __asm__ volatile("csrw mepc,     %0" :: "r"(val)); break;
    case HAL_CSR_MCAUSE:  __asm__ volatile("csrw mcause,   %0" :: "r"(val)); break;
    case HAL_CSR_MTVAL:   __asm__ volatile("csrw mtval,    %0" :: "r"(val)); break;
    case HAL_CSR_MIP:     __asm__ volatile("csrw mip,      %0" :: "r"(val)); break;
    default: break;
    }
#else
    (void)csr; (void)val;
#endif
}

static inline void hal_csr_set(uint16_t csr, uint32_t mask)
{
#if defined(__riscv)
    switch (csr) {
    case HAL_CSR_MSTATUS: __asm__ volatile("csrs mstatus, %0" :: "r"(mask)); break;
    case HAL_CSR_MIE:     __asm__ volatile("csrs mie,     %0" :: "r"(mask)); break;
    case HAL_CSR_MTVEC:   __asm__ volatile("csrs mtvec,   %0" :: "r"(mask)); break;
    case HAL_CSR_MEPC:    __asm__ volatile("csrs mepc,    %0" :: "r"(mask)); break;
    case HAL_CSR_MIP:     __asm__ volatile("csrs mip,     %0" :: "r"(mask)); break;
    default: break;
    }
#else
    (void)csr; (void)mask;
#endif
}

static inline void hal_csr_clr(uint16_t csr, uint32_t mask)
{
#if defined(__riscv)
    switch (csr) {
    case HAL_CSR_MSTATUS: __asm__ volatile("csrc mstatus, %0" :: "r"(mask)); break;
    case HAL_CSR_MIE:     __asm__ volatile("csrc mie,     %0" :: "r"(mask)); break;
    case HAL_CSR_MTVEC:   __asm__ volatile("csrc mtvec,   %0" :: "r"(mask)); break;
    case HAL_CSR_MEPC:    __asm__ volatile("csrc mepc,    %0" :: "r"(mask)); break;
    case HAL_CSR_MIP:     __asm__ volatile("csrc mip,     %0" :: "r"(mask)); break;
    default: break;
    }
#else
    (void)csr; (void)mask;
#endif
}
#endif /* HAL_CSR_SIM */

#endif /* HAL_CSR_H */
