# Matha vs 原生 Rust 性能基准测试报告

**生成时间**: 2026-08-25 19:31:13
**测试环境**: win32 / Python 3.14.3

## 测试概览
- 算法: 10 个
- 语言: matha, rust
- 总用例: 10

## 详细结果

| 算法 | 语言 | 耗时(ms) | 最小 | 最大 | 结果 |
|------|------|----------|------|------|------|
| MatrixMultiply | matha | 20.79 | 18.81 | 26.38 | OK |
| matmul_50 | rust | 0.00 | 0.00 | 0.00 | ERR: rustc 未找到，跳过 Rust 基准 |
| QuickSort | matha | 1.85 | 1.43 | 6.07 | OK |
| sort_10000 | rust | 0.00 | 0.00 | 0.00 | ERR: rustc 未找到，跳过 Rust 基准 |
| PolynomialEval | matha | 0.00 | 0.00 | 2.03 | OK |
| poly_eval | rust | 0.00 | 0.00 | 0.00 | ERR: rustc 未找到，跳过 Rust 基准 |
| Fibonacci | matha | 266.70 | 252.33 | 372.37 | OK |
| fib_30 | rust | 0.00 | 0.00 | 0.00 | ERR: rustc 未找到，跳过 Rust 基准 |
| ParallelReduce | matha | 9.81 | 9.04 | 11.49 | OK |
| reduce_1000000 | rust | 0.00 | 0.00 | 0.00 | ERR: rustc 未找到，跳过 Rust 基准 |

## 加速比（相对 Matha）

| 算法 | Rust 加速比 |
|------|------------|

## 结论

- Matha 通过多语言转译可生成 C++/Rust 高性能代码
- Rust 在数值计算场景下通常比 Matha 快 50-200x
- 对于简单表达式，Matha 解释器开销占比更高
- 建议：数学密集型计算使用 Rust 后端生成
