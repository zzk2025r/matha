# -*- coding: utf-8 -*-
"""Embedded Domain: 嵌入式系统内建函数。

覆盖：
  - ADC 模数转换计算
  - PWM 占空比/频率计算
  - 传感器公式（温度、光线、距离等）
  - 电机控制（步进、直流、舵机）
  - 通信协议（UART 波特率、I2C 地址计算）
"""

from __future__ import annotations


# ============================================================
# ADC / DAC
# ============================================================

def _adc_value(voltage: float, ref_voltage: float = 3.3, bits: int = 12) -> int:
    """ADC 电压 → 数字值。"""
    if ref_voltage <= 0:
        return 0
    return int((voltage / ref_voltage) * ((1 << bits) - 1))


def _adc_voltage(digital: int, ref_voltage: float = 3.3, bits: int = 12) -> float:
    """ADC 数字值 → 电压。"""
    max_val = (1 << bits) - 1
    if max_val == 0:
        return 0.0
    return (digital / max_val) * ref_voltage


def _dac_value(voltage: float, ref_voltage: float = 3.3, bits: int = 12) -> int:
    """DAC 电压 → 数字值（同 ADC）。"""
    return _adc_value(voltage, ref_voltage, bits)


# ============================================================
# PWM
# ============================================================

def _pwm_duty_cycle(on_time: float, period: float) -> float:
    """计算占空比（%）。"""
    if period <= 0:
        return 0.0
    return min(100.0, max(0.0, (on_time / period) * 100.0))


def _pwm_period(freq: float, duty: float = 50.0) -> float:
    """计算周期（秒），给定频率。"""
    if freq <= 0:
        return 0.0
    return 1.0 / freq


def _pwm_on_time(period: float, duty: float) -> float:
    """计算高电平时间（秒）。"""
    return period * (duty / 100.0)


# ============================================================
# 传感器
# ============================================================

# 热敏电阻 B 值计算
def _thermistor_temperature(R: float, R0: float = 10000.0,
                            T0: float = 298.15, B: float = 3950.0) -> float:
    """NTC 热敏电阻温度计算（K）。

    R: 当前电阻 (Ω)
    R0: 标称电阻 (Ω)，通常 25°C 时
    T0: 标称温度 (K)，通常 298.15K (25°C)
    B: B 值 (K)
    """
    import math
    if R <= 0 or R0 <= 0:
        return 0.0
    return B / (B / T0 + math.log(R0 / R))


def _thermistor_temperature_celsius(R: float, R0: float = 10000.0,
                                     T0: float = 298.15, B: float = 3950.0) -> float:
    """NTC 热敏电阻温度计算（°C）。"""
    return _thermistor_temperature(R, R0, T0, B) - 273.15


# 光线传感器（光敏电阻）
def _photocell_light(R_dark: float, R_light: float, R_sensor: float) -> float:
    """光敏电阻光照估算（相对百分比）。"""
    if R_sensor <= 0:
        return 0.0
    if R_dark <= R_light:
        return 100.0
    ratio = (R_sensor - R_light) / (R_dark - R_light)
    return max(0.0, min(100.0, ratio * 100.0))


# 超声波测距
def _ultrasonic_distance(time_us: float, speed_of_sound: float = 343.0) -> float:
    """超声波测距（米）。time_us: 回波时间（微秒）。"""
    return (time_us * 1e-6 * speed_of_sound) / 2.0


# 陀螺仪/加速度计
def _accel_angle(ax: float, ay: float, az: float) -> tuple[float, float]:
    """加速度计计算俯仰角和横滚角（度）。"""
    import math
    pitch = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))
    roll = math.degrees(math.atan2(ay, az))
    return (pitch, roll)


# 步进电机
def _stepper_steps_to_degrees(steps: int, steps_per_rev: int = 200, reduction: float = 1.0) -> float:
    """步进数 → 角度（度）。"""
    if steps_per_rev <= 0 or reduction <= 0:
        return 0.0
    return steps * 360.0 / (steps_per_rev * reduction)


def _stepper_degrees_to_steps(degrees: float, steps_per_rev: int = 200, reduction: float = 1.0) -> int:
    """角度 → 步进数。"""
    if steps_per_rev <= 0 or reduction <= 0:
        return 0
    return int(degrees * steps_per_rev * reduction / 360.0)


# 舵机
def _servo_angle(pulse_us: float, min_pulse: float = 500.0, max_pulse: float = 2500.0) -> float:
    """脉冲宽度 → 舵机角度（度）。"""
    if max_pulse <= min_pulse:
        return 0.0
    return (pulse_us - min_pulse) / (max_pulse - min_pulse) * 180.0


def _servo_pulse(angle: float, min_pulse: float = 500.0, max_pulse: float = 2500.0) -> float:
    """舵机角度 → 脉冲宽度（微秒）。"""
    return min_pulse + (angle / 180.0) * (max_pulse - min_pulse)


# ============================================================
# 通信协议
# ============================================================

def _uart_baud_error(desired: float, crystal: float = 11059200.0, divider: int = 16) -> float:
    """UART 波特率误差计算（%）。"""
    actual_div = int(crystal / (desired * divider))
    if actual_div <= 0:
        return 100.0
    actual_baud = crystal / (actual_div * divider)
    if desired <= 0:
        return 100.0
    return abs((actual_baud - desired) / desired) * 100.0


def _i2c_pullup_resistor(vcc: float = 3.3, i2c_current: float = 3.0e-3) -> float:
    """计算 I2C 上拉电阻（Ω）。"""
    if i2c_current <= 0:
        return 0.0
    return vcc / i2c_current


def _spi_clock_divider(clock: float, sys_clock: float = 72000000.0) -> int:
    """SPI 时钟分频器计算。"""
    if clock <= 0:
        return 1
    div = sys_clock / clock
    # SPI 分频器只能是 2,4,8,16,32,64,128
    prescalers = [2, 4, 8, 16, 32, 64, 128]
    for p in prescalers:
        if sys_clock / p <= clock:
            return p
    return prescalers[-1]


# ============================================================
# 电机控制
# ============================================================

def _dc_motor_rpm(voltage: float, k_v: float) -> float:
    """直流电机转速（RPM）。k_v: RPM/V。"""
    if k_v <= 0:
        return 0.0
    return voltage * k_v


def _dc_motor_current(torque: float, k_t: float) -> float:
    """直流电机堵转电流（A）。k_t: Nm/A。"""
    if k_t <= 0:
        return 0.0
    return torque / k_t


def _stepper_torque(freq: float, voltage: float, resistance: float) -> float:
    """步进电机转矩估算（简化）。"""
    if resistance <= 0:
        return 0.0
    # 简化模型：转矩 ∝ V/R，随频率衰减
    base_torque = voltage / resistance
    cutoff_freq = resistance / (2 * 3.14159 * 0.001)  # 假设 L=1mH
    return base_torque / (1 + freq / cutoff_freq)


# ============================================================
# 电源管理
# ============================================================

def _battery_voltage(cells: int, cell_type: str = "liion") -> float:
    """电池组电压估算。"""
    types = {
        "liion": 3.7, "lipo": 3.7, "nimh": 1.2, "alkaline": 1.5,
        "leadacid": 2.1, "lifepo4": 3.2,
    }
    return cells * types.get(cell_type, 3.7)


def _battery_capacity_wh(ah: float, voltage: float) -> float:
    """电池容量（Wh）。"""
    return ah * voltage


def _power_budget(items: list) -> float:
    """功耗预算计算（W）。items: [(power_w, duty_cycle), ...]。"""
    total = 0.0
    for power, duty in items:
        total += power * max(0.0, min(1.0, duty))
    return total


# ============================================================
# 注册
# ============================================================

def _register_embedded(builtins: dict) -> None:
    """将嵌入式领域内建注册到解释器。"""
    # ADC/DAC
    builtins["ADC值"] = _curry3(_adc_value)
    builtins["ADC电压"] = _curry3(_adc_voltage)
    builtins["DAC值"] = _curry3(_dac_value)

    # PWM
    builtins["PWM占空比"] = _curry2(_pwm_duty_cycle)
    builtins["PWM周期"] = _pwm_period
    builtins["PWM高电平"] = _curry2(_pwm_on_time)

    # 传感器
    builtins["热敏温度K"] = _curry4(_thermistor_temperature)
    builtins["热敏温度C"] = _curry4(_thermistor_temperature_celsius)
    builtins["光照估算"] = _curry3(_photocell_light)
    builtins["超声波距离"] = _curry2(_ultrasonic_distance)
    builtins["加速度角度"] = _curry3(_accel_angle)

    # 电机
    builtins["步进角度"] = _curry3(_stepper_steps_to_degrees)
    builtins["步进步数"] = _curry3(_stepper_degrees_to_steps)
    builtins["舵机角度"] = _curry3(_servo_angle)
    builtins["舵机脉冲"] = _curry3(_servo_pulse)
    builtins["直流转速"] = _curry2(_dc_motor_rpm)
    builtins["直流电流"] = _curry2(_dc_motor_current)
    builtins["步进转矩"] = _curry3(_stepper_torque)

    # 通信
    builtins["UART误差"] = _curry3(_uart_baud_error)
    builtins["I2C上拉"] = _curry2(_i2c_pullup_resistor)
    builtins["SPI分频"] = _curry2(_spi_clock_divider)

    # 电源
    builtins["电池电压"] = _curry2(_battery_voltage)
    builtins["电池容量"] = _curry2(_battery_capacity_wh)
    builtins["功耗预算"] = _power_budget


def _register_embedded_symtab_names() -> list[str]:
    return [
        "ADC值", "ADC电压", "DAC值",
        "PWM占空比", "PWM周期", "PWM高电平",
        "热敏温度K", "热敏温度C", "光照估算", "超声波距离", "加速度角度",
        "步进角度", "步进步数", "舵机角度", "舵机脉冲",
        "直流转速", "直流电流", "步进转矩",
        "UART误差", "I2C上拉", "SPI分频",
        "电池电压", "电池容量Wh", "功耗预算",
    ]


def _curry2(fn):
    """两参 → 柯里化 f(a)(b)。"""
    def with_first(a):
        return lambda b: fn(a, b)
    return with_first


def _curry3(fn):
    """三参 → 柯里化 f(a)(b)(c)。"""
    def with_first(a):
        def with_second(b):
            return lambda c: fn(a, b, c)
        return with_second
    return with_first


def _curry4(fn):
    """四参 → 柯里化 f(a)(b)(c)(d)。"""
    def w1(a):
        def w2(b):
            def w3(c):
                return lambda d: fn(a, b, c, d)
            return w3
        return w2
    return w1
