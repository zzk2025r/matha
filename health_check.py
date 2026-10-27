from src.inner_loop import get_inner_loop
from src.growth_engine import create_growth_engine
from src.unified_growth import get_unified_growth
from src.plugins.ffi_sdk import get_engine

print('=== Subsystem Health Check ===')

# 1. Inner Loop
try:
    loop = get_inner_loop()
    print('InnerLoop: OK')
    result = loop.self_upgrade_check()
    print(f'  Version: {result["current_version"]}, Latest: {result["latest_version"]}')
except Exception as e:
    print(f'InnerLoop: ERROR - {e}')

# 2. Growth Engine
try:
    engine = create_growth_engine()
    report = engine.run_growth_cycle(max_iterations=1)
    stats = engine.get_growth_stats()
    print('GrowthEngine: OK')
    print(f'  Resources audited: {stats.get("resources_audited", 0)}')
    print(f'  Defects: {stats.get("engine_defects", {}).get("total", 0)}')
except Exception as e:
    print(f'GrowthEngine: ERROR - {e}')

# 3. Unified Growth
try:
    ug = get_unified_growth()
    result = ug.sandbox_run('#1: [2+2]')
    print(f'UnifiedGrowth Sandbox: {result}')
    result = ug.upgrade('#1: [x+1]')
    print(f'  Upgrade: {result}')
    result = ug.formula_grow('auto', max_combinations=2)
    print(f'  Formula grow: {result}')
except Exception as e:
    print(f'UnifiedGrowth: ERROR - {e}')

# 4. FFI SDK
try:
    eng = get_engine()
    eng.initialize()
    outputs = eng.execute('#1: [sin(3.14)]')
    print(f'FFI SDK: OK, sin(3.14)={outputs}')
except Exception as e:
    print(f'FFI SDK: ERROR - {e}')