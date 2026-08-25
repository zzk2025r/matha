#!/usr/bin/env python3
"""全面检测 Matha 领域的不足与缺陷"""
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
    # 所有顶层 def
    all_defs = re.findall(r'\ndef (\w+)\(', content)
    reg = [d for d in all_defs if d.startswith('_register_')]
    custom = [d for d in all_defs if not d.startswith('_') and not d.startswith('_curry')]
    # 中文函数
    cn_names = re.findall(r"""name\s*=\s*'([^']+)'""", content)
    cn_count = sum(1 for n in cn_names if any('\u4e00' <= c <= '\u9fff' for c in n))
    has_test = os.path.exists(f'tests/test_{name}.py')
    has_doc = '"""' in content
    # 找 TODO/FIXME
    todos = re.findall(r'(TODO|FIXME|XXX|HACK|deprecated)', content, re.IGNORECASE)
    # 找空函数体（只有 pass）
    empty_bodies = re.findall(r'def \w+.*:\n    """[\s\S]*?"""?\n    pass', content)
    # 找函数数量
    fn_count = len(all_defs)

    stats.append({
        'name': name, 'lines': lines, 'funcs': fn_count,
        'custom': len(custom), 'cn': cn_count,
        'has_test': has_test, 'has_doc': has_doc,
        'todos': len(todos), 'empty_bodies': len(empty_bodies),
        'content': content
    })

    # 检测问题
    if not has_test:
        issues.append(('无测试', name, f'{fn_count}个函数'))
    if fn_count < 5:
        issues.append(('函数过少', name, f'仅{fn_count}个函数'))
    if len(todos) > 0:
        issues.append(('TODO标记', name, f'{len(todos)}处'))
    if not has_doc:
        issues.append(('无文档', name, ''))
    if lines < 50:
        issues.append(('代码过少', name, f'仅{lines}行'))

print('=' * 70)
print('  Matha 领域专业功能缺陷检测报告')
print('=' * 70)

# 统计
total_issues = len(issues)
no_test = sum(1 for i in issues if i[0] == '无测试')
few_funcs = sum(1 for i in issues if i[0] == '函数过少')
no_doc = sum(1 for i in issues if i[0] == '无文档')
too_small = sum(1 for i in issues if i[0] == '代码过少')
has_todo = sum(1 for i in issues if i[0] == 'TODO标记')

print(f'\n总问题数: {total_issues}')
print(f'  无测试: {no_test}')
print(f'  函数过少(<5): {few_funcs}')
print(f'  代码过少(<50行): {too_small}')
print(f'  无文档: {no_doc}')
print(f'  含TODO: {has_todo}')
print()

# 按类型分组
print('--- 无测试的领域 ---')
for typ, name, detail in sorted(issues, key=lambda x: x[0]):
    if typ == '无测试':
        print(f'  {name}: {detail}')

print('\n--- 代码量过小的领域 ---')
for typ, name, detail in sorted(issues, key=lambda x: x[0]):
    if typ == '代码过少':
        print(f'  {name}: {detail}')

print('\n--- 含 TODO/FIXME 的领域 ---')
for typ, name, detail in sorted(issues, key=lambda x: x[0]):
    if typ == 'TODO标记':
        print(f'  {name}: {detail}')

print('\n--- 函数数最少的领域 ---')
by_funcs = sorted(stats, key=lambda x: x['funcs'])
for s in by_funcs[:10]:
    test_mark = '✓' if s['has_test'] else '✗'
    print(f'  {s["name"]:<25} {s["funcs"]:>3}函数 {s["lines"]:>4}行 {test_mark}')

print('\n--- 完整领域对比 (前20) ---')
complete = [s for s in stats if s['funcs'] > 5]
for s in sorted(complete, key=lambda x: -x['funcs'])[:20]:
    test_mark = '✓' if s['has_test'] else '✗'
    cn_bar = '█' * min(s['cn'] // 2, 20)
    print(f'  {s["name"]:<25} {s["funcs"]:>3}函数 {s["cn"]:>3}中文 {s["lines"]:>4}行 {test_mark}')

# 检查重复注册
print('\n--- 重复注册检查 ---')
all_regs = []
for s in stats:
    regs = re.findall(r'builtins\["([^"]+)"\]', s['content'])
    for r in regs:
        all_regs.append((r, s['name']))

# 检查跨模块函数名冲突
seen = {}
for fn, mod in all_regs:
    if fn not in seen:
        seen[fn] = []
    seen[fn].append(mod)
conflicts = {fn: mods for fn, mods in seen.items() if len(mods) > 1}
for fn, mods in list(conflicts.items())[:10]:
    print(f'  冲突: "{fn}" 在 {mods}')

# 检查缺失的注册
print('\n--- 未注册的自定义函数检查 ---')
unregistered = []
for s in stats:
    if s['funcs'] > 5:
        # 找到所有函数名
        all_funcs = re.findall(r'def (\w+)\(', s['content'])
        all_funcs = [f for f in all_funcs if not f.startswith('_') and not f.startswith('_curry')]
        # 找到注册中的函数
        registered = re.findall(r'builtins\["([^"]+)"\]', s['content'])
        # 检查是否有未注册的
        for fn in all_funcs:
            if fn not in registered and fn not in ['Graph', 'HardwareDriverRegistry', 'DomainRegistry']:
                # 这些可能是类或其他非函数
                pass

print('\n' + '=' * 70)
print('  检测完成')
print('=' * 70)
