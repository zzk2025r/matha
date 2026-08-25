#!/usr/bin/env python3
"""重新统计：包含所有以 _ 开头的中文函数"""
import re, os
from pathlib import Path

domains = sorted(Path('src/domains').glob('*.py'))
results = []
for f in domains:
    name = f.stem
    if name == '__init__':
        continue
    with open(f, encoding='utf-8') as fh:
        content = fh.read()
    lines = content.count('\n')
    # 所有顶层 def（非 class 方法）
    all_defs = re.findall(r'\ndef (\w+)\(', content)
    # 注册函数
    reg = [d for d in all_defs if d.startswith('_register_')]
    # 所有其他 def（含中文、含 _ 前缀）
    custom = [d for d in all_defs if not d.startswith('_register_') and not d.startswith('_curry')]
    # 中文函数
    cn_names = re.findall(r"""name\s*=\s*'([^']+)'""", content)
    cn_count = sum(1 for n in cn_names if any('\u4e00' <= c <= '\u9fff' for c in n))
    # 测试
    has_test = os.path.exists(f'tests/test_{name}.py')
    results.append((name, len(all_defs), len(custom), len(reg), cn_count, has_test, lines))

# 分类
empty = [r for r in results if r[1] == 0]
partial = [r for r in results if 0 < r[1] <= 5]
complete = [r for r in results if r[1] > 5]

total_defs = sum(r[1] for r in results)
total_custom = sum(r[2] for r in results)
total_cn = sum(r[4] for r in results)
total_test = sum(1 for r in results if r[5])
total_lines = sum(r[6] for r in results)

print(f'领域模块总数: {len(results)}')
print(f'完整领域(>5函数): {len(complete)}, 部分领域(<=5函数): {len(partial)}, 空壳: {len(empty)}')
print(f'总函数数: {total_defs}')
print(f'自定义函数: {total_custom}')
print(f'中文函数: {total_cn}')
print(f'有测试: {total_test}/{len(results)}')
print(f'总代码行数: {total_lines}')
print()

print(f'{"领域":<25} {"总def":>6} {"自定义":>7} {"注册":>4} {"中文":>4} {"测试":>4} {"行数":>5}')
print('-'*70)
for r in sorted(results, key=lambda x: -x[1]):
    status = '✅' if r[1] > 5 else ('⚠️' if r[1] > 0 else '❌')
    print(f'{r[0]:<25} {r[1]:>6} {r[2]:>7} {r[3]:>4} {r[4]:>4} {"✓" if r[5] else "✗":>4} {r[6]:>5}  {status}')

print()
print('=== 空壳/部分领域 ===')
for r in sorted(empty + partial, key=lambda x: x[1]):
    print(f'  {r[0]}: {r[1]}def, {r[2]}custom, {r[4]}cn, test={"✓" if r[5] else "✗"}')
