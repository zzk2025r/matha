# Matha v2.5 优先级 2 任务清单

**优先级 1（领域注册）已完成。** 以下是优先级 2 的详细任务清单。

---

## 任务总览

| 优先级 | 任务组 | 预计工作量 | 当前状态 |
|--------|--------|-----------|---------|
| 2 | 补充已有领域的测试 | 4 小时 | 待开始 |
| 3 | 创建缺失领域文件（17个） | 8 小时 | 待开始 |
| 4 | 完善应用层 | 4 小时 | 待开始 |

---

## 优先级 2：补充已有领域的测试

### 任务 2.1：economics 领域测试

**文件：** `tests/test_economics.py`  
**源文件：** `src/domains/economics.py`  
**预计用例数：** 15

| 测试函数 | 测试内容 |
|---------|---------|
| test_supply_demand | 供需曲线交点 |
| test_gdp_growth | GDP 增长率计算 |
| test_inflation_rate | 通货膨胀率 |
| test_compound_interest | 复利计算 |
| test_loan_amortization | 贷款摊销 |
| test_roi | 投资回报率 |
| test_present_value | 现值计算 |
| test_net_present_value | 净现值 |
| test_internal_rate_return | 内部收益率 |
| test_elasticity | 价格弹性 |
| test_market_equilibrium | 市场均衡 |
| test_tax_calculation | 税收计算 |
| test_gini_coefficient | 基尼系数 |
| test_per_capita_income | 人均收入 |
| test_trade_balance | 贸易收支 |

---

### 任务 2.2：computer_science 领域测试

**文件：** `tests/test_computer_science.py`  
**源文件：** `src/domains/computer_science.py`  
**预计用例数：** 12

| 测试函数 | 测试内容 |
|---------|---------|
| test_bubble_sort | 冒泡排序 |
| test_quick_sort | 快速排序 |
| test_binary_search | 二分查找 |
| test_linked_list | 链表操作 |
| test_stack | 栈操作 |
| test_queue | 队列操作 |
| test_hash_table | 哈希表 |
| test_tree_traversal | 树遍历 |
| test_graph_bfs | BFS 遍历 |
| test_graph_dfs | DFS 遍历 |
| test_dynamic_programming | 动态规划 |
| test_big_o_analysis | 复杂度分析 |

---

### 任务 2.3：electrical 领域测试

**文件：** `tests/test_electrical.py`  
**源文件：** `src/domains/electrical.py`  
**预计用例数：** 10

| 测试函数 | 测试内容 |
|---------|---------|
| test_ohms_law | 欧姆定律 |
| test_kirchhoff_voltage | KVL |
| test_kirchhoff_current | KCL |
| test_power_calculation | 功率计算 |
| test_series_parallel | 串并联电阻 |
| test_voltage_divider | 分压电路 |
| test_current_divider | 分流电路 |
| test_rc_circuit | RC 电路响应 |
| test_rl_circuit | RL 电路响应 |
| test_impedance | 阻抗计算 |

---

### 任务 2.4：embedded 领域测试

**文件：** `tests/test_embedded.py`  
**源文件：** `src/domains/embedded.py`  
**预计用例数：** 8

| 测试函数 | 测试内容 |
|---------|---------|
| test_adc_conversion | ADC 转换 |
| test_pwm_duty_cycle | PWM 占空比 |
| test_sensor_temperature | 温度传感器 |
| test_sensor_pressure | 压力传感器 |
| test_gpio_control | GPIO 控制 |
| test_i2c_read | I2C 读取 |
| test_spi_transfer | SPI 传输 |
| test_uart_communication | UART 通信 |

---

### 任务 2.5：extended_modeling 领域测试

**文件：** `tests/test_extended_modeling.py`  
**源文件：** `src/domains/extended_modeling.py`  
**预计用例数：** 10

| 测试函数 | 测试内容 |
|---------|---------|
| test_structural_analysis | 结构分析 |
| test_fluid_flow | 流体流动 |
| test_thermal_analysis | 热分析 |
| test_electromagnetic_field | 电磁场 |
| test_control_system | 控制系统 |
| test_material_modeling | 材料建模 |
| test_coupled_physics | 耦合物理 |
| test_boundary_conditions | 边界条件 |
| test_mesh_generation | 网格生成 |
| test_simulation_solver | 仿真求解 |

---

### 任务 2.6：real_hardware 领域测试

**文件：** `tests/test_real_hardware.py`  
**源文件：** `src/domains/real_hardware.py`  
**预计用例数：** 8

| 测试函数 | 测试内容 |
|---------|---------|
| test_sensor_driver | 传感器驱动 |
| test_actuator_control | 执行器控制 |
| test_motors | 电机控制 |
| test_servo_control | 舵机控制 |
| test_stepper_motor | 步进电机 |
| test_encoders | 编码器 |
| test_limit_switches | 限位开关 |
| test_motor_controller | 电机控制器 |

---

## 优先级 3：创建缺失领域文件（17 个）

### 模板参考
以 `src/domains/economics.py` 为标准模板，每个文件需包含：
1. 模块文档字符串（说明覆盖范围）
2. 所有函数实现（柯里化封装）
3. `__all__` 导出列表
4. `_register_xxx(builtins)` 注册函数
5. `_xxx_symtab_names()` 符号表函数

### 详细任务列表

| # | 领域 | 源文件 | 测试文件 | 参考模块 | 预计行数 |
|---|------|--------|---------|---------|---------|
| 1 | automation | `src/domains/automation.py` | `tests/test_automation.py` | economics.py | ~250 |
| 2 | iot_hardware | `src/domains/iot_hardware.py` | `tests/test_iot_hardware.py` | embedded.py | ~250 |
| 3 | os_network | `src/domains/os_network.py` | `tests/test_os_network.py` | computer_science.py | ~250 |
| 4 | audio_video | `src/domains/audio_video.py` | `tests/test_audio_video.py` | creative_coding.py | ~250 |
| 5 | graphics | `src/domains/graphics.py` | `tests/test_graphics.py` | creative_coding.py | ~250 |
| 6 | hpc | `src/domains/hpc.py` | `tests/test_hpc.py` | ai_data_science.py | ~250 |
| 7 | fintech | `src/domains/fintech.py` | `tests/test_fintech.py` | economics.py | ~250 |
| 8 | autonomous | `src/domains/autonomous.py` | `tests/test_autonomous.py` | game_dev.py | ~250 |
| 9 | aerospace | `src/domains/aerospace.py` | `tests/test_aerospace.py` | celestial.py | ~300 |
| 10 | bio_computing | `src/domains/bio_computing.py` | `tests/test_bio_computing.py` | biology.py | ~250 |
| 11 | hardware_reverse | `src/domains/hardware_reverse.py` | `tests/test_hardware_reverse.py` | embedded.py | ~200 |
| 12 | spatial_meta | `src/domains/spatial_meta.py` | `tests/test_spatial_meta.py` | celestial.py | ~250 |
| 13 | algo_trading | `src/domains/algo_trading.py` | `tests/test_algo_trading.py` | economics.py | ~250 |
| 14 | comp_chem | `src/domains/comp_chem.py` | `tests/test_comp_chem.py` | chemistry.py | ~250 |
| 15 | green_tech | `src/domains/green_tech.py` | `tests/test_green_tech.py` | thermo.py | ~250 |
| 16 | metaverse_arch | `src/domains/metaverse_arch.py` | `tests/test_metaverse_arch.py` | creative_coding.py | ~250 |
| 17 | digital_rights | `src/domains/digital_rights.py` | `tests/test_digital_rights.py` | blockchain.py | ~200 |

---

## 优先级 4：完善应用层

### 任务 4.1：software_app 真实化

**文件：** `src/domains/software_app.py`

| 函数 | 当前状态 | 改进方向 |
|------|---------|---------|
| `http_get/post/put/delete` | 模拟返回 | 集成 `requests` 库 |
| `db_query/insert/update/delete` | 内存存储 | 集成 `sqlite3` 真实数据库 |
| `jwt_encode/decode` | 模拟 | 集成 `PyJWT` 库 |
| `bcrypt_hash/verify` | 模拟 | 集成 `bcrypt` 库 |
| `cache_*` | 内存缓存 | 集成 `redis` 或持久化缓存 |
| `queue_*` | 内存队列 | 集成 `queue.Queue` 或 Redis |

### 任务 4.2：注册脚本生成

**新建文件：** `scripts/regenerate_registry.py`

```python
"""
自动扫描 src/domains/ 目录，生成 interp.py 中的注册条目。
"""
import os, re

DOMAINS_DIR = "src/domains"
INTERP_FILE = "src/interp.py"

def scan_domains():
    """扫描所有域文件，提取注册函数。"""
    domains = {}
    for f in os.listdir(DOMAINS_DIR):
        if f.endswith(".py") and not f.startswith("_"):
            path = os.path.join(DOMAINS_DIR, f)
            with open(path, encoding="utf-8") as fp:
                content = fp.read()
            # 查找 _register_xxx 函数
            match = re.search(r'def _register_(\w+)\(', content)
            if match:
                domains[f[:-3]] = f"_{match.group(1)}"
    return domains

def generate_imports(domains):
    """生成导入语句。"""
    lines = []
    for name, _ in sorted(domains.items()):
        lines.append(f'    ("src.domains.{name}", "{_[1:]}"),')
    return lines

if __name__ == "__main__":
    domains = scan_domains()
    print(f"发现 {len(domains)} 个已注册领域")
    for mod, fn in domains.items():
        print(f"  {mod} -> {fn}")
```

---

## 执行顺序建议

```
优先级 2（测试补充）：
  Day 1: 任务 2.1-2.3（economics, computer_science, electrical）
  Day 2: 任务 2.4-2.6（embedded, extended_modeling, real_hardware）

优先级 3（创建缺失领域）：
  Day 3-4: 创建前 8 个领域文件
  Day 5: 创建后 9 个领域文件
  Day 6: 为所有新领域创建测试

优先级 4（应用层完善）：
  Day 7: software_app 真实化
  Day 8: 注册脚本生成
  Day 9: 全量回归测试
```

---

## 预期成果

| 指标 | 当前 (v2.5) | 目标 (v3.0) |
|------|------------|------------|
| 领域文件数 | 37 | 54 |
| 已注册函数 | ~348 | ~550 |
| 测试用例 | 290 | ~500 |
| 领域完成度 | 85% | 95%+ |
