# -*- coding: utf-8 -*-
"""Kernel Math 领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.kernel_math import (
    syscall_num, syscall_entry_size, syscall_latency_ns,
    pcb_size, pcb_alloc_cost, pcb_context_switch_cycles,
    page_table_entries, page_table_overhead_bytes,
    linear_address, virtual_to_physical,
    interrupt_latency_us, exception_vector,
    scheduler_tick_latency_us, context_switch_overhead_us,
    throughput_max_tasks, kernel_mem_layout, total_kernel_mem,
)


class TestKernelMath(unittest.TestCase):
    def test_syscall_num(self):
        self.assertEqual(syscall_num('read'), 3)
        self.assertEqual(syscall_num('exit'), 1)

    def test_syscall_entry_size(self):
        size = syscall_entry_size(10)
        self.assertGreater(size, 0)

    def test_syscall_latency(self):
        ns = syscall_latency_ns(False)
        self.assertGreater(ns, 0)

    def test_pcb_size(self):
        size = pcb_size(18, 4096)
        self.assertGreater(size, 0)

    def test_pcb_alloc_cost(self):
        cost = pcb_alloc_cost(10, 4096)
        self.assertGreater(cost, 0)

    def test_pcb_switch_cycles(self):
        cycles = pcb_context_switch_cycles(18)
        self.assertGreater(cycles, 0)

    def test_page_table_entries(self):
        entries = page_table_entries(4096, 4 * 1024 * 1024 * 1024)
        self.assertGreater(entries, 0)

    def test_page_table_overhead(self):
        overhead = page_table_overhead_bytes(4096, 4 * 1024 * 1024 * 1024)
        self.assertGreater(overhead, 0)

    def test_linear_address(self):
        addr = linear_address(1, 0x1000, 4096)
        self.assertGreater(addr, 0)

    def test_virtual_to_physical(self):
        result = virtual_to_physical(0x1000, 4096)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result, (1, 0))

    def test_interrupt_latency(self):
        us = interrupt_latency_us(0, True)
        self.assertGreater(us, 0)

    def test_exception_vector(self):
        vec = exception_vector(1)
        self.assertIsInstance(vec, str)
        self.assertGreater(len(vec), 0)

    def test_scheduler_tick(self):
        us = scheduler_tick_latency_us(3000)
        self.assertGreater(us, 0)

    def test_context_switch_overhead(self):
        us = context_switch_overhead_us(3000, 18)
        self.assertGreater(us, 0)

    def test_throughput_tasks(self):
        n = throughput_max_tasks(100, 1000)
        self.assertGreater(n, 0)

    def test_kernel_mem_layout(self):
        layout = kernel_mem_layout()
        self.assertIsInstance(layout, dict)

    def test_total_kernel_mem(self):
        total = total_kernel_mem({'text': (0, 1024), 'data': (1024, 512)})
        self.assertEqual(total, 1536)


if __name__ == '__main__':
    unittest.main()
