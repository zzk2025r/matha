#!/usr/bin/env python3
"""全面检测 Matha 领域的不足与缺陷 - 补充版"""
import re, os
from pathlib import Path

domains = sorted(Path('src/domains').glob('*.py'))
issues = []
stats = []

for f in domains:
    name = f.stem
    if name == '__init__':
        continue
    with open(f, encoding='utf-8') as fh:
        content = fh.read()
    lines = content.count('\n')
    all_defs = re.findall(r'\ndef (\w+)\(', content)
    reg = [d for d in all_defs if d.startswith('_register_')]
    custom = [d for d in all_defs if not d.startswith('_') and not d.startswith('_curry')]
    cn_names = re.findall(r"""name\s*=\s*'([^']+)'""", content)
    cn_count = sum(1 for n in cn_names if any('\u4e00' <= c <= '\u9fff' for c in n))
    has_test = os.path.exists(f'tests/test_{name}.py')
    has_doc = '"""' in content
    todos = re.findall(r'(TODO|FIXME|XXX|HACK|deprecated)', content, re.IGNORECASE)

    # 重复定义检测
    def_lines = re.findall(r'^def (\w+)\(', content, re.MULTILINE)
    dupes = {}
    for d in def_lines:
        dupes[d] = dupes.get(d, 0) + 1
    dup_list = {k: v for k, v in dupes.items() if v > 1}

    stats.append({
        'name': name, 'lines': lines, 'funcs': len(all_defs),
        'custom': len(custom), 'cn': cn_count,
        'has_test': has_test, 'has_doc': has_doc,
        'todos': len(todos), 'dupes': dup_list,
        'reg_count': len(reg),
    })

    if not has_test:
        issues.append(('无测试', name, f'{len(all_defs)}函数'))
    if len(all_defs) <= 5:
        issues.append(('函数过少', name, f'仅{len(all_defs)}个'))
    if len(todos) > 0:
        issues.append(('TODO标记', name, f'{len(todos)}处'))
    if lines < 50:
        issues.append(('代码过少', name, f'仅{lines}行'))
    if dup_list:
        issues.append(('重复定义', name, str(list(dup_list.keys()))))

# 跨模块函数名冲突
all_regs = []
for s in stats:
    regs = re.findall(r'builtins\["([^"]+)"\]', s['content'])
    for r in regs:
        all_regs.append((r, s['name']))
seen = {}
for fn, mod in all_regs:
    if fn not in seen:
        seen[fn] = []
    seen[fn].append(mod)
conflicts = {fn: mods for fn, mods in seen.items() if len(mods) > 1}

# 评估
print('=' * 70)
print('  Matha 领域专业功能缺陷检测报告 (补充版)')
print('=' * 70)
print(f'\n领域总数: {len(stats)}')
print(f'总问题数: {len(issues)}')
print()

by_type = {}
for typ, name, detail in issues:
    if typ not in by_type:
        by_type[typ] = []
    by_type[typ].append((name, detail))

for typ, items in sorted(by_type.items()):
    print(f'[{typ}] ({len(items)}个)')
    for name, detail in items:
        print(f'  - {name}: {detail}')
    print()

print('--- 跨模块同名函数冲突 ---')
if conflicts:
    for fn, mods in sorted(conflicts.items()):
        print(f'  "{fn}": {mods}')
else:
    print('  无冲突')

print()
print('--- 无测试领域 (需补充测试) ---')
for name, detail in by_type.get('无测试', []):
    print(f'  {name}: {detail}')

print()
print('--- 重复定义 (需清理) ---')
for s in stats:
    if s['dupes']:
        print(f'  {s["name"]}: {s["dupes"]}')

print()
print('--- 完整领域中文函数统计 ---')
complete = [s for s in stats if s['funcs'] > 5]
print(f'完整领域数: {len(complete)}')
cn_domains = [s for s in complete if s['cn'] > 0]
no_cn = [s for s in complete if s['cn'] == 0]
print(f'有中文函数: {len(cn_domains)}')
print(f'无中文函数: {len(no_cn)}')
if no_cn:
    print('  无中文函数的领域:')
    for s in sorted(no_cn, key=lambda x: -x['funcs'])[:10]:
        test = '✓' if s['has_test'] else '✗'
        print(f'    {s["name"]:<25} {s["funcs"]}函数 {s["lines"]}行 {test}')

print()
print('--- 领域函数数分布 ---')
buckets = {'<5': 0, '5-10': 0, '10-20': 0, '20-30': 0, '30-50': 0, '>50': 0}
for s in stats:
    n = s['funcs']
    if n < 5:
        buckets['<5'] += 1
    elif n < 10:
        buckets['5-10'] += 1
    elif n < 20:
        buckets['10-20'] += 1
    elif n < 30:
        buckets['20-30'] += 1
    elif n < 50:
        buckets['30-50'] += 1
    else:
        buckets['>50'] += 1
for k, v in buckets.items():
    bar = '█' * v
    print(f'  {k:>6}: {v:>2} {bar}')

print()
print('=' * 70)
