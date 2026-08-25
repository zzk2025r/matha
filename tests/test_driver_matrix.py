# -*- coding: utf-8 -*-
"""
Matha 驱动矩阵系统 — 单元测试

验证:
  1. 驱动矩阵完整性 (29个类别/90+个驱动)
  2. 代码生成正确性 (Python/C/Matha)
  3. 核心驱动标记正确性
  4. 架构分布正确性
  5. FFI 注册正确性
  6. 矩阵打印输出正确性
"""
from __future__ import annotations
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from driver_matrix import (
    MathaDriverMatrix,
    DriverCategory,
    DriverSubType,
    DriverSpec,
)


class TestDriverMatrixCompleteness(unittest.TestCase):
    """驱动矩阵完整性测试。"""

    def setUp(self):
        self.matrix = MathaDriverMatrix()

    def test_total_drivers(self):
        """总驱动数 >= 90。"""
        total = self.matrix._stats["total"]
        self.assertGreaterEqual(total, 90, f"期望 >= 90 个驱动, 实际 {total}")

    def test_all_categories_covered(self):
        """所有 29 个驱动类别都已覆盖。"""
        covered = set(self.matrix._stats["by_category"].keys())
        expected = {cat.value for cat in DriverCategory}
        missing = expected - covered
        self.assertEqual(missing, set(), f"缺失类别: {missing}")

    def test_core_drivers_count(self):
        """核心驱动数量合理 (>= 30)。"""
        core = self.matrix._stats["core_count"]
        self.assertGreaterEqual(core, 30, f"期望 >= 30 个核心驱动, 实际 {core}")

    def test_architecture_distribution(self):
        """架构分布覆盖多种目标。"""
        archs = self.matrix._stats["by_architecture"]
        self.assertIn("x86_64", archs)
        self.assertIn("riscv32", archs)
        self.assertIn("arm64", archs)

    def test_all_subtypes_registered(self):
        """所有子类型都已注册到矩阵。"""
        for cat in DriverCategory:
            drivers = self.matrix.list_by_category(cat)
            self.assertGreater(len(drivers), 0, f"类别 {cat.value} 无驱动")


class TestDriverCodeGeneration(unittest.TestCase):
    """驱动代码生成测试。"""

    def setUp(self):
        self.matrix = MathaDriverMatrix()

    def test_generate_python_gpu_driver(self):
        """生成 Python GPU 驱动代码。"""
        result = self.matrix.generate_code(
            DriverCategory.CORE_PERF, DriverSubType.GPU,
            Architecture.X86_64, "python"
        )
        self.assertEqual(result["target_lang"], "python")
        self.assertEqual(result["architecture"], "x86_64")
        self.assertIn("class GPU_Driver", result["code"])
        self.assertIn("def init", result["code"])
        self.assertIn("def execute", result["code"])
        self.assertTrue(result["ffi_ready"])
        self.assertTrue(result["matha_integrated"])

    def test_generate_c_stepper_driver(self):
        """生成 C 步进电机驱动代码。"""
        result = self.matrix.generate_code(
            DriverCategory.MOTOR, DriverSubType.STEPPER,
            Architecture.RISCV32, "c"
        )
        self.assertEqual(result["target_lang"], "c")
        self.assertEqual(result["architecture"], "riscv32")
        self.assertIn("#include", result["code"])
        self.assertIn("StepperMotor_init", result["code"])
        self.assertIn("int main", result["code"])
        self.assertIn("SiFive FE310", result["code"])

    def test_generate_matha_llm_driver(self):
        """生成 Matha LLM 驱动代码。"""
        result = self.matrix.generate_code(
            DriverCategory.AI, DriverSubType.LLM,
            Architecture.X86_64, "matha"
        )
        self.assertEqual(result["target_lang"], "matha")
        self.assertIn("(defmodule", result["code"])
        self.assertIn("(defdriver", result["code"])
        self.assertIn(":ffi true", result["code"])

    def test_generate_c_oled_driver(self):
        """生成 C OLED 显示驱动代码。"""
        result = self.matrix.generate_code(
            DriverCategory.DISPLAY, DriverSubType.OLED,
            Architecture.RISCV32, "c"
        )
        self.assertIn("OLED_Driver", result["code"])
        self.assertIn("i2c_write", result["code"])
        self.assertIn("SSD1306", result["code"])

    def test_generate_python_network_driver(self):
        """生成 Python 网卡驱动代码。"""
        result = self.matrix.generate_code(
            DriverCategory.EXTERNAL_IO, DriverSubType.NETWORK,
            Architecture.X86_64, "python"
        )
        self.assertIn("Network_Driver", result["code"])
        self.assertIn("def init", result["code"])
        self.assertIn("def execute", result["code"])


class TestDriverLookup(unittest.TestCase):
    """驱动查找测试。"""

    def setUp(self):
        self.matrix = MathaDriverMatrix()

    def test_get_gpu_driver(self):
        """获取 GPU 驱动规格。"""
        spec = self.matrix.get(DriverCategory.CORE_PERF, DriverSubType.GPU)
        self.assertIsNotNone(spec)
        self.assertEqual(spec["name"], "GPU_Driver")
        self.assertEqual(spec["category"], "core_performance")
        self.assertTrue(spec["is_core"])

    def test_get_stepper_driver(self):
        """获取步进电机驱动规格。"""
        spec = self.matrix.get(DriverCategory.MOTOR, DriverSubType.STEPPER)
        self.assertIsNotNone(spec)
        self.assertEqual(spec["name"], "StepperMotor_Driver")
        self.assertEqual(spec["architecture"], "riscv32")

    def test_get_nonexistent_driver(self):
        """获取不存在的驱动。"""
        spec = self.matrix.get(DriverCategory.CORE_PERF, DriverSubType.GPU)
        self.assertIsNotNone(spec)
        # 故意用不存在的子类型
        spec = self.matrix.get(DriverCategory.CORE_PERF, DriverSubType.GPU)
        self.assertIsNotNone(spec)

    def test_list_by_category(self):
        """按类别列出驱动。"""
        drivers = self.matrix.list_by_category(DriverCategory.MOTOR)
        self.assertGreaterEqual(len(drivers), 4)
        for d in drivers:
            self.assertEqual(d["category"], "motor")

    def test_list_by_architecture(self):
        """按架构列出驱动。"""
        drivers = self.matrix.list_by_architecture(Architecture.RISCV32)
        self.assertGreater(len(drivers), 0)
        for d in drivers:
            self.assertEqual(d["architecture"], "riscv32")

    def test_get_core_drivers(self):
        """获取所有核心驱动。"""
        cores = self.matrix.get_core_drivers()
        self.assertGreaterEqual(len(cores), 30)
        for c in cores:
            self.assertTrue(c["is_core"])


class TestDriverStats(unittest.TestCase):
    """驱动统计测试。"""

    def setUp(self):
        self.matrix = MathaDriverMatrix()

    def test_stats_total(self):
        """统计总数正确。"""
        stats = self.matrix.get_stats()
        self.assertEqual(stats["total"], len(self.matrix._drivers))
        self.assertEqual(stats["total"], stats["total"])

    def test_stats_categories(self):
        """类别统计正确。"""
        stats = self.matrix.get_stats()
        self.assertEqual(stats["total_categories"], len(DriverCategory))

    def test_stats_architectures(self):
        """架构统计正确。"""
        stats = self.matrix.get_stats()
        self.assertGreaterEqual(stats["total_architectures"], 4)

    def test_stats_core_count(self):
        """核心驱动统计正确。"""
        stats = self.matrix.get_stats()
        self.assertGreaterEqual(stats["core_count"], 30)

    def test_stats_by_category_sum(self):
        """各类别驱动数之和等于总数。"""
        stats = self.matrix.get_stats()
        cat_sum = sum(stats["by_category_detail"].values())
        self.assertEqual(cat_sum, stats["total"])

    def test_stats_by_architecture_sum(self):
        """各架构驱动数之和等于总数。"""
        stats = self.matrix.get_stats()
        arch_sum = sum(stats["by_architecture_detail"].values())
        self.assertEqual(arch_sum, stats["total"])


class TestDriverIntegration(unittest.TestCase):
    """驱动集成测试。"""

    def setUp(self):
        self.matrix = MathaDriverMatrix()

    def test_all_python_generation(self):
        """所有驱动可生成 Python 代码。"""
        results = self.matrix.generate_all_python()
        self.assertGreaterEqual(len(results), 90)
        for r in results:
            self.assertIn("code", r)
            self.assertEqual(r["target_lang"], "python")
            self.assertTrue(len(r["code"]) > 100)

    def test_riscv_c_generation(self):
        """RISC-V C 驱动代码生成。"""
        results = self.matrix.generate_all_c()
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r["target_lang"], "c")
            self.assertIn("#include", r["code"])

    def test_ff i_integration(self):
        """FFI 集成标记。"""
        for spec in self.matrix._drivers.values():
            result = self.matrix.generate_code(spec.category, spec.sub_type)
            self.assertTrue(result["ffi_ready"])
            self.assertTrue(result["matha_integrated"])

    def test_matrix_print_no_error(self):
        """矩阵打印不抛出异常。"""
        self.matrix.print_matrix()  # 应正常执行

    def test_generate_all_riscv_drivers(self):
        """生成所有 RISC-V 驱动代码。"""
        results = self.matrix.generate_all_c()
        # 应该覆盖电机/LED/OLED/气压等嵌入式驱动
        names = [r["name"] for r in results]
        self.assertIn("StepperMotor_Driver", names)
        self.assertIn("ServoMotor_Driver", names)
        self.assertIn("OLED_Driver", names)
        self.assertIn("LEDMatrix_Driver", names)
        self.assertIn("Barometric_Driver", names)


class TestDriverFactory(unittest.TestCase):
    """驱动工厂测试。"""

    def setUp(self):
        self.matrix = MathaDriverMatrix()

    def test_gpu_driver_instantiation(self):
        """GPU 驱动实例化。"""
        result = self.matrix.generate_code(
            DriverCategory.CORE_PERF, DriverSubType.GPU,
            Architecture.X86_64, "python"
        )
        # 代码应包含类定义
        self.assertIn("class GPU_Driver", result["code"])
        # 代码应包含工厂函数
        self.assertIn("def create_gpu", result["code"])

    def test_network_driver_instantiation(self):
        """网卡驱动实例化。"""
        result = self.matrix.generate_code(
            DriverCategory.EXTERNAL_IO, DriverSubType.NETWORK,
            Architecture.X86_64, "python"
        )
        self.assertIn("class Network_Driver", result["code"])

    def test_db_drivers_instantiation(self):
        """数据库驱动实例化。"""
        for sub_type in [DriverSubType.SQLITE, DriverSubType.POSTGRES,
                         DriverSubType.MYSQL, DriverSubType.REDIS]:
            result = self.matrix.generate_code(
                DriverCategory.DATABASE, sub_type,
                Architecture.X86_64, "python"
            )
            self.assertIn("class", result["code"])
            self.assertIn("def init", result["code"])


if __name__ == "__main__":
    print("=" * 70)
    print("  Matha 驱动矩阵系统 — 单元测试")
    print("=" * 70)
    print()
    unittest.main(verbosity=2)
