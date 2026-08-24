/*
 * Matha 嵌入式项目模板 — RISC-V (SiFive FE310)
 * 功能: GPIO 控制 + PWM 电机调速 + I2C 温度传感器
 * 生成时间: 2026-08-23
 *
 * 硬件连接:
 *   - GPIO0: 按钮输入 (启动/停止)
 *   - GPIO1: LED 指示灯
 *   - GPIO2: 电机使能
 *   - PWM0: 电机速度控制
 *   - I2C0: ADS1115 温度传感器 (地址 0x48)
 */

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>

/* ========== 硬件定义 ========== */
#define GPIO_BASE       0x40001000UL
#define PWM_BASE        0x40018000UL
#define I2C_BASE        0x40003000UL
#define UART_BASE       0x40000000UL

/* GPIO 寄存器 */
#define GPIO_OUTPUT     (*(volatile uint32_t *)(GPIO_BASE + 0x00))
#define GPIO_INPUT      (*(volatile uint32_t *)(GPIO_BASE + 0x04))
#define GPIO_ENABLE     (*(volatile uint32_t *)(GPIO_BASE + 0x08))
#define GPIO_DIR        (*(volatile uint32_t *)(GPIO_BASE + 0x0C))

/* 引脚定义 */
#define PIN_BUTTON      0
#define PIN_LED         1
#define PIN_MOTOR_EN    2
#define PIN_MOTOR_PWM   3

/* 电机控制参数 */
#define MOTOR_PWM_FREQ  20000UL    /* 20kHz PWM 频率 */
#define MOTOR_MAX_SPEED 100        /* 最大速度百分比 */
#define MOTOR_STOP      0
#define MOTOR_FORWARD   1
#define MOTOR_REVERSE   -1

/* 温度传感器参数 */
#define ADS1115_ADDR    0x48
#define TEMP_SAMPLE_MS  1000       /* 温度采样间隔 */

/* ========== GPIO 驱动 ========== */

void gpio_init(void) {{
    /* 设置引脚方向 */
    GPIO_DIR |= (1 << PIN_BUTTON) | (1 << PIN_LED) |
                (1 << PIN_MOTOR_EN) | (1 << PIN_MOTOR_PWM);
    /* 使能输出 */
    GPIO_ENABLE |= (1 << PIN_LED) | (1 << PIN_MOTOR_EN) | (1 << PIN_MOTOR_PWM);
    /* 初始状态: LED 灭, 电机停 */
    GPIO_OUTPUT &= ~(1 << PIN_LED);
    GPIO_OUTPUT &= ~(1 << PIN_MOTOR_EN);
}}

bool gpio_read(int pin) {{
    return (GPIO_INPUT >> pin) & 1;
}}

void gpio_set(int pin, int value) {{
    if (value)
        GPIO_OUTPUT |= (1 << pin);
    else
        GPIO_OUTPUT &= ~(1 << pin);
}}

void gpio_toggle(int pin) {{
    GPIO_OUTPUT ^= (1 << pin);
}}

/* ========== PWM 电机驱动 ========== */

typedef struct {{
    uint32_t freq;
    uint32_t period;
    uint32_t duty;
    int8_t   direction;
    bool     running;
}} MotorController;

MotorController motor;

void motor_init(void) {{
    motor.freq = MOTOR_PWM_FREQ;
    motor.period = 1000000 / MOTOR_PWM_FREQ;  /* 周期(微秒) */
    motor.duty = 0;
    motor.direction = 0;
    motor.running = false;

    /* 配置 PWM 外设 */
    *(volatile uint32_t *)(PWM_BASE + 0x00) = motor.period;  /* 周期寄存器 */
    *(volatile uint32_t *)(PWM_BASE + 0x04) = 0;             /* 占空比 = 0 */
    *(volatile uint32_t *)(PWM_BASE + 0x08) = 1;             /* 使能 PWM */
}}

void motor_set_speed(int8_t direction, uint8_t percent) {{
    if (percent > 100) percent = 100;
    if (percent == 0) {{
        motor.duty = 0;
        motor.direction = 0;
        motor.running = false;
        gpio_set(PIN_MOTOR_EN, 0);
        return;
    }}

    motor.direction = direction;
    motor.duty = (uint32_t)((float)percent / 100.0 * motor.period);
    motor.running = true;
    gpio_set(PIN_MOTOR_EN, 1);

    /* 更新 PWM 寄存器 */
    *(volatile uint32_t *)(PWM_BASE + 0x04) = motor.duty;

    /* 方向控制 (通过 GPIO 切换 H 桥方向引脚) */
    gpio_set(PIN_MOTOR_PWM, (direction == MOTOR_REVERSE) ? 1 : 0);

    printf("[MOTOR] dir=%s, speed=%d%%, duty=%lu\n",
           direction == MOTOR_FORWARD ? "FWD" : "REV", percent, motor.duty);
}}

void motor_stop(void) {{
    motor_set_speed(0, 0);
}}

/* ========== I2C 温度传感器驱动 ========== */

#define I2C_STATUS_BUSY   0x01
#define I2C_STATUS_ACK    0x08

void i2c_init(void) {{
    *(volatile uint32_t *)(I2C_BASE + 0x0C) = 312;  /* 时钟分频 */
    *(volatile uint32_t *)(I2C_BASE + 0x00) |= 0x10; /* 使能 I2C */
}}

bool i2c_write_reg(uint8_t addr, uint8_t reg, uint8_t data) {{
    *(volatile uint32_t *)(I2C_BASE + 0x00) = ((uint32_t)addr << 1) | 0x0B; /* WRITE+START */
    while (*(volatile uint32_t *)(I2C_BASE + 0x04) & I2C_STATUS_BUSY);

    *(volatile uint32_t *)(I2C_BASE + 0x08) = reg;
    while (*(volatile uint32_t *)(I2C_BASE + 0x04) & I2C_STATUS_BUSY);

    *(volatile uint32_t *)(I2C_BASE + 0x08) = data;
    while (*(volatile uint32_t *)(I2C_BASE + 0x04) & I2C_STATUS_BUSY);

    *(volatile uint32_t *)(I2C_BASE + 0x00) = 0x02; /* STOP */
    while (*(volatile uint32_t *)(I2C_BASE + 0x04) & I2C_STATUS_BUSY);

    return (*(volatile uint32_t *)(I2C_BASE + 0x04) & I2C_STATUS_ACK) != 0;
}}

bool i2c_read_reg(uint8_t addr, uint8_t reg, uint8_t *data) {{
    i2c_write_reg(addr, reg, 0);
    *(volatile uint32_t *)(I2C_BASE + 0x00) = ((uint32_t)addr << 1 | 0x09); /* READ+START */
    while (*(volatile uint32_t *)(I2C_BASE + 0x04) & I2C_STATUS_BUSY);
    *data = (uint8_t)(*(volatile uint32_t *)(I2C_BASE + 0x08) & 0xFF);
    *(volatile uint32_t *)(I2C_BASE + 0x00) = 0x02; /* STOP */
    return true;
}}

float read_temperature(void) {{
    uint8_t raw_h, raw_l;

    /* 配置 ADS1115: 单端通道0, 增益=2/3, 860SPS */
    i2c_write_reg(ADS1115_ADDR, 0x01, 0xC0);  /* OS = Start Conversion */
    i2c_write_reg(ADS1115_ADDR, 0x01, 0x86);  /* MUX=0, PGA=0x02, DR=0x07 */

    /* 读取转换结果 */
    i2c_read_reg(ADS1115_ADDR, 0x00, &raw_h);
    i2c_read_reg(ADS1115_ADDR, 0x00, &raw_l);

    int16_t raw = (int16_t)((raw_h << 8) | raw_l);

    /* LM35: 10mV/°C, 增益=2/3 → 满量程=±6.144V */
    float voltage = (float)raw * 6.144f / 32768.0f;
    return voltage * 100.0f;
}}

/* ========== UART 输出 ========== */

void uart_init(void) {{
    *(volatile uint32_t *)(UART_BASE + 0x00) = 0;  /* 禁用 */
    *(volatile uint32_t *)(UART_BASE + 0x04) = 52;  /* 分频 = 156MHz/(16*115200) ≈ 84 */
    *(volatile uint32_t *)(UART_BASE + 0x0C) = 0x73; /* 8N1 模式 */
    *(volatile uint32_t *)(UART_BASE + 0x00) = 0x01; /* 使能 */
}}

void uart_send_byte(uint8_t c) {{
    while (!(*(volatile uint32_t *)(UART_BASE + 0x04) & 0x02));
    *(volatile uint32_t *)(UART_BASE + 0x08) = c;
}}

void uart_send_string(const char *s) {{
    while (*s) uart_send_byte(*s++);
}}

void uart_send_float(float f) {{
    char buf[16];
    sprintf(buf, "%.2f", f);
    uart_send_string(buf);
}}

/* ========== 主程序 ========== */

int main(void) {{
    uart_init();
    gpio_init();
    motor_init();
    i2c_init();

    uart_send_string("Matha RISC-V Embedded Project\r\n");
    uart_send_string("GPIO + PWM + I2C Temp Sensor\r\n\r\n");

    uint32_t last_temp_ms = 0;
    uint32_t last_tick = 0;
    bool motor_on = false;
    int speed = 50;  /* 默认 50% 速度 */

    while (1) {{
        uint32_t tick = *(volatile uint32_t *)(0x40000000UL);  /* 系统 tick */

        /* 按钮检测: 按下切换电机开关 */
        if (!gpio_read(PIN_BUTTON) && tick - last_tick > 200) {{
            last_tick = tick;
            motor_on = !motor_on;
            gpio_toggle(PIN_LED);
            if (motor_on) {{
                motor_set_speed(MOTOR_FORWARD, speed);
                uart_send_string("[MOTOR] START\r\n");
            }} else {{
                motor_stop();
                uart_send_string("[MOTOR] STOP\r\n");
            }}
        }}

        /* 温度读取 (每秒) */
        if (tick - last_temp_ms >= TEMP_SAMPLE_MS) {{
            last_temp_ms = tick;
            float temp = read_temperature();
            uart_send_string("[TEMP] ");
            uart_send_float(temp);
            uart_send_string(" C\r\n");
        }}

        /* 状态输出 */
        if (motor_on) {{
            uart_send_string("[STATUS] Motor: RUNNING @ ");
            char buf[8];
            sprintf(buf, "%d%%", speed);
            uart_send_string(buf);
            uart_send_string("\r\n");
        }}

        /* 延时 */
        for (volatile int i = 0; i < 100000; i++);
    }}
}}
