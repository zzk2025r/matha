/* hal/boot.h — crt0 与链接脚本之间的符号契约。 */
#ifndef HAL_BOOT_H
#define HAL_BOOT_H

#include <hal/types.h>

/* 这些符号由 baremetal/link.ld 提供、boot/crt0.S 消费：
     _estack   栈顶（RAM 末端）
     _sidata   .data 在 FLASH 中的加载镜像起点
     _sdata/_edata  .data 运行区间
     _sbss/_ebss    .bss 清零区间
     _heap_start/_heap_end  堆可用区间（第 3 步 allocator 读取） */
extern char _estack[];
extern char _sidata[], _sdata[], _edata[];
extern char _sbss[], _ebss[];
extern char _heap_start[], _heap_end[];

/* 裸机入口约定：crt0 完成最小环境后置好后调用 main()。
   main 不返回；若返回则 crt0 进入 wfi 死循环。 */
int main(void);

#endif /* HAL_BOOT_H */
