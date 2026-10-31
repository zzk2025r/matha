# -*- coding: utf-8 -*-
"""工具型插件包（非领域插件）。

与 `src/domains/`（81 个领域插件，经 `src/plugin_api.py` 联邦契约按需加载）不同，
本目录放的是**编译器工具插件**：它们依赖内核公开接口，但内核绝不反向依赖它们。

  * `parallel_parser` —— 线程池批量解析（内核解析保持单线程确定性）
  * `toolchain_llvm` —— 外部 LLVM 工具链（llc/clang 子进程）；工具缺失即
    抛 `ToolchainUnavailable`，不提供任何「模拟成功」
  * `toolchain_msvc` —— 外部汇编/链接工具链（nasm/link），同上
  * `toolchain_signature` —— 包签名工具链（cosign/sigstore）
  * `device_config` / `deps_probe` / `ffi` / `interop` / `ffi_sdk` / `tree_sitter_*` ——
    需 ctypes / 子进程 / 第三方解析器生成器的硬件探测与外部能力，阶段 3 从
    `src/` 根目录搬入本层（内核不反向依赖）
  * `numpy_accel` —— 需 NumPy 的数组内建（`numpy数组` 等）；环境无 NumPy
    则立即抛 `NumpyBackendUnavailable`，不再 `try/except ImportError: pass` 静默降级
  * `legacy_mir_vm` —— 原 `src/vm.py`（MIR 级栈式解释器，阶段 2 归档）：主链不
    走它，仅多语言前端交叉验证需要直接执行 MIR 时显式 import
  * `src/m3v_vm.py`（第三条重复 VM，内含坏导入 `import compiler_matha`）已删除，
    历史由 git 保留；主链执行入口只看 `src/kernel/exec_api.py`

内核与插件的方向性由 `scripts/dep_audit.py` + `tests/test_kernel_purity.py` 静态
把守：`src/parser.py` 里出现 `threading` / `concurrent.futures` 即 CI 失败。
"""
