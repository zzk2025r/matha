/* tools/sim/allocator_sim_main.c — 宿主上驱动真实 hal/mem/allocator.c 的分配器测试。
 *
 * 用 -DHAL_MEM_SIM_HEAP 让 hal_mem_init 消费一块静态堆（不引用裸机链接符号），
 * 证明可回收分配器的关键行为：first-fit、8 字节对齐、释放后复用、相邻空闲块
 * 合并（释放全部后 avail 复原）、超大分配返回 NULL。
 */
#include <stdio.h>
#include <stdint.h>

#define HAL_MEM_SIM_HEAP 1
#include <hal/hal.h>

/* allocator.c 在 HAL_MEM_SIM_HEAP 下读取这两个全局作为堆来源。 */
static _Alignas(16) char sim_heap[4096];
char      *g_hal_sim_heap_base = sim_heap;
hal_size_t g_hal_sim_heap_size = sizeof(sim_heap);

static int g_fails;
static void cond(const char *n, int c) { if (c) printf("  [ok]   %s\n", n); else { printf("  [FAIL] %s\n", n); g_fails++; } }

int main(void)
{
    printf("=== 可回收分配器 宿主行为模拟 ===\n");

    hal_mem_init();
    hal_size_t avail0 = hal_mem_avail();
    cond("堆就绪，初始 avail 接近整块（≈4096）", avail0 >= 4000u && avail0 <= sizeof(sim_heap));

    void *a = hal_malloc(100u), *b = hal_malloc(100u), *c = hal_malloc(100u);
    cond("三次分配均非空", a && b && c);
    cond("分配互不重叠", a != b && b != c && a != c);
    cond("分配指针 8 字节对齐",
         (((uintptr_t)a | (uintptr_t)b | (uintptr_t)c) % 8u) == 0u);
    cond("分配后 avail 下降", hal_mem_avail() < avail0);

    /* 释放中间块 b，再申请更小的 d → first-fit 应复用 b 的空闲块。 */
    hal_free(b);
    void *d = hal_malloc(50u);
    cond("释放后被更小的分配复用（d == 原 b）", d == b);

    /* 全部释放并合并：avail 应复原到接近初始（证明相邻空闲块合并）。 */
    hal_free(a); hal_free(c); hal_free(d);
    hal_size_t availf = hal_mem_avail();
    cond("全部释放合并后 avail 复原", availf + 16u >= avail0);

    /* 回收生效：合并后可再容纳一次接近整堆的大分配。 */
    void *big = hal_malloc(avail0 - 32u);
    cond("释放后可再完成一次大分配（回收生效）", big != NULL);
    if (big) { hal_free(big); }

    /* 超出堆容量：返回 NULL（裸机无 OOM 处理，交由上层判 NULL）。 */
    cond("超大分配返回 NULL", hal_malloc(1u << 20) == NULL);

    if (g_fails == 0) {
        printf("结果：分配器寄存器级模拟全部通过（真实 allocator.c）\n");
        return 0;
    }
    printf("结果：分配器模拟失败 %d 项\n", g_fails);
    return 1;
}
