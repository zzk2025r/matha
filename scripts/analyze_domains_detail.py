#!/usr/bin/env python3
"""分析每个域的具体状态，找出需要补充的内容"""
import re, os
from pathlib import Path

domains = sorted(Path('src/domains').glob('*.py'))
results = {}
for f in domains:
    name = f.stem
    if name == '__init__':
        continue
    with open(f, encoding='utf-8') as fh:
        content = fh.read()
    # 找 _register_xxx 函数
    reg_match = re.search(r'def _register_\w+\(.*?\):\n((?:    .*\n)*)', content)
    reg_body = reg_match.group(1) if reg_match else ''
    # 找所有函数定义
    fn_defs = re.findall(r'\n    def (\w+)\(', content)
    # 找自定义函数（非内部）
    custom = [d for d in fn_defs if not d.startswith('_')]
    # 找中文
    cn_names = re.findall(r"name\s*=\s*'([^']+)'", content)
    cn_count = sum(1 for n in cn_names if any('\u4e00' <= c <= '\u9fff' for c in n))
    # 找文档
    doc_lines = [l for l in content.split('\n') if l.strip().startswith('#') and len(l.strip()) > 5]
    doc_count = len(doc_lines)
    # 找测试
    test_name = f'tests/test_{name}.py'
    has_test = os.path.exists(test_name)
    results[name] = {
        'funcs': len(fn_defs),
        'custom': len(custom),
        'cn': cn_count,
        'docs': doc_count,
        'test': has_test,
        'content': content[:200]
    }

# 分类
empty = [(n, r) for n, r in results.items() if r['funcs'] == 0]
partial = [(n, r) for n, r in results.items() if 0 < r['funcs'] <= 3]
complete = [(n, r) for n, r in results.items() if r['funcs'] > 3]

print(f'总计: {len(results)} 个域')
print(f'空壳: {len(empty)}, 部分: {len(partial)}, 完整: {len(complete)}')
print()

print('=== 空壳域内容摘要 ===')
for n, r in sorted(empty):
    lines = r['content'].count('\n')
    # 找注释行
    comments = sum(1 for l in r['content'].split('\n') if l.strip().startswith('#'))
    print(f'  {n}: {lines}行, {comments}注释行')
    print(f'    {r["content"][:300].replace(chr(10), " | ")}')
    print()

print('=== 部分域函数列表 ===')
for n, r in sorted(partial, key=lambda x: -x[1]['funcs']):
    print(f'  {n}: {r["funcs"]}函数, {r["custom"]}自定义, {r["cn"]}中文, test={r["test"]}')
