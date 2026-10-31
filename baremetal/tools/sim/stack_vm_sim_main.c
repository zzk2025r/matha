/* tools/sim/stack_vm_sim_main.c — 宿主上驱动真实 hal/vm/stack_vm.c 的栈式引擎测试。
 *
 * 用 -DHAL_VM_SIM 把 panic 从「wfi 停机」改缝成 setjmp 捕获（sim 需要断言
 * panic 确实发生及其原因前缀），并对齐 allocator 先例注入静态区、不引用裸机
 * 链接符号。断言集覆盖：17 条 op 的正常语义、CALL/RET 平衡、负值（经 SUB 构造，
 * PUSH 的 operand 是 u16 无符号，直推造不出负数）、全部显式拒绝路径
 * （栈溢出/栈空/除零/INT_MIN/-1/代码越界/非法 op/mem 越界/环满）与看门狗 cap。
 * 编码口径：指令定宽 2 字（op + operand 各一字），跳转目标按字下标 ×2 计。
 * 诚实口径：行为级验证，不等于 RV32 固件实跑（后者走 build.ps1
 * 产 ELF + main.c 的 vm_selfcheck）。
 */
#include <stdio.h>
#include <string.h>
#include <setjmp.h>

#define HAL_VM_SIM 1
#include <hal/hal.h>

/* panic 捕获缝：stack_vm.c 的 sim 分支把 hal_vm_panic 宏接到本函数；
   记录 why 后 longjmp 回 run_program。*/
static jmp_buf    g_panic_jmp;
static char       g_panic_msg[64];
static uint32_t   g_panic_pc;

void sim_panic(const char *why, uint32_t pcval, const char *tag)
{
    (void)tag;
    snprintf(g_panic_msg, sizeof(g_panic_msg), "%s", why);
    g_panic_pc = pcval;
    longjmp(g_panic_jmp, 1);
}

/* sim 静态区（注入给 hal_vm_init_region，替代裸机 .bss 直连）。 */
static int32_t sim_stack[HAL_VM_STACK_WORDS];
static int32_t sim_mem[HAL_VM_MEM_WORDS];

static int g_pass, g_fail;

static void expect(int cond, const char *name)
{
    if (cond) { g_pass++; printf("  [ok  ] %s\n", name); }
    else      { g_fail++; printf("  [FAIL] %s\n", name); }
}

/* 装载并跑到 HALT；返回步数。panic 由调用前 setjmp 决定去向。 */
static uint32_t run_program(const uint16_t *code, uint32_t words, uint32_t cap)
{
    hal_vm_init_region(code, words, sim_stack, sim_mem, HAL_VM_MEM_WORDS);
    return hal_vm_run(cap);
}

static int panics(const uint16_t *code, uint32_t words, const char *why_prefix)
{
    if (setjmp(g_panic_jmp) == 0) {
        run_program(code, words, 10000u);
        return 0;                    /* 跑完了都没 panic = 不合格 */
    }
    return strncmp(g_panic_msg, why_prefix, strlen(why_prefix)) == 0;
}

#define PROG(name, ...)                                                    \
    static const uint16_t name[] = { __VA_ARGS__ };                        \
    static const uint32_t name##_words = sizeof(name) / sizeof(name[0])

/* 正常段守护运行：每条程序前独立 arm setjmp。若程序内 panic，只把本项记为
   FAIL（不读取残留输出环），继续跑下一条；绝不与 panics() 共用跳转目标，
   也不回到 main 顶部 setjmp 触发整条序列无限重启。依赖作用域内的 steps/expect。 */
#define RUN_GUARD(name, cond, label)                                       \
    do {                                                                   \
        int _panicked = (setjmp(g_panic_jmp) == 0)                         \
            ? (steps = run_program(name, name##_words, 1000u), 0)          \
            : (steps = 0u, 1);                                             \
        expect(!_panicked && (cond), (label));                             \
    } while (0)

/* ── 正常语义组（定宽 2 字：op,operand 成对；无操作数指令 operand 写 0）── */

/* (7+5)*3 = 36 */
PROG(p_arith,
    0x01,7, 0x01,5, 0x03,0, 0x01,3, 0x05,0,
    0x0e,0, 0x0f,0);

/* DIV 截断向零：20/6 = 3 -> OUT */
PROG(p_div,
    0x01,20, 0x01,6, 0x06,0, 0x0e,0, 0x0f,0);

/* SUB：20-6 = 14 -> OUT（顺带覆盖 SUB 正常路径） */
PROG(p_sub,
    0x01,20, 0x01,6, 0x04,0, 0x0e,0, 0x0f,0);

/* 负值须经 SUB 构造（PUSH operand 是 u16 无符号）：0-3 = -3; -3+5 = 2 -> OUT */
PROG(p_neg,
    0x01,0, 0x01,3, 0x04,0,
    0x01,5, 0x03,0,
    0x0e,0, 0x0f,0);

/* SWAP/DUP/POP 协同：PUSH 1、PUSH 2 → 底1 顶2；SWAP → 底2 顶1；DUP → 顶 1 1；
   POP 丢顶 → 顶 1；OUT 观测 1；POP 揭示 → 顶 2；OUT 观测 2；POP 清空。
   观测序列 [1,2]。 */
PROG(p_stack_ops,
    0x01,1,                     /* PUSH 1 */
    0x01,2,                     /* PUSH 2: 底1 顶2 */
    0x08,0,                     /* SWAP: 底1 顶2 -> 底2 顶1 */
    0x07,0,                     /* DUP:  顶 1 1 */
    0x02,0,                     /* POP 丢顶 -> 顶 1 */
    0x0e,0,                     /* OUT -> 观测 1 */
    0x02,0,                     /* POP -> 顶 2 */
    0x0e,0,                     /* OUT -> 观测 2 */
    0x02,0,                     /* POP 清空 */
    0x0f,0);

/* mem 往返：STORE mem[1]=7; STORE mem[2]=9; LOAD+LOAD=16 -> OUT */
PROG(p_mem,
    0x01,7,  0x11,1,
    0x01,9,  0x11,2,
    0x10,1,  0x10,2,  0x03,0,
    0x0e,0,  0x0f,0);

/* CALL/RET 平衡：主程 CALL w8（压返回址 w2）；sub 算 6*7=42 后 STORE mem[0]
   （弹掉结果，使返回址重新回到栈顶），RET 弹返回址回主程；主程 LOAD mem[0] OUT。
   （若 sub 直接把 42 留在栈上，RET 会误弹 42 当返回址——单栏 VM 的固有约定。） */
PROG(p_call,
    /* 0 */ 0x0c,8,             /* CALL -> w8（压返回址 w2） */
    /* 2 */ 0x10,0,             /* LOAD mem[0] -> 42 */
    /* 4 */ 0x0e,0,             /* OUT（子程序结果 42） */
    /* 6 */ 0x0f,0,             /* HALT */
    /* 8 */ 0x01,6,             /* sub: PUSH 6 */
    /*10 */ 0x01,7,             /*      PUSH 7 */
    /*12 */ 0x05,0,             /*      MUL -> 42 */
    /*14 */ 0x11,0,             /*      STORE mem[0]（弹 42，返回址复位栈顶） */
    /*16 */ 0x0d,0);            /*      RET -> w2 */

/* JZ/JNZ：PUSH 0 -> JZ 取真跳 w8（peek 不弹）；POP 掉 0 后 PUSH 1 ->
   JNZ 取真跳 w18；POP 1 后 PUSH 5 -> OUT -> HALT。死路分支（w4..w7、
   w14..w17）若被误走会多出 OUT 值，断言即红。跳转目标均按定宽 2 字
   的真实数组下标写（偶字），与 packed 布局逐字对齐。 */
PROG(p_branch,
    /* 0 */ 0x01,0,             /* PUSH 0 */
    /* 2 */ 0x0a,8,             /* JZ -> w8（真分支，peek 不弹） */
    /* 4 */ 0x01,99,            /* 死路 PUSH */
    /* 6 */ 0x0e,0,             /* 死路 OUT */
    /* 8 */ 0x02,0,             /* JZ 目标：POP 掉 0 */
    /*10 */ 0x01,1,             /* PUSH 1 */
    /*12 */ 0x0b,18,            /* JNZ -> w18（真分支） */
    /*14 */ 0x01,77,            /* 死路 PUSH */
    /*16 */ 0x0e,0,             /* 死路 OUT */
    /*18 */ 0x02,0,             /* JNZ 目标：POP 1 */
    /*20 */ 0x01,5,             /* PUSH 5 */
    /*22 */ 0x0e,0,             /* OUT 5 */
    /*24 */ 0x0f,0);            /* HALT */

/* ── 显式拒绝组（全部必须 panic）────────────────────────────────────────── */

PROG(r_div0,   0x01,5, 0x01,0, 0x06,0, 0x0f,0);
/* INT_MIN/-1 对：u16 PUSH 造不出负数，且非负 int32 相加/乘要到 -2^31 必然
   触发回绕——故 sim 构建带 -fwrapv 保证二补码回绕为定义行为。用
   32768 * (32768+32768) = 2^15 * 2^16 = 2^31 回绕成 INT_MIN；-1 经 0-1 构造；
   两值寄存 mem 后 LOAD 相除触发 division overflow。 */
PROG(r_divovf2,
    0x01,0x8000,                          /* PUSH 32768 */
    0x01,0x8000, 0x01,0x8000, 0x03,0,     /* 32768+32768 = 65536 */
    0x05,0,                               /* 32768*65536 -> 回绕 INT_MIN */
    0x11,1,                               /* STORE mem[1] = INT_MIN */
    0x01,0,  0x01,1,  0x04,0,             /* 0-1 = -1 */
    0x11,2,                               /* STORE mem[2] = -1 */
    0x10,1,  0x10,2,  0x06,0,             /* LOAD INT_MIN / LOAD -1 -> DIV panic */
    0x0f,0);
PROG(r_underflow, 0x01,5, 0x03,0, 0x0f,0);  /* ADD 弹两下，第二下空栈 */
PROG(r_illegal, 0x00,0x00);                 /* op=0 非法 */
PROG(r_illegal2, 0xFF,0x00);
PROG(r_codeoverrun, 0x01,1);                /* 无 HALT：PUSH 吃完后 fetch 越界 */
PROG(r_jumpoob, 0x09,100);                  /* JMP 到代码区外 */
PROG(r_retoob, 0x01,100, 0x0d,0);           /* RET 弹出 100（> 代码 4 字） */
/* 栈溢出：PUSH 1 后 DUP↔JMP 自环（JMP 回 DUP 所在 w2），每轮深 1，256 槽必溢出 */
PROG(r_stkovf,
    0x01,1,
    /*2*/ 0x07,0,   /* DUP */
    /*4*/ 0x09,2);  /* JMP -> w2（回到 DUP） */
/* mem 越界：LOAD 下标 9999（> 512） */
PROG(r_memoob, 0x10,9999, 0x0f,0);
/* 环满：PUSH 1 后 17 轮 DUP/OUT（OUT 不弹）；第 17 次 OUT 时 g_out_count==16
   先触发 out ring full（栈深此时仅 18，远未到 256 溢出） */
PROG(r_outring,
    0x01,1,
    0x07,0, 0x0e,0, 0x07,0, 0x0e,0, 0x07,0, 0x0e,0,
    0x07,0, 0x0e,0, 0x07,0, 0x0e,0, 0x07,0, 0x0e,0,
    0x07,0, 0x0e,0, 0x07,0, 0x0e,0, 0x07,0, 0x0e,0,
    0x07,0, 0x0e,0, 0x07,0, 0x0e,0, 0x07,0, 0x0e,0,
    0x07,0, 0x0e,0, 0x07,0, 0x0e,0, 0x07,0, 0x0e,0,
    0x07,0, 0x0e,0, 0x07,0, 0x0e,0,
    0x0f,0);

int main(void)
{
    /* 关 stdout 缓冲：挂死/终止时仍能保留已打印进度，便于定位卡住的用例。 */
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("=== stack_vm 宿主行为模拟（真实 hal/vm/stack_vm.c）===\n");

    /* longjmp 回来后自动变量不可靠：steps 取 volatile（C 标准对 setjmp 的要求）。 */
    volatile uint32_t steps;

    /* ── 正常语义（每项独立 setjmp 守护：panic 只红该项，不重启整条序列）── */
    {
        int _p = (setjmp(g_panic_jmp) == 0)
            ? (steps = run_program(p_arith, p_arith_words, 1000u), 0)
            : (steps = 0u, 1);
        expect(!_p && hal_vm_out_count() == 1 && hal_vm_out_get(0) == 36, "(7+5)*3 == 36");
        expect(!_p && steps == 7, "算术程序 7 指令到 HALT");
    }

    RUN_GUARD(p_div, hal_vm_out_count() == 1 && hal_vm_out_get(0) == 3,
              "DIV 截断向零: 20/6 == 3");

    RUN_GUARD(p_sub, hal_vm_out_count() == 1 && hal_vm_out_get(0) == 14,
              "SUB: 20-6 == 14");

    RUN_GUARD(p_neg, hal_vm_out_count() == 1 && hal_vm_out_get(0) == 2,
              "负值经 SUB 构造: (0-3)+5 == 2");

    RUN_GUARD(p_stack_ops,
              hal_vm_out_count() == 2 && hal_vm_out_get(0) == 1 && hal_vm_out_get(1) == 2,
              "SWAP/DUP/POP 序列 OUT == [1,2]");

    RUN_GUARD(p_mem, hal_vm_out_count() == 1 && hal_vm_out_get(0) == 16,
              "STORE/LOAD mem 往返: 7+9 == 16");

    RUN_GUARD(p_call, hal_vm_out_count() == 1 && hal_vm_out_get(0) == 42,
              "CALL/RET 平衡: 子程序 6*7 == 42");

    RUN_GUARD(p_branch, hal_vm_out_count() == 1 && hal_vm_out_get(0) == 5,
              "JZ(peek 不弹)/JNZ 双分支全走对路径");

    /* ── 显式拒绝 ── */
    expect(panics(r_div0, r_div0_words, "divide by zero"), "除零 panic");
    expect(panics(r_divovf2, r_divovf2_words, "division overflow"),
           "INT_MIN/-1（算术倍增构造）panic");
    expect(panics(r_underflow, r_underflow_words, "stack underflow"), "ADD 弹空 panic");
    expect(panics(r_illegal, r_illegal_words, "illegal opcode"), "op=0 非法 panic");
    expect(panics(r_illegal2, r_illegal2_words, "illegal opcode"), "op=0xFF 非法 panic");
    expect(panics(r_codeoverrun, r_codeoverrun_words, "code overrun"), "无 HALT 取指越界 panic");
    expect(panics(r_jumpoob, r_jumpoob_words, "jump out of code"), "JMP 越界 panic");
    expect(panics(r_retoob, r_retoob_words, "ret out of code"), "RET 弹坏返回址 panic");
    expect(panics(r_stkovf, r_stkovf_words, "stack overflow"), "循环 DUP 栈溢出 panic");
    expect(panics(r_memoob, r_memoob_words, "mem index OOB"), "mem 下标越界 panic");
    expect(panics(r_outring, r_outring_words, "out ring full"), "OUT 环满 panic");

    /* ── 看门狗：死循环 JMP 自己，cap 强制停 ── */
    {
        static const uint16_t spin[] = {0x09,0x00};
        steps = run_program(spin, sizeof(spin)/sizeof(spin[0]), 50u);
        expect(steps == 50, "看门狗 cap 强制停机（返回 50 步）");
    }

    /* ── 四字段契约：编译期锁在头文件按字宽分支；宿主 64 位含尾 pad=24 ── */
#if UINTPTR_MAX == 0xFFFFFFFFu
    expect(sizeof(hal_vm_ctx_t) == 16u, "ctx 四字段 16 字节（rv32 字宽）");
#else
    expect(sizeof(hal_vm_ctx_t) == 24u, "ctx 四字段 24 字节（宿主 64 位含 pad）");
#endif

    printf("结果：%s（通过 %d / 计入 %d）\n",
           g_fail == 0 ? "PASS" : "FAIL", g_pass, g_pass + g_fail);
    return g_fail == 0 ? 0 : 1;
}
