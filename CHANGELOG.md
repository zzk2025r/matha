# Changelog

All notable changes to this project will be documented in this file.

---

## [v3.1.0] - 2026-08-19

### Performance
- **Lexer**: 长标识符/数字构建由字符串拼接改为 `list.append()` + `''.join()`，消除 O(n²) 累积
- **Lexer**: `is_cjk()` 由 `any()` 遍历改为 early-return，减少 CJK 字符检查开销
- **Parser**: `_has_conditional_suffix()` / `_parse_conditional_binding()` 移除 `list(self.tokens)` 全量拷贝，改用 `pos` 保存/恢复
- **Interpreter**: `_domain_registers` 去重，65 条重复注册条目精简为 27 条唯一条目
- **Codegen/MIR**: `_compile_expr` 由字符串 `type.__name__` 链式比较改为 `type` 分派缓存，首次查找后 O(1)

### Bug Fixes
- **spatial_meta.py**: 删除文件末尾重复的 `_curry8` 定义（19 行）
- **interp.py**: 修复斐波那契递归函数因闭包共享导致的错误结果（`-80` → `55`）

### New Features
- **graph.py**: 新增 `_register_graph()`，注册 17 个图算法（BFS/DFS/Dijkstra/Prim/Kruskal 等）
- **23 个新测试文件**: 覆盖此前无测试的完整领域

### Documentation
- 新增 `docs/MATHA_DOMAIN_COMPLETION_REPORT.md` — 领域完成度报告
- 新增 `scripts/benchmark_performance.py` — 性能基准测试脚本
- 更新 `docs/FINAL_UPGRADE_REPORT_v3.0.md`

---

## [v3.0.0] - 2026-08-18

### Features
- **57 个领域模块**，覆盖数学、物理、化学、生物、工程、金融、AI、游戏等全领域
- **1,323 个自定义函数**，平均 23.2 个/领域
- **2,356 个中文函数名**，中文优先设计
- **Flutter 移动端** — 节点编辑器 + WebSocket 协作

### Architecture
- 自举验证: 77 项全部通过
- 测试覆盖: 488 Python + 11 Flutter 测试
- 协作系统: WebSocket 端到端测试通过
- WASM 构建: 支持浏览器部署

---

## [v2.5.0] - 2026-08-17

### Features
- **17 个新增领域**: aerospace, algo_trading, comp_chem, digital_rights, green_tech, hardware_reverse, hpc, iot_hardware, metaverse_arch, audio_video, bio_computing, fintech, graphics, os_network, automation, spatial_meta, kernel_math
- **software_app** 真实化: SQLite 持久化 + JWT 认证 + PBKDF2 密码哈希
- **协作系统**: WebSocket 多人实时编辑 + Conflict Strategy 选择

---
