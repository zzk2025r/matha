/*
 * Matha RISC-V I2C 温度传感器驱动
 * 目标: SiFive FE310 (RISC-V 32-bit)
 * 协议: I2C 100kHz, 地址: 0x48
 * 生成时间: 2026-08-23
 */

#include <stdint.h>
#include <stdbool.h>

/* ========== 寄存器定义 ========== */
#define I2C_BASE_ADDR     0x40003000UL
#define I2C_CTRL_REG      (*(volatile uint32_t *)(I2C_BASE_ADDR + 0x00))
#define I2C_STATUS_REG    (*(volatile uint32_t *)(I2C_BASE_ADDR + 0x04))
#define I2C_DATA_REG      (*(volatile uint32_t *)(I2C_BASE_ADDR + 0x08))
#define I2C_CLK_DIV       (*(volatile uint32_t *)(I2C_BASE_ADDR + 0x0C))

/* I2C 控制位 */
#define I2C_CTRL_START    (1 << 0)
#define I2C_CTRL_STOP     (1 << 1)
#define I2C_CTRL_READ     (1 << 2)
#define I2C_CTRL_WRITE    (1 << 3)
#define I2C_CTRL_ENABLE   (1 << 4)

/* I2C 状态位 */
#define I2C_STATUS_BUSY   (1 << 0)
#define I2C_STATUS_TXNF   (1 << 1)
#define I2C_STATUS_RXNE   (1 << 2)
#define I2C_STATUS_ACK    (1 << 3)

/* ADS1115 寄存器 */
#define ADS1115_REG_CONVERT  0x00
#define ADS1115_REG_CONFIG   0x01
#define ADS1115_I2C_ADDR    0x48

/* 配置寄存器位域 */
#define CFG_OS_SHIFT    15
#define CFG_MUX_SHIFT   12
#define CFG_PGA_SHIFT   9
#define CFG_MODE_SHIFT  8
#define CFG_DR_SHIFT    5

/* 增益配置 */
#define PGA_6144V   0x00   /* ±6.144V */
#define PGA_4096V   0x01   /* ±4.096V */
#define PGA_2048V   0x02   /* ±2.048V (默认) */
#define PGA_1024V   0x03   /* ±1.024V */
#define PGA_0512V   0x04   /* ±0.512V */
#define PGA_0256V   0x05   /* ±0.256V */

/* 数据速率 */
#define DR_8SPS     0x00
#define DR_16SPS    0x01
#define DR_32SPS    0x02
#define DR_64SPS    0x03
#define DR_128SPS   0x04
#define DR_250SPS   0x05
#define DR_475SPS   0x06
#define DR_860SPS   0x07

/* ========== I2C 驱动 ========== */

void i2c_init(void) {
    I2C_CLK_DIV = 312;  /* 156MHz / (2 * (312+1)) ≈ 250kHz, 再分频到100kHz */
    I2C_CTRL_REG |= I2C_CTRL_ENABLE;
}

bool i2c_write_reg(uint8_t addr, uint8_t reg, uint8_t data) {
    I2C_CTRL_REG = (addr << 1) | I2C_CTRL_WRITE | I2C_CTRL_START;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    I2C_DATA_REG = reg;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    I2C_DATA_REG = data;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    I2C_CTRL_REG = I2C_CTRL_STOP;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    return (I2C_STATUS_REG & I2C_STATUS_ACK) != 0;
}

bool i2c_read_reg(uint8_t addr, uint8_t reg, uint8_t *data, uint8_t len) {
    /* 发送寄存器地址 */
    i2c_write_reg(addr, reg, 0);

    /* 读取数据 */
    I2C_CTRL_REG = ((addr << 1) | I2C_CTRL_READ) | I2C_CTRL_START;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    *data = (uint8_t)(I2C_DATA_REG & 0xFF);
    I2C_CTRL_REG = I2C_CTRL_STOP;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    return true;
}

/* ========== ADS1115 驱动 ========== */

typedef struct {
    uint8_t i2c_addr;
    uint8_t channel;
    uint8_t gain;
    uint8_t data_rate;
} ADS1115_Config;

void ads1115_init(ADS1115_Config *cfg) {
    uint16_t config = (1 << CFG_OS_SHIFT)
                    | (cfg->channel << CFG_MUX_SHIFT)
                    | (cfg->gain << CFG_PGA_SHIFT)
                    | (0 << CFG_MODE_SHIFT)    /* 单次转换模式 */
                    | (cfg->data_rate << CFG_DR_SHIFT);
    i2c_write_reg(cfg->i2c_addr, 0x01, config >> 8);
    i2c_write_reg(cfg->i2c_addr, 0x01, config & 0xFF);
}

int16_t ads1115_read_raw(ADS1115_Config *cfg) {
    uint8_t raw_h, raw_l;
    i2c_read_reg(cfg->i2c_addr, 0x00, &raw_h, 1);
    i2c_read_reg(cfg->i2c_addr, 0x00, &raw_l, 1);
    return (int16_t)((raw_h << 8) | raw_l);
}

float ads1115_read_voltage(ADS1115_Config *cfg) {
    int16_t raw = ads1115_read_raw(cfg);
    float full_scale = 6.144f / (1 << cfg->gain);
    return (float)raw * full_scale / 32768.0f;
}

float ads1115_read_temperature_lm35(ADS1115_Config *cfg) {
    float voltage = ads1115_read_voltage(cfg);
    return voltage * 100.0f;  /* LM35: 10mV/°C */
}

/* ========== 主函数 ========== */

int main(void) {
    ADS1115_Config sensor = {
        .i2c_addr = 0x48,
        .channel  = 0,
        .gain     = PGA_2048V,
        .data_rate = DR_860SPS,
    };

    i2c_init();
    ads1115_init(&sensor);

    while (1) {
        float temp = ads1115_read_temperature_lm35(&sensor);
        /* 发送温度值到 UART 或显示 */
        // uart_send_float(temp);
        // delay_ms(1000);
    }
}
