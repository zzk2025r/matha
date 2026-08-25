# -*- coding: utf-8 -*-
"""验证 interp.py 中 8 个新注册条目的加载情况。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.interp import _build_domain_builtins

b = _build_domain_builtins()

modules_to_check = [
    ('src.domains.ai_data_science', '_register_ai_data_science'),
    ('src.domains.game_dev', '_register_game_dev'),
    ('src.domains.quantum_compute', '_register_quantum_compute'),
    ('src.domains.chaos_fractal', '_register_chaos_fractal'),
    ('src.domains.genetic_algo', '_register_genetic_algo'),
    ('src.domains.creative_coding', '_register_creative_coding'),
    ('src.domains.blockchain', '_register_blockchain'),
    ('src.domains.software_app', '_register_software_app'),
]

print('=== interp.py 8个新注册条目验证 ===')
all_ok = True
for mod_path, fn_name in modules_to_check:
    try:
        mod = __import__(mod_path, fromlist=[fn_name])
        fn = getattr(mod, fn_name)
        # 测试注册函数调用
        import inspect
        sig = inspect.signature(fn)
        print(f'  ✓ {fn_name}{sig}')
    except Exception as e:
        print(f'  ✗ {fn_name}: {e}')
        all_ok = False

print()
# 抽样验证新注册的键
samples = [
    ('sigmoid', 'ai_data_science'),
    ('relu', 'ai_data_science'),
    ('sprite_create', 'game_dev'),
    ('hadamard', 'quantum_compute'),
    ('Lorenz吸引子', 'chaos_fractal'),
    ('遗传算法进化', 'genetic_algo'),
    ('Perlin噪声2D', 'creative_coding'),
    ('创建区块', 'blockchain'),
    ('HTTP_GET', 'software_app'),
]
print('=== 新注册函数抽样 ===')
for key, domain in samples:
    if key in b:
        print(f'  ✓ "{key}" [{domain}]')
    else:
        print(f'  ✗ "{key}" [{domain}] 未找到')
        all_ok = False

custom_keys = [k for k in b.keys() if k not in ['与', '或', '非']]
print()
print(f'自定义函数总数: {len(custom_keys)}')
print(f'其中中文函数: {sum(1 for k in custom_keys if any(ord(c) > 127 for c in k))}')
print()
if all_ok:
    print('全部 8 个领域注册验证通过 ✓')
else:
    print('存在注册问题，请检查上述错误')
    sys.exit(1)
