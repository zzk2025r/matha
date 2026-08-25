#!/usr/bin/env python3
"""详细分析每个域的函数情况"""
import re, os
from pathlib import Path

domains = sorted(Path('src/domains').glob('*.py'))
for f in domains:
    name = f.stem
    if name == '__init__':
        continue
    with open(f, encoding='utf-8') as fh:
        content = fh.read()
    lines = content.count('\n')
    # 找所有 def 行
    all_defs = re.findall(r'\ndef (\w+)\(', content)
    reg_defs = [d for d in all_defs if d.startswith('_register_')]
    custom_defs = [d for d in all_defs if not d.startswith('_') and d not in ('GameConfig',)]
    # 跳过 dataclass 等
    custom_defs = [d for d in custom_defs if not d[0].isupper()]
    has_test = os.path.exists(f'tests/test_{name}.py')
    has_register = len(reg_defs) > 0
    print(f'{name:<25} lines={lines:>4}  defs={len(all_defs):>3}  reg={len(reg_defs):>2}  custom={len(custom_defs):>3}  test={has_test}  reg_func={reg_defs[0] if reg_defs else "NONE"}')
