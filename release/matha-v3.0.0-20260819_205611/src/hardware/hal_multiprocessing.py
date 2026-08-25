# -*- coding: utf-8 -*-
"""HAL Multiprocessing 并发写入（重导出模块）

本模块从 src.hardware.hal 重导出 multiprocessing worker 函数，
供外部代码方便导入。

用法：
  from src.hardware.hal import (
      run_multiprocess_stress_test,
      _gpio_writer_worker,
      _gpio_batch_writer_worker,
  )
  # 或
  from src.hardware.hal_multiprocessing import (
      run_multiprocess_stress_test,
      gpio_writer_worker,      # 别名
      gpio_batch_writer_worker,
  )
"""
from src.hardware.hal import (
    run_multiprocess_stress_test,
    _gpio_writer_worker as gpio_writer_worker,
    _gpio_batch_writer_worker as gpio_batch_writer_worker,
)

__all__ = [
    "run_multiprocess_stress_test",
    "gpio_writer_worker",
    "gpio_batch_writer_worker",
]
