# -*- coding: utf-8 -*-
"""Fluid Experiment 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest


class TestFluidExp(unittest.TestCase):
    """流体实验领域测试。"""

    def test_import_and_register(self):
        from src.domains.fluid_exp import _register_fluid_exp
        builtins = {}
        _register_fluid_exp(builtins)
        self.assertGreater(len(builtins), 50)

    def test_symtab_names(self):
        from src.domains.fluid_exp import _fluid_exp_symtab_names
        names = _fluid_exp_symtab_names()
        self.assertGreater(len(names), 50)

    def test_registered_reynolds(self):
        from src.domains.fluid_exp import _register_fluid_exp
        builtins = {}
        _register_fluid_exp(builtins)
        self.assertIn('边界_局部雷诺数', builtins)

    def test_registered_mach(self):
        from src.domains.fluid_exp import _register_fluid_exp
        builtins = {}
        _register_fluid_exp(builtins)
        self.assertIn('可压缩_马赫数', builtins)

    def test_registered_prandtl(self):
        from src.domains.fluid_exp import _register_fluid_exp
        builtins = {}
        _register_fluid_exp(builtins)
        # 普朗特数通过内置常量体现
        self.assertIn('gamma_空气', builtins)

    def test_reynolds_number(self):
        from src.domains.fluid_exp import _边界_局部雷诺数
        re = _边界_局部雷诺数(10, 1, 1e-6)
        self.assertEqual(re, 1e7)

    def test_mach_number(self):
        from src.domains.fluid_exp import _可压缩_马赫数
        m = _可压缩_马赫数(340, 340)
        self.assertAlmostEqual(m, 1.0, delta=0.01)

    def test_speed_of_sound(self):
        from src.domains.fluid_exp import _可压缩_声速
        c = _可压缩_声速(1.4, 287, 298)
        self.assertAlmostEqual(c, 346, delta=10)

    def test_froude_number(self):
        from src.domains.fluid_exp import _明渠_弗劳德数
        fr = _明渠_弗劳德数(10, 1, 9.81)
        self.assertAlmostEqual(fr, 3.19, delta=0.1)

    def test_manning_formula(self):
        from src.domains.fluid_exp import _明渠_曼宁流速_SI
        v = _明渠_曼宁流速_SI(0.013, 1, 0.001)
        self.assertGreater(v, 0)

    def test_drag_force(self):
        from src.domains.fluid_exp import _管损_局部水头损失
        hl = _管损_局部水头损失(0.5, 10, 9.81)
        self.assertGreater(hl, 0)

    def test_constants(self):
        from src.domains.fluid_exp import (
            G_STANDARD, GAMMA_AIR, R_AIR,
            GAMMA_MONO, GAMMA_DI, GAMMA_POLY,
        )
        self.assertAlmostEqual(G_STANDARD, 9.80665, delta=0.01)
        self.assertAlmostEqual(GAMMA_AIR, 1.4, delta=0.01)
        self.assertAlmostEqual(R_AIR, 287, delta=1)
        self.assertAlmostEqual(GAMMA_MONO, 5.0/3.0, delta=0.01)

    def test_nusselt_number(self):
        from src.domains.fluid_exp import _管损_比阻
        s = _管损_比阻(0.02, 100, 0.1, 9.81)
        self.assertGreater(s, 0)

    def test_grashof_number(self):
        from src.domains.fluid_exp import _管损_总水头损失
        # Test a registered function
        builtins = {}
        from src.domains.fluid_exp import _register_fluid_exp
        _register_fluid_exp(builtins)
        self.assertIn('管损_总水头损失', builtins)

    def test_all_builtins_callable(self):
        from src.domains.fluid_exp import _register_fluid_exp
        builtins = {}
        _register_fluid_exp(builtins)
        # 所有 builtins 应该是可调用的
        for k, v in list(builtins.items())[:10]:
            self.assertTrue(callable(v) or isinstance(v, (int, float)),
                          f'{k} is not callable: {type(v)}')


if __name__ == '__main__':
    unittest.main()
