/* baremetal/main.c — Matha 裸机 HAL 的最小 freestanding 入口（无 libc / 无 OS）。
 *
 * 第 1 步（骨架）：验证 boot → hal_init → uart_puts 这条不依赖宿主 OS 的
 *   最直路径可编译链接。串口真正在实板/QEMU 上打出文字是第 2 步的目标。
 */
#include <hal/hal.h>

static void busy_delay(volatile uint32_t n)
{
    while (n--) {
        /* 粗略空转：第 3 步接管 CLINT mtime 后换成基于定时器的精确延时。 */
    }
}

int main(void)
{
    hal_init(115200u);

    uart_puts("\r\n");
    uart_puts("Matha bare-metal HAL skeleton (P5)\r\n");
    uart_puts("boot -> hal_init -> uart : OK\r\n");

    for (;;) {
        uart_puts("hal alive\r\n");
        busy_delay(1000000u);
    }

    return 0;   /* 不可达：裸机 main 永不返回 */
}
