# -*- coding: utf-8 -*-
"""
Matha RISC-V 示例项目
=====================
1. I2C 温度传感器驱动 (ADS1115)
2. 线性代数引擎矩阵运算演示
3. GPIO + PWM 电机调速完整嵌入式项目模板
"""
from __future__ import annotations
import sys
import os
import time
import math
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s [%(levelname)s] %(message)s')
logger = logging.getLogger("matha.riscv_demo")


# ═══════════════════════════════════════════════════════════════════════════════
#  模块 1: RISC-V I2C 温度传感器驱动 (ADS1115)
# ═══════════════════════════════════════════════════════════════════════════════

class I2CError(Exception):
    """I2C 通信错误。"""
    pass


@dataclass
class I2CConfig:
    """I2C 总线配置。"""
    bus: int = 1                    # I2C 总线编号
    address: int = 0x48             # 设备地址
    clock_speed: int = 100000       # 100kHz (标准模式)
    timeout_ms: int = 1000          # 超时时间

    # RISC-V 专用寄存器地址
    base_addr: int = 0x40003000     # RISC-V I2C 外设基地址
    ctrl_offset: int = 0x00         # 控制寄存器偏移
    status_offset: int = 0x04       # 状态寄存器偏移
    data_offset: int = 0x08         # 数据寄存器偏移
    clk_offset: int = 0x0C          # 时钟分频寄存器偏移


@dataclass
class ADS1115Config:
    """ADS1115 温度传感器配置。"""
    i2c_addr: int = 0x48            # I2C 地址
    data_rate: int = 860            # 数据速率 (SPS)
    gain: int = 1                   # 增益 (PGA = 6 / gain)
    mode: int = 0                   # 0=单次转换, 1=连续转换
    channel: int = 0                # 通道 (0-3)

    # ADS1115 寄存器地址
    REG_CONVERT = 0x00              # 转换结果寄存器
    REG_CONFIG  = 0x01              # 配置寄存器
    REG_THLOW   = 0x02              # 低阈值寄存器
    REG_THHIGH  = 0x03              # 高阈值寄存器


class I2CBus:
    """
    RISC-V I2C 总线驱动。

    支持两种模式：
      - 仿真模式 (默认): 使用 Python 模拟 I2C 通信
      - 真实模式: 使用 linux-i2c-dev 或 RISC-V 硬件外设

    生成的 C 代码可用于 SiFive FE310 (RISC-V 32-bit) 裸机环境。
    """

    def __init__(self, config: I2CConfig):
        self.cfg = config
        self._initialized = False
        self._simulating = True  # 默认仿真模式

        # 尝试导入真实硬件库
        try:
            import smbus2
            self._smbus = smbus2.SMBus(config.bus)
            self._simulating = False
            logger.info(f"  [I2C] 使用真实硬件 (smbus2), 总线={config.bus}")
        except ImportError:
            try:
                import board
                i2c = board.I2C()
                self._simulating = False
                logger.info(f"  [I2C] 使用硬件 I2C (board.I2C)")
            except ImportError:
                logger.warning(f"  [I2C] 使用仿真模式 (未安装 smbus2/board)")

    def init(self) -> bool:
        """初始化 I2C 总线。"""
        if self._initialized:
            return True

        if not self._simulating:
            # 真实硬件初始化
            self._setup_hardware()
        else:
            # 仿真初始化
            self._sim_regs = {0: 0, 1: 0, 2: 0, 3: 0}
            self._sim_data = [0] * 16  # 模拟 I2C 数据缓冲区

        self._initialized = True
        logger.info(f"  [I2C] 初始化完成: bus={self.cfg.bus}, "
                    f"addr=0x{self.cfg.address:02X}, speed={self.cfg.clock_speed}Hz")
        return True

    def _setup_hardware(self):
        """配置真实 I2C 硬件参数。"""
        pass  # smbus2 自动处理

    def write_reg(self, reg: int, data: bytes) -> bool:
        """向寄存器写入数据。"""
        if self._simulating:
            self._sim_regs[reg] = int.from_bytes(data, 'big')
            logger.debug(f"  [I2C写] 0x{self.cfg.address:02X} -> 0x{reg:02X}: {data.hex()}")
            return True
        else:
            try:
                self._smbus.write_i2c_block_data(self.cfg.address, reg, list(data))
                return True
            except Exception as e:
                raise I2CError(f"I2C 写入失败: {e}")

    def read_reg(self, reg: int, length: int = 2) -> bytes:
        """从寄存器读取数据。"""
        if self._simulating:
            val = self._sim_regs.get(reg, 0)
            result = val.to_bytes(length, 'big')
            logger.debug(f"  [I2C读] 0x{self.cfg.address:02X} <- 0x{reg:02X}: {result.hex()}")
            return result
        else:
            try:
                data = self._smbus.read_i2c_block_data(self.cfg.address, reg, length)
                return bytes(data)
            except Exception as e:
                raise I2CError(f"I2C 读取失败: {e}")

    def scan(self) -> List[int]:
        """扫描 I2C 总线上的设备。"""
        found = []
        if self._simulating:
            # 仿真模式：返回模拟的ADS1115设备
            return [0x48]
        else:
            for addr in range(0x03, 0x78):
                try:
                    self._smbus.write_quick(addr)
                    found.append(addr)
                except Exception:
                    pass
            return found


class ADSTemperatureSensor:
    """
    ADS1115 I2C 温度传感器驱动。

    ADS1115 是 16位 ADC，可用于连接：
      - NTC 热敏电阻
      - PT100/PT1000 温度传感器
      - LM35 模拟温度传感器

    支持 RISC-V 裸机环境，可生成 C 代码用于 SiFive FE310。
    """

    # ADS1115 配置寄存器位域
    CFG_OS_BIT    = 15    # 操作状态位
    CFG_MUX_BIT   = 12    # 多路选择器 (3 bits)
    CFG_PGA_BIT   = 9     # 程序增益放大器 (3 bits)
    CFG_MODE_BIT  = 8     # 工作模式
    CFG_DR_BIT    = 5     # 数据速率 (3 bits)
    CFG_CMODE_BIT = 4     # 比较器模式
    CFG_CPOL_BIT  = 3     # 比较器极性
    CFG_CLAT_BIT  = 2     # 比较器滞后
    CFG_CQUE_BIT  = 0     # 比较器队列 (2 bits)

    # PGA 增益配置
    PGA_GAINS = {
        2/3: 0b000,
        1:   0b001,
        2:   0b010,
        4:   0b011,
        8:   0b100,
        16:  0b101,
    }

    # 数据速率配置
    DATA_RATES = {
        8:   0b000,
        16:  0b001,
        32:  0b010,
        64:  0b011,
        128: 0b100,
        250: 0b101,
        475: 0b110,
        860: 0b111,
    }

    def __init__(self, i2c: I2CBus, config: ADS1115Config):
        self.i2c = i2c
        self.cfg = config
        self._temp_history: List[float] = []
        self._read_count = 0

    def init(self) -> bool:
        """初始化 ADS1115。"""
        self.i2c.init()

        # 扫描 I2C 总线确认设备
        devices = self.i2c.scan()
        if self.cfg.i2c_addr not in devices:
            logger.warning(f"  [ADS1115] 未在总线找到设备 0x{self.cfg.i2c_addr:02X}")
            logger.warning(f"  [ADS1115] 检测到设备: {[hex(d) for d in devices]}")

        # 写入配置寄存器: 单端通道0, 增益=2/3 (±6.144V), 860SPS
        cfg_reg = (
            (1 << self.CFG_OS_BIT) |           # 启动转换
            (self.cfg.channel << self.CFG_MUX_BIT) |
            (self.PGA_GAINS[self.cfg.gain] << self.CFG_PGA_BIT) |
            (self.cfg.mode << self.CFG_MODE_BIT) |
            (self.DATA_RATES[self.cfg.data_rate] << self.CFG_DR_BIT) |
            (0 << self.CFG_CMODE_BIT) |
            (0 << self.CFG_CPOL_BIT) |
            (0 << self.CFG_CLAT_BIT) |
            (0 << self.CFG_CQUE_BIT)
        )

        self.i2c.write_reg(self.cfg.REG_CONFIG, cfg_reg.to_bytes(2, 'big'))
        logger.info(f"  [ADS1115] 初始化完成: 通道={self.cfg.channel}, "
                    f"增益={self.cfg.gain}, 速率={self.cfg.data_rate}SPS")
        return True

    def read_raw(self) -> int:
        """读取原始 ADC 值 (16位有符号)。"""
        data = self.i2c.read_reg(self.cfg.REG_CONVERT, 2)
        raw = int.from_bytes(data, 'big', signed=True)
        return raw

    def read_voltage(self) -> float:
        """读取通道电压 (mV)。"""
        raw = self.read_raw()
        # ADS1115: 16位ADC, 满量程 = PGA增益 * 6.144V
        full_scale = 6.144 / self.cfg.gain
        voltage = raw * full_scale / 32768.0
        return voltage * 1000.0  # 转换为 mV

    def read_temperature_ntc(self, r_nominal: float = 10000.0,
                              t_nominal: float = 25.0,
                              b_coeff: float = 3950.0,
                              r_series: float = 10000.0) -> float:
        """
        通过 NTC 热敏电阻读取温度。

        参数:
            r_nominal: 额定电阻值 (Ω)
            t_nominal: 额定温度 (°C)
            b_coeff:   B 系数
            r_series:  串联电阻值 (Ω)

        返回:
            温度值 (°C)
        """
        voltage = self.read_voltage() / 1000.0  # 转换为 V

        # 分压公式: V_out = V_cc * R_ntc / (R_series + R_ntc)
        # R_ntc = R_series * V_out / (V_cc - V_out)
        if voltage >= 5.0:  # 防止除零
            return float('nan')

        r_ntc = r_series * voltage / (5.0 - voltage)

        # Steinhart-Hart 简化公式
        # 1/T = 1/T0 + (1/B) * ln(R/R0)
        t_kelvin = 1.0 / (1.0 / (t_nominal + 273.15) +
                          (1.0 / b_coeff) * math.log(r_ntc / r_nominal))
        return t_kelvin - 273.15

    def read_temperature_lm35(self) -> float:
        """通过 LM35 模拟温度传感器读取温度。"""
        # LM35: 10mV/°C, 0°C = 0V
        voltage = self.read_voltage() / 1000.0  # V
        return voltage * 100.0  # °C

    def read_temperature(self, sensor_type: str = "lm35") -> float:
        """读取温度，根据传感器类型自动选择计算方式。"""
        if sensor_type == "lm35":
            temp = self.read_temperature_lm35()
        elif sensor_type == "ntc":
            temp = self.read_temperature_ntc()
        else:
            raise ValueError(f"未知传感器类型: {sensor_type}")

        self._temp_history.append(temp)
        self._read_count += 1
        logger.info(f"  [ADS1115] 温度: {temp:.2f}°C (读取次数={self._read_count})")
        return temp

    def get_stats(self) -> dict:
        """获取传感器统计信息。"""
        if not self._temp_history:
            return {"readings": 0, "avg_temp": None}

        return {
            "readings": self._read_count,
            "avg_temp": sum(self._temp_history) / len(self._temp_history),
            "min_temp": min(self._temp_history),
            "max_temp": max(self._temp_history),
            "history": self._temp_history[-10:],  # 最近10次读取
        }


# C 代码生成：I2C 温度传感器驱动
def generate_i2c_sensor_c(i2c_addr: int = 0x48, channel: int = 0) -> str:
    """生成 RISC-V 裸机 C 代码驱动。"""
    return f'''/*
 * Matha RISC-V I2C 温度传感器驱动
 * 目标: SiFive FE310 (RISC-V 32-bit)
 * 协议: I2C 100kHz, 地址: 0x{i2c_addr:02X}
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
#define ADS1115_I2C_ADDR    0x{i2c_addr:02X}

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

void i2c_init(void) {{
    I2C_CLK_DIV = 312;  /* 156MHz / (2 * (312+1)) ≈ 250kHz, 再分频到100kHz */
    I2C_CTRL_REG |= I2C_CTRL_ENABLE;
}}

bool i2c_write_reg(uint8_t addr, uint8_t reg, uint8_t data) {{
    I2C_CTRL_REG = (addr << 1) | I2C_CTRL_WRITE | I2C_CTRL_START;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    I2C_DATA_REG = reg;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    I2C_DATA_REG = data;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    I2C_CTRL_REG = I2C_CTRL_STOP;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    return (I2C_STATUS_REG & I2C_STATUS_ACK) != 0;
}}

bool i2c_read_reg(uint8_t addr, uint8_t reg, uint8_t *data, uint8_t len) {{
    /* 发送寄存器地址 */
    i2c_write_reg(addr, reg, 0);

    /* 读取数据 */
    I2C_CTRL_REG = ((addr << 1) | I2C_CTRL_READ) | I2C_CTRL_START;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    *data = (uint8_t)(I2C_DATA_REG & 0xFF);
    I2C_CTRL_REG = I2C_CTRL_STOP;
    while (I2C_STATUS_REG & I2C_STATUS_BUSY);

    return true;
}}

/* ========== ADS1115 驱动 ========== */

typedef struct {{
    uint8_t i2c_addr;
    uint8_t channel;
    uint8_t gain;
    uint8_t data_rate;
}} ADS1115_Config;

void ads1115_init(ADS1115_Config *cfg) {{
    uint16_t config = (1 << CFG_OS_SHIFT)
                    | (cfg->channel << CFG_MUX_SHIFT)
                    | (cfg->gain << CFG_PGA_SHIFT)
                    | (0 << CFG_MODE_SHIFT)    /* 单次转换模式 */
                    | (cfg->data_rate << CFG_DR_SHIFT);
    i2c_write_reg(cfg->i2c_addr, 0x01, config >> 8);
    i2c_write_reg(cfg->i2c_addr, 0x01, config & 0xFF);
}}

int16_t ads1115_read_raw(ADS1115_Config *cfg) {{
    uint8_t raw_h, raw_l;
    i2c_read_reg(cfg->i2c_addr, 0x00, &raw_h, 1);
    i2c_read_reg(cfg->i2c_addr, 0x00, &raw_l, 1);
    return (int16_t)((raw_h << 8) | raw_l);
}}

float ads1115_read_voltage(ADS1115_Config *cfg) {{
    int16_t raw = ads1115_read_raw(cfg);
    float full_scale = 6.144f / (1 << cfg->gain);
    return (float)raw * full_scale / 32768.0f;
}}

float ads1115_read_temperature_lm35(ADS1115_Config *cfg) {{
    float voltage = ads1115_read_voltage(cfg);
    return voltage * 100.0f;  /* LM35: 10mV/°C */
}}

/* ========== 主函数 ========== */

int main(void) {{
    ADS1115_Config sensor = {{
        .i2c_addr = 0x{i2c_addr:02X},
        .channel  = {channel},
        .gain     = PGA_2048V,
        .data_rate = DR_860SPS,
    }};

    i2c_init();
    ads1115_init(&sensor);

    while (1) {{
        float temp = ads1115_read_temperature_lm35(&sensor);
        /* 发送温度值到 UART 或显示 */
        // uart_send_float(temp);
        // delay_ms(1000);
    }}
}}
'''


# ═══════════════════════════════════════════════════════════════════════════════
#  模块 2: 线性代数引擎矩阵运算演示
# ═══════════════════════════════════════════════════════════════════════════════

class Matrix:
    """
    线性代数引擎 — 矩阵运算。

    支持 RISC-V 裸机环境的高效矩阵运算，
    生成的 C 代码可用于嵌入式系统。
    """

    def __init__(self, data: List[List[float]]):
        if not data or not data[0]:
            raise ValueError("矩阵不能为空")
        rows = len(data)
        cols = len(data[0])
        if any(len(row) != cols for row in data):
            raise ValueError("矩阵行列不一致")
        self.data = [[float(x) for x in row] for row in data]
        self.rows = rows
        self.cols = cols
        self._ops_count = 0

    @property
    def shape(self) -> Tuple[int, int]:
        return (self.rows, self.cols)

    @classmethod
    def identity(cls, n: int) -> 'Matrix':
        """生成 n×n 单位矩阵。"""
        data = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        return cls(data)

    @classmethod
    def zeros(cls, rows: int, cols: int) -> 'Matrix':
        """生成全零矩阵。"""
        return cls([[0.0] * cols for _ in range(rows)])

    @classmethod
    def from_list(cls, data: List[List[float]]) -> 'Matrix':
        """从列表创建矩阵。"""
        return cls(data)

    def __add__(self, other: 'Matrix') -> 'Matrix':
        if self.shape != other.shape:
            raise ValueError(f"矩阵尺寸不匹配: {self.shape} vs {other.shape}")
        result = [[self.data[i][j] + other.data[i][j]
                   for j in range(self.cols)] for i in range(self.rows)]
        self._ops_count += 1
        return Matrix(result)

    def __sub__(self, other: 'Matrix') -> 'Matrix':
        if self.shape != other.shape:
            raise ValueError(f"矩阵尺寸不匹配: {self.shape} vs {other.shape}")
        result = [[self.data[i][j] - other.data[i][j]
                   for j in range(self.cols)] for i in range(self.rows)]
        self._ops_count += 1
        return Matrix(result)

    def __mul__(self, other) -> 'Matrix':
        """矩阵乘法或标量乘法。"""
        if isinstance(other, Matrix):
            if self.cols != other.rows:
                raise ValueError(f"矩阵乘法尺寸不匹配: {self.shape} x {other.shape}")
            result = [[sum(self.data[i][k] * other.data[k][j]
                          for k in range(self.cols))
                       for j in range(other.cols)]
                      for i in range(self.rows)]
            self._ops_count += 1
            return Matrix(result)
        else:
            # 标量乘法
            result = [[self.data[i][j] * other for j in range(self.cols)]
                      for i in range(self.rows)]
            self._ops_count += 1
            return Matrix(result)

    def __rmul__(self, other) -> 'Matrix':
        return self * other

    def __truediv__(self, scalar: float) -> 'Matrix':
        if scalar == 0:
            raise ZeroDivisionError("矩阵除法：标量为零")
        result = [[self.data[i][j] / scalar for j in range(self.cols)]
                  for i in range(self.rows)]
        self._ops_count += 1
        return Matrix(result)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Matrix):
            return False
        if self.shape != other.shape:
            return False
        return all(abs(self.data[i][j] - other.data[i][j]) < 1e-10
                   for i in range(self.rows) for j in range(self.cols))

    def transpose(self) -> 'Matrix':
        """矩阵转置。"""
        result = [[self.data[j][i] for i in range(self.rows)]
                  for j in range(self.cols)]
        self._ops_count += 1
        return Matrix(result)

    def determinant(self) -> float:
        """行列式 (仅方阵)。"""
        if self.rows != self.cols:
            raise ValueError("行列式仅对方阵有效")
        n = self.rows
        if n == 1:
            return self.data[0][0]
        if n == 2:
            return self.data[0][0] * self.data[1][1] - self.data[0][1] * self.data[1][0]

        det = 0.0
        for j in range(n):
            # 构建子矩阵
            sub = []
            for i in range(1, n):
                row = []
                for k in range(n):
                    if k != j:
                        row.append(self.data[i][k])
                sub.append(row)
            sign = (-1) ** j
            det += sign * self.data[0][j] * Matrix(sub).determinant()
        self._ops_count += 1
        return det

    def inverse(self) -> Optional['Matrix']:
        """矩阵求逆 (高斯-若尔当消元法)。"""
        if self.rows != self.cols:
            raise ValueError("逆矩阵仅对方阵有效")
        n = self.rows
        # 构建增广矩阵 [A | I]
        aug = [self.data[i][:] + [1.0 if i == j else 0.0 for j in range(n)]
               for i in range(n)]

        for col in range(n):
            # 选主元
            max_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
            aug[col], aug[max_row] = aug[max_row], aug[col]

            pivot = aug[col][col]
            if abs(pivot) < 1e-12:
                return None  # 矩阵奇异

            # 归一化主元行
            for j in range(2 * n):
                aug[col][j] /= pivot

            # 消去其他行
            for row in range(n):
                if row != col:
                    factor = aug[row][col]
                    for j in range(2 * n):
                        aug[row][j] -= factor * aug[col][j]

        # 提取逆矩阵
        result = [row[n:] for row in aug]
        self._ops_count += 1
        return Matrix(result)

    def trace(self) -> float:
        """矩阵迹 (对角线元素之和)。"""
        if self.rows != self.cols:
            raise ValueError("迹仅对方阵有效")
        return sum(self.data[i][i] for i in range(self.rows))

    def norm(self, p: float = 2.0) -> float:
        """矩阵范数。"""
        if p == 2:
            # Frobenius 范数
            return math.sqrt(sum(self.data[i][j] ** 2
                                for i in range(self.rows) for j in range(self.cols)))
        return sum(abs(self.data[i][j]) ** p
                   for i in range(self.rows) for j in range(self.cols)) ** (1.0 / p)

    def dot(self, other: 'Matrix') -> 'Matrix':
        """矩阵乘法 (同 __mul__)。"""
        return self * other

    def mat_pow(self, n: int) -> 'Matrix':
        """矩阵幂 (快速幂)。"""
        if self.rows != self.cols:
            raise ValueError("矩阵幂仅对方阵有效")
        if n < 0:
            self = self.inverse()
            n = -n
        if n == 0:
            return Matrix.identity(self.rows)
        if n == 1:
            return self

        result = Matrix.identity(self.rows)
        base = self
        while n > 0:
            if n & 1:
                result = result * base
            base = base * base
            n >>= 1
        self._ops_count += 1
        return result

    def to_c_code(self, name: str = "matrix") -> str:
        """生成 C 代码。"""
        lines = [
            f"/* Matha Linear Algebra — {name} */",
            f"float {name}_data[{self.rows}][{self.cols}] = {{",
        ]
        for row in self.data:
            lines.append("    {" + ", ".join(f"{v:.4f}f" for v in row) + "},")
        lines.append("};")
        lines.append(f"int {name}_rows = {self.rows};")
        lines.append(f"int {name}_cols = {self.cols};")
        return "\n".join(lines)

    def __repr__(self) -> str:
        rows_str = " | ".join(
            "  ".join(f"{v:8.3f}" for v in row)
            for row in self.data
        )
        return f"Matrix({self.rows}x{self.cols}):\n{rows_str}"

    def get_stats(self) -> dict:
        return {
            "shape": self.shape,
            "ops_count": self._ops_count,
            "determinant": self.determinant() if self.rows == self.cols else None,
            "trace": self.trace() if self.rows == self.cols else None,
            "norm": self.norm(),
        }


# C 代码生成：线性代数引擎
def generate_linalg_c() -> str:
    """生成 RISC-V 裸机线性代数 C 代码。"""
    return '''/*
 * Matha 线性代数引擎 — RISC-V 裸机 C 代码
 * 目标: SiFive FE310 / RISCV32
 * 优化: -Os (代码大小优化)
 */

#include <stdint.h>
#include <string.h>
#include <stdio.h>

/* ========== 矩阵结构 ========== */
typedef struct {{
    float data[16][16];  /* 最大 16x16 */
    int rows;
    int cols;
}} Matrix;

/* ========== 矩阵操作 ========== */

void mat_init(Matrix *m, int rows, int cols) {{
    m->rows = rows;
    m->cols = cols;
    memset(m->data, 0, sizeof(m->data));
}}

void mat_identity(Matrix *m, int n) {{
    mat_init(m, n, n);
    for (int i = 0; i < n; i++) {{
        m->data[i][i] = 1.0f;
    }}
}}

void mat_copy(Matrix *dst, const Matrix *src) {{
    memcpy(dst->data, src->data, sizeof(src->data));
    dst->rows = src->rows;
    dst->cols = src->cols;
}}

void mat_add(const Matrix *a, const Matrix *b, Matrix *result) {{
    for (int i = 0; i < a->rows; i++) {{
        for (int j = 0; j < a->cols; j++) {{
            result->data[i][j] = a->data[i][j] + b->data[i][j];
        }}
    }}
    result->rows = a->rows;
    result->cols = a->cols;
}}

void mat_mul(const Matrix *a, const Matrix *b, Matrix *result) {{
    memset(result->data, 0, sizeof(result->data));
    for (int i = 0; i < a->rows; i++) {{
        for (int k = 0; k < a->cols; k++) {{
            float aik = a->data[i][k];
            for (int j = 0; j < b->cols; j++) {{
                result->data[i][j] += aik * b->data[k][j];
            }}
        }}
    }}
    result->rows = a->rows;
    result->cols = b->cols;
}}

float mat_det(const Matrix *m) {{
    int n = m->rows;
    if (n == 1) return m->data[0][0];
    if (n == 2) return m->data[0][0] * m->data[1][1] - m->data[0][1] * m->data[1][0];

    float det = 0.0f;
    for (int j = 0; j < n; j++) {{
        /* 构建子矩阵 */
        Matrix sub;
        int si = 0;
        for (int i = 1; i < n; i++) {{
            int sj = 0;
            for (int k = 0; k < n; k++) {{
                if (k != j) sub.data[si][sj++] = m->data[i][k];
            }}
            si++;
        }}
        int sign = (j % 2 == 0) ? 1 : -1;
        det += sign * m->data[0][j] * mat_det(&sub);
    }}
    return det;
}}

/* 高斯消元法求逆 */
int mat_inv(const Matrix *m, Matrix *result) {{
    int n = m->rows;
    if (n != m->cols) return -1;

    float aug[16][32];  /* 增广矩阵 [A|I] */

    /* 构建增广矩阵 */
    for (int i = 0; i < n; i++) {{
        for (int j = 0; j < n; j++) aug[i][j] = m->data[i][j];
        for (int j = 0; j < n; j++) aug[i][n + j] = (i == j) ? 1.0f : 0.0f;
    }}

    /* 高斯-若尔当消元 */
    for (int col = 0; col < n; col++) {{
        /* 选主元 */
        int max_row = col;
        for (int row = col + 1; row < n; row++) {{
            if (fabsf(aug[row][col]) > fabsf(aug[max_row][col])) max_row = row;
        }}
        if (fabsf(aug[max_row][col]) < 1e-12f) return -1;  /* 奇异矩阵 */

        /* 交换行 */
        for (int j = 0; j < 2 * n; j++) {{
            float tmp = aug[col][j];
            aug[col][j] = aug[max_row][j];
            aug[max_row][j] = tmp;
        }}

        /* 归一化 */
        float pivot = aug[col][col];
        for (int j = 0; j < 2 * n; j++) aug[col][j] /= pivot;

        /* 消去其他行 */
        for (int row = 0; row < n; row++) {{
            if (row == col) continue;
            float factor = aug[row][col];
            for (int j = 0; j < 2 * n; j++) {{
                aug[row][j] -= factor * aug[col][j];
            }}
        }}
    }}

    /* 提取逆矩阵 */
    for (int i = 0; i < n; i++) {{
        for (int j = 0; j < n; j++) {{
            result->data[i][j] = aug[i][n + j];
        }}
    }}
    result->rows = n;
    result->cols = n;
    return 0;
}}

/* ========== 应用示例 ========== */

void example_matrix_operations(void) {{
    Matrix A, B, C, I;

    /* 初始化矩阵 A = [[1,2],[3,4]] */
    mat_init(&A, 2, 2);
    A.data[0][0] = 1.0f; A.data[0][1] = 2.0f;
    A.data[1][0] = 3.0f; A.data[1][1] = 4.0f;

    /* 初始化矩阵 B = [[5,6],[7,8]] */
    mat_init(&B, 2, 2);
    B.data[0][0] = 5.0f; B.data[0][1] = 6.0f;
    B.data[1][0] = 7.0f; B.data[1][1] = 8.0f;

    /* C = A + B */
    mat_add(&A, &B, &C);
    printf("A+B = [[%.1f,%.1f],[%.1f,%.1f]]\\n",
           C.data[0][0], C.data[0][1], C.data[1][0], C.data[1][1]);

    /* C = A * B */
    mat_mul(&A, &B, &C);
    printf("A*B = [[%.1f,%.1f],[%.1f,%.1f]]\\n",
           C.data[0][0], C.data[0][1], C.data[1][0], C.data[1][1]);

    /* det(A) */
    printf("det(A) = %.1f\\n", mat_det(&A));

    /* A^(-1) */
    if (mat_inv(&A, &I) == 0) {{
        printf("A^(-1) = [[%.2f,%.2f],[%.2f,%.2f]]\\n",
               I.data[0][0], I.data[0][1], I.data[1][0], I.data[1][1]);
    }}

    /* I = A * A^(-1) */
    mat_mul(&A, &I, &C);
    printf("A*A^(-1) = [[%.2f,%.2f],[%.2f,%.2f]]\\n",
           C.data[0][0], C.data[0][1], C.data[1][0], C.data[1][1]);
}}

int main(void) {{
    example_matrix_operations();
    return 0;
}}
'''


# ═══════════════════════════════════════════════════════════════════════════════
#  模块 3: GPIO + PWM 电机调速完整嵌入式项目模板
# ═══════════════════════════════════════════════════════════════════════════════

class GPIOPin:
    """GPIO 引脚控制。"""

    def __init__(self, pin: int, mode: str = "OUTPUT"):
        self.pin = pin
        self.mode = mode  # INPUT, OUTPUT, PWM, ANALOG
        self._value = 0
        self._pull = "none"  # none, up, down

    def set(self, value: int):
        """设置引脚值 (0/1)。"""
        if value not in (0, 1):
            raise ValueError("GPIO 值必须为 0 或 1")
        self._value = value
        logger.debug(f"  [GPIO] Pin {self.pin} = {value}")

    def get(self) -> int:
        return self._value

    def high(self):
        self.set(1)

    def low(self):
        self.set(0)

    def toggle(self):
        self.set(1 - self._value)

    def __repr__(self):
        return f"GPIOPin({self.pin}, {self.mode}, val={self._value})"


class PWMChannel:
    """
    PWM 电机调速通道。

    支持 RISC-V 硬件 PWM 外设:
      - SiFive FE310: 4 个 PWM 通道
      - STM32: 多个定时器 PWM
      - 通用: 软件 PWM (位定时)
    """

    def __init__(self, pin: GPIOPin, freq: int = 20000, duty: float = 0.0):
        self.pin = pin
        self.freq = freq       # 频率 (Hz)
        self.period = 1000000 // freq if freq > 0 else 10000  # 周期 (微秒)
        self._duty_cycle = duty  # 占空比 (0.0 - 1.0)
        self._running = False

        # RISC-V PWM 寄存器 (SiFive FE310 示例)
        self.pwm_base = 0x40018000  # PWM 外设基地址
        self.pwm_period_reg = self.pwm_base + 0x00
        self.pwm_duty_reg = self.pwm_base + 0x04
        self.pwm_enable_reg = self.pwm_base + 0x08

    @property
    def duty_cycle(self) -> float:
        return self._duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, value: float):
        """设置占空比 (0.0 - 1.0)。"""
        self._duty_cycle = max(0.0, min(1.0, value))
        # 更新 RISC-V PWM 寄存器
        duty_val = int(self._duty_cycle * self.period)
        self._write_duty(duty_val)
        logger.debug(f"  [PWM] Pin {self.pin.pin}: duty={self._duty_cycle:.1%}, "
                     f"period={self.period}us, val={duty_val}")

    def _write_duty(self, duty_val: int):
        """写入 PWM 占空比寄存器。"""
        if hasattr(self, '_simulating') and self._simulating:
            self._sim_duty = duty_val
        else:
            # 真实硬件写入
            pass

    def start(self):
        """启动 PWM 输出。"""
        self._running = True
        self.pin.set(1)  # 启用输出
        logger.info(f"  [PWM] 通道 Pin {self.pin.pin} 启动: {self.freq}Hz")

    def stop(self):
        """停止 PWM 输出。"""
        self._running = False
        self.pin.low()
        logger.info(f"  [PWM] 通道 Pin {self.pin.pin} 停止")

    def set_speed(self, percent: float) -> float:
        """
        设置电机转速 (百分比)。

        参数:
            percent: -100.0 (全速反转) ~ 0.0 (停止) ~ 100.0 (全速正转)

        返回:
            实际设置的占空比
        """
        if percent < 0:
            # 反转
            self.duty_cycle = abs(percent) / 100.0
            self._direction = "reverse"
        else:
            # 正转
            self.duty_cycle = percent / 100.0
            self._direction = "forward"
        logger.info(f"  [PWM] 电机 Pin {self.pin.pin}: "
                    f"{self._direction} {abs(percent):.1f}%")
        return self.duty_cycle

    def get_stats(self) -> dict:
        return {
            "pin": self.pin.pin,
            "freq": self.freq,
            "duty_cycle": self._duty_cycle,
            "running": self._running,
            "period_us": self.period,
        }


# 完整嵌入式项目模板
def generate_embedded_project_template() -> str:
    """生成完整的 RISC-V 嵌入式项目模板。"""
    return '''/*
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

    printf("[MOTOR] dir=%s, speed=%d%%, duty=%lu\\n",
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

    uart_send_string("Matha RISC-V Embedded Project\\r\\n");
    uart_send_string("GPIO + PWM + I2C Temp Sensor\\r\\n\\r\\n");

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
                uart_send_string("[MOTOR] START\\r\\n");
            }} else {{
                motor_stop();
                uart_send_string("[MOTOR] STOP\\r\\n");
            }}
        }}

        /* 温度读取 (每秒) */
        if (tick - last_temp_ms >= TEMP_SAMPLE_MS) {{
            last_temp_ms = tick;
            float temp = read_temperature();
            uart_send_string("[TEMP] ");
            uart_send_float(temp);
            uart_send_string(" C\\r\\n");
        }}

        /* 状态输出 */
        if (motor_on) {{
            uart_send_string("[STATUS] Motor: RUNNING @ ");
            char buf[8];
            sprintf(buf, "%d%%", speed);
            uart_send_string(buf);
            uart_send_string("\\r\\n");
        }}

        /* 延时 */
        for (volatile int i = 0; i < 100000; i++);
    }}
}}
'''


# ═══════════════════════════════════════════════════════════════════════════════
#  主函数 — 演示入口
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  Matha RISC-V 嵌入式驱动演示")
    print("  1. I2C 温度传感器驱动 (ADS1115)")
    print("  2. 线性代数引擎矩阵运算")
    print("  3. GPIO + PWM 电机调速完整项目")
    print("=" * 70)
    print()

    # ─── 模块 1: I2C 温度传感器 ───────────────────────────────────────
    print("═" * 70)
    print("  [1] RISC-V I2C 温度传感器驱动 (ADS1115)")
    print("=" * 70)

    # 仿真模式演示
    i2c_bus = I2CBus(I2CConfig(bus=1, address=0x48, clock_speed=100000))
    sensor_cfg = ADS1115Config(i2c_addr=0x48, channel=0, gain=1, data_rate=860)
    sensor = ADSTemperatureSensor(i2c_bus, sensor_cfg)
    sensor.init()

    # 模拟多次读取
    print(f"\n  模拟温度读取 (LM35 传感器):")
    for i in range(5):
        temp = sensor.read_temperature("lm35")
        # 模拟温度变化
        time.sleep(0.1)

    stats = sensor.get_stats()
    print(f"\n  传感器统计:")
    print(f"    读取次数: {stats['readings']}")
    print(f"    平均温度: {stats['avg_temp']:.2f}°C")
    print(f"    温度范围: [{stats['min_temp']:.2f}°, {stats['max_temp']:.2f}°]")

    # 生成 C 代码
    print(f"\n  生成 RISC-V C 代码驱动:")
    c_code = generate_i2c_sensor_c(i2c_addr=0x48, channel=0)
    print(f"    C 代码行数: {len(c_code.splitlines())}")
    print(f"    目标架构: SiFive FE310 (RISCV32)")
    print(f"    代码大小: ~{(len(c_code) // 1024)}KB")
    print(f"    ✓ C 代码生成完成")
    print()

    # ─── 模块 2: 线性代数引擎 ───────────────────────────────────────
    print("═" * 70)
    print("  [2] 线性代数引擎矩阵运算演示")
    print("=" * 70)

    # 创建测试矩阵
    A = Matrix.from_list([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
        [7.0, 8.0, 10.0]
    ])
    B = Matrix.from_list([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0]
    ])
    C = Matrix.from_list([
        [2.0, 1.0],
        [1.0, 2.0],
        [1.0, 1.0]
    ])

    print(f"\n  矩阵 A (3x3):")
    print(A)
    print(f"\n  矩阵 B (单位矩阵):")
    print(B)
    print(f"\n  矩阵 C (3x2):")
    print(C)

    # 矩阵运算演示
    print(f"\n  ── 矩阵运算 ──")
    print(f"  A + B =")
    print(A + B)
    print(f"\n  A - B =")
    print(A - B)
    print(f"\n  A * B =")
    print(A * B)
    print(f"\n  A * C =")
    print(A * C)
    print(f"\n  A^T =")
    print(A.transpose())
    print(f"\n  det(A) = {A.determinant():.4f}")
    print(f"  trace(A) = {A.trace():.4f}")
    print(f"  ||A||_F = {A.norm():.4f}")

    # 矩阵求逆
    inv_A = A.inverse()
    if inv_A is not None:
        print(f"\n  A^(-1) =")
        print(inv_A)
        print(f"\n  A * A^(-1) =")
        print(A * inv_A)

    # 矩阵幂
    print(f"\n  A^2 =")
    print(A.mat_pow(2))

    # 生成 C 代码
    print(f"\n  生成 RISC-V C 代码:")
    c_linalg = generate_linalg_c()
    print(f"    C 代码行数: {len(c_linalg.splitlines())}")
    print(f"    目标架构: SiFive FE310 (RISCV32)")
    print(f"    ✓ C 代码生成完成")
    print()

    # ─── 模块 3: GPIO + PWM 电机调速 ────────────────────────────────
    print("═" * 70)
    print("  [3] GPIO + PWM 电机调速完整嵌入式项目")
    print("=" * 70)

    # GPIO 演示
    button = GPIOPin(0, "INPUT")
    led = GPIOPin(1, "OUTPUT")
    motor_en = GPIOPin(2, "OUTPUT")

    print(f"\n  GPIO 引脚:")
    print(f"    按钮: {button}")
    print(f"    LED:  {led}")
    print(f"    电机使能: {motor_en}")

    # PWM 电机演示
    pwm = PWMChannel(led, freq=20000, duty=0.0)
    pwm.start()

    print(f"\n  PWM 电机调速演示:")
    speeds = [0, 25, 50, 75, 100, 75, 50, 25, 0]
    for s in speeds:
        pwm.set_speed(s)
        time.sleep(0.05)

    pwm.stop()

    # 生成完整项目模板
    print(f"\n  生成完整 RISC-V 嵌入式项目模板:")
    project_code = generate_embedded_project_template()
    print(f"    C 代码行数: {len(project_code.splitlines())}")
    print(f"    代码大小: ~{(len(project_code) // 1024)}KB")
    print(f"    功能模块: GPIO控制 + PWM电机调速 + I2C温度传感器")
    print(f"    ✓ 项目模板生成完成")
    print()

    # ─── 汇总 ───────────────────────────────────────────────────────
    print("=" * 70)
    print("  演示完成 — 汇总")
    print("=" * 70)
    print(f"""
  [I2C 温度传感器]
    驱动类: ADSTemperatureSensor (ADS1115)
    协议: I2C 100kHz, 地址 0x48
    支持: LM35 / NTC 热敏电阻
    C 代码: generate_i2c_sensor_c() → SiFive FE310 裸机

  [线性代数引擎]
    类: Matrix
    运算: + - * transpose() det() inverse() mat_pow() norm()
    C 代码: generate_linalg_c() → 嵌入式矩阵运算库

  [GPIO + PWM 电机]
    GPIO: GPIOPin (输入/输出/上拉/下拉)
    PWM: PWMChannel (20kHz, 0-100% 占空比)
    项目模板: generate_embedded_project_template()
    → 完整 RISC-V 裸机项目 (GPIO+PWM+I2C)

  [生成文件]
    I2C 驱动 C 代码:     ~{len(generate_i2c_sensor_c().splitlines())} 行
    线性代数 C 代码:     ~{len(generate_linalg_c().splitlines())} 行
    嵌入式项目模板:      ~{len(project_code.splitlines())} 行
""")
    print("=" * 70)
    print("  ✅ 所有演示完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
