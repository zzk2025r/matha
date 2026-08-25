#!/usr/bin/env python3
"""分析所有领域模块的完成度"""
import re, os
from pathlib import Path

domains = sorted(Path('src/domains').glob('*.py'))
empty = []
partial = []
complete = []
all_details = []

for f in domains:
    name = f.stem
    with open(f, encoding='utf-8') as fh:
        content = fh.read()
    # 统计函数定义（在 _register_xxx 函数体内）
    fn_defs = re.findall(r'\n    def (\w+)\(', content)
    # 统计中文函数名
    cn_names = re.findall(r"name\s*=\s*'([^']+)'", content)
    cn_count = sum(1 for n in cn_names if any('\u4e00' <= c <= '\u9fff' for c in n))
    # 统计所有函数名（含英文）
    all_fn_names = [d for d in fn_defs if not d.startswith('_')]
    all_details.append((name, len(fn_defs), cn_count, len(all_fn_names)))

    if len(fn_defs) == 0:
        empty.append((name, 0, cn_count))
    elif len(fn_defs) <= 3:
        partial.append((name, len(fn_defs), cn_count))
    else:
        complete.append((name, len(fn_defs), cn_count))

print('=' * 60)
print('  Matha 领域专业功能完成度报告')
print('=' * 60)
print(f'\n领域模块总数: {len(domains)}')
print(f'  完整领域 (>3个函数): {len(complete)}')
print(f'  部分领域 (1-3个函数): {len(partial)}')
print(f'  空壳领域 (0个函数):   {len(empty)}')
print()

total_custom = sum(d[1] for d in all_details)
total_cn = sum(d[2] for d in all_details)
print(f'自定义函数总数: {total_custom}')
print(f'中文函数总数:   {total_cn}')
print()

print('-' * 60)
print(f'{"领域":<32} {"函数数":>6} {"中文":>6}')
print('-' * 60)
for name, fns, cn, _ in sorted(all_details, key=lambda x: -x[1]):
    bar = '█' * min(fns // 2, 20)
    if fns == 0:
        status = '  空壳'
    elif fns <= 3:
        status = '  部分'
    else:
        status = '  完整'
    print(f'{name:<32} {fns:>6} {cn:>6}  {bar} {status}')

print()
if partial:
    print('部分领域（可补充函数）:')
    for n, f, c in sorted(partial, key=lambda x: -x[1]):
        print(f'  - {n}: {f}个函数, {c}个中文')

if empty:
    print('\n空壳领域（需完全实现）:')
    for n, f, c in sorted(empty, key=lambda x: -x[1]):
        print(f'  - {n}: 0个函数')

print()
print('=' * 60)
completion_rate = len(complete) / len(domains) * 100 if domains else 0
print(f'领域完成度: {len(complete)}/{len(domains)} = {completion_rate:.1f}%')
func_completion = total_custom / max(len(domains) * 10, 1) * 100
print(f'函数密度:   {total_custom}个函数 / {len(domains)}个领域 = {total_custom/len(domains):.1f}个/领域')
print('=' * 60)
