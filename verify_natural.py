# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\trae")
from src.virtual_code import VirtualCodeEngine

e = VirtualCodeEngine(debug=False)
nl = e.natural_to_code('计算 正弦 余弦', language='zh')
print("capabilities:", nl['capabilities'])
print("code_name:", nl['code_name'])
print("spiral_complete:", nl['spiral_complete'])
print("language:", nl['language'])
print("natural_text:", nl['natural_text'])

# Verify each capability
for cap in nl['capabilities']:
    print(f"  Capability: '{cap}' (type: {type(cap).__name__})")
