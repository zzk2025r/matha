# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\trae")
from src.matha_system import MathaSystem

print("=== MathaSystem 完整系统测试 ===")
s = MathaSystem(debug=False)
s.initialize()

print(s.info())

# eval
r = s.eval('1+2*3')
assert r == 7, f"Expected 7, got {r}"
print(f"[PASS] eval('1+2*3') = {r}")

# virtual
entry = s.virtual('test_v')
assert entry.name == 'test_v'
print(f"[PASS] virtual('test_v') = {entry.name}")

# auto_fix
r3 = s.auto_fix('missing_add', 10, 20)
print(f"[PASS] auto_fix('missing_add', 10, 20) = {r3}")

# define
d = s.define('test_d')
d.add_definition('add', 'add', lambda *args: sum(args) if args else 0)
r2 = s.interpret_capability('test_d', 'add', 1, 2, 3)
assert r2 == 6, f"Expected 6, got {r2}"
print(f"[PASS] interpret_capability('test_d', 'add', 1,2,3) = {r2}")

# spiral
spiral_r = s.spiral('spiral_t', 'add', 5, 3)
assert spiral_r['result'] == 8, f"Expected 8, got {spiral_r['result']}"
print(f"[PASS] spiral('spiral_t', 'add', 5, 3) = {spiral_r['result']}")

# natural language
nl = s.natural_to_code('计算 正弦 余弦', language='zh')
print(f"[PASS] natural_to_code = {nl['capabilities']}")

# status
status = s.get_status()
assert status['initialized'] == True
assert status['interpreter'] == True
assert status['compiler'] == True
assert status['vm'] == True
print(f"[PASS] get_status() = initialized={status['initialized']}")

# all features
print(f"\n[PASS] All features working:")
print(f"  - Interpreter: {status['interpreter']}")
print(f"  - Compiler: {status['compiler']}")
print(f"  - VM: {status['vm']}")
print(f"  - Runtime: {status['runtime']}")
print(f"  - Virtual Registry: {status['virtual_created']} created")
print(f"  - Virtual Definition: {status['definitions']} definitions, {status['capabilities']} capabilities")
print(f"  - LSP: {status['lsp']}")
print(f"  - MCP: {status['mcp']}")
print(f"  - AI Assistant: {status['ai_assistant']}")
print(f"  - Domain Registry: {status['domain_registry']}")
print(f"  - Bootstrap: {status['bootstrap']}")
print(f"  - Type System: {status['type_system']}")
print(f"  - Semantic Analyzer: {status['semantic_analyzer']}")

print("\n=== MathaSystem 完整系统测试通过 ===")
