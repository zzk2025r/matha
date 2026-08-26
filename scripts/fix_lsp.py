# -*- coding: utf-8 -*-
"""Fix lsp.py completions bug"""
path = r'd:\trae\src\lsp.py'
content = open(path, 'r', encoding='utf-8').read()

# Fix 1: fn_name check - remove 'and fn_name != trigger'
content = content.replace(
    "if fn_name.lower().startswith(trigger.lower()) and fn_name != trigger:",
    "if fn_name.lower().startswith(trigger.lower()):"
)

# Fix 2: cls_name check - remove 'and cls_name != trigger'
content = content.replace(
    "if cls_name.lower().startswith(trigger.lower()) and cls_name != trigger:",
    "if cls_name.lower().startswith(trigger.lower()):"
)

# Fix 3: var_name regex and check
old_var_section = """            # 变量
            for m in re.finditer(r'(\\w+)\\s*[:=]', ln):
                var_name = m.group(1)
                if var_name.lower().startswith(trigger.lower()) and var_name not in (
                    'if', 'else', 'for', 'while', 'def', 'class', 'return', 'import'
                ):"""
new_var_section = """            # 变量（排除数字和保留字）
            for m in re.finditer(r'\\b(\\w+)\\s*[:=]', ln):
                var_name = m.group(1)
                if (var_name.lower().startswith(trigger.lower())
                        and not var_name.isdigit()
                        and var_name not in (
                    'if', 'else', 'for', 'while', 'def', 'class',
                    'return', 'import', 'not', 'and', 'or', 'in', 'is')):"""
content = content.replace(old_var_section, new_var_section)

open(path, 'w', encoding='utf-8').write(content)
print('lsp.py fixed')

# Verify
content2 = open(path, 'r', encoding='utf-8').read()
assert 'fn_name != trigger' not in content2, "Fix 1 failed"
assert 'cls_name != trigger' not in content2, "Fix 2 failed"
assert r'\b(\w+)\s*[:=]' in content2, "Fix 3 failed"
print('All fixes verified')
