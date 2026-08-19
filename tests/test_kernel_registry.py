# -*- coding: utf-8 -*-
"""Kernel 与 Registry 基础设施测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest


class TestKernel(unittest.TestCase):
    """kernel 模块重导出验证。"""

    def test_import_kernel_module(self):
        from src.domains import kernel
        self.assertTrue(hasattr(kernel, '_register_kernel_builtins'))
        self.assertTrue(hasattr(kernel, 'kernel_symtab_names'))

    def test_register_alias(self):
        from src.domains import kernel
        builtins = {}
        kernel._register_kernel(builtins)
        self.assertGreater(len(builtins), 0)

    def test_mechanics_alias(self):
        from src.domains import kernel
        builtins = {}
        kernel._register_mechanics(builtins)
        self.assertGreater(len(builtins), 0)

    def test_symtab_names(self):
        from src.domains.kernel_math import kernel_symtab_names
        names = kernel_symtab_names()
        self.assertGreater(len(names), 10)

    def test_registered_functions(self):
        from src.domains import kernel
        builtins = {}
        kernel._register_kernel(builtins)
        self.assertIn('syscall_号', builtins)
        self.assertIn('pcb_大小', builtins)
        self.assertIn('页表项数', builtins)
        self.assertIn('中断延迟', builtins)


class TestRegistry(unittest.TestCase):
    """Registry 基础设施测试。"""

    def test_import_registry(self):
        from src.domains.registry import DomainRegistry, get_registry
        self.assertTrue(callable(get_registry))
        self.assertIsNotNone(DomainRegistry)

    def test_domain_registry_create(self):
        from src.domains.registry import DomainRegistry
        reg = DomainRegistry()
        self.assertIsInstance(reg, DomainRegistry)

    def test_register_domain(self):
        from src.domains.registry import DomainMeta, DomainRegistry
        meta = DomainMeta(
            name='test', display_name='Test',
            description='Test domain', module='test_mod'
        )
        reg = DomainRegistry()
        reg.register('test', meta)
        self.assertIn('test', reg._domains)

    def test_get_domain(self):
        from src.domains.registry import DomainMeta, DomainRegistry
        meta = DomainMeta(
            name='test2', display_name='Test2',
            description='Test2', module='test_mod2'
        )
        reg = DomainRegistry()
        reg.register('test2', meta)
        result = reg.get('test2')
        self.assertIsNotNone(result)

    def test_all_domains_registered(self):
        """验证所有领域都已正确注册。"""
        from src.domains.registry import get_registry
        reg = get_registry()
        domain_names = list(reg._domains.keys())
        self.assertGreater(len(domain_names), 20)
        key_domains = ['AI_DataScience', 'SoftwareAppDev', 'GameImmersion',
                       'QuantumComputing', 'ChaosFractal', 'BlockchainWeb3',
                       'CreativeCoding', 'GeneticAlgorithm']
        for d in key_domains:
            self.assertIn(d, domain_names, f'领域 {d} 未注册')

    def test_domain_compile(self):
        from src.domains.registry import domain_compile
        # domain_compile expects Matha source code string
        result = domain_compile("func add(x, y) { x + y }", "matha")
        self.assertIsNotNone(result)

    def test_get_registry_singleton(self):
        from src.domains.registry import get_registry
        r1 = get_registry()
        r2 = get_registry()
        self.assertIs(r1, r2)

    def test_domain_meta_fields(self):
        from src.domains.registry import DomainMeta
        meta = DomainMeta(
            name='test', display_name='Test',
            description='A test domain', module='src.domains.test'
        )
        self.assertEqual(meta.name, 'test')
        self.assertEqual(meta.display_name, 'Test')
        self.assertEqual(meta.category, 'general')
        self.assertEqual(meta.targets, ['c', 'python', 'matha'])

    def test_registered_domain_count(self):
        """验证注册表包含所有预期领域。"""
        from src.domains.registry import get_registry
        reg = get_registry()
        domain_names = list(reg._domains.keys())
        self.assertGreaterEqual(len(domain_names), 27)
        expected = [
            'AI_DataScience', 'SoftwareAppDev', 'GameImmersion',
            'Automation', 'IoTHardware', 'OSNetwork', 'BlockchainWeb3',
            'AudioVideo', 'GraphicsRender', 'HPC', 'FinTech',
            'AutonomousDriving', 'AerospaceDefense', 'BioComputing',
            'HardwareReverse', 'SpatialMeta', 'AlgoTrading', 'CompChem',
            'GreenTech', 'MetaverseArch', 'DigitalRights', 'CreativeCoding',
            'GeneticAlgorithm', 'QuantumComputing', 'ChaosFractal',
            'ComputationalLaw', 'GeekGray',
        ]
        for e in expected:
            self.assertIn(e, domain_names, f'缺失领域: {e}')


if __name__ == '__main__':
    unittest.main()
