from src.bootstrap import MathaBootstrap
from src.matha_bootstrap import interpret
from src import get_engine, MathaEngine

# Test MathaBootstrap
bs = MathaBootstrap()
print('MathaBootstrap OK')

# Test interpret
out, trace = interpret('result = 1 + 2 * 3\n#1：[result]')
print(f'Interpret result: {out}')

# Test engine
engine = get_engine()
result = engine.eval('sin(3.14159) + cos(1.57)')
print(f'Engine eval: {result}')

# Test interop status
status = engine.get_interop_status()
print(f'Interop: interp={status["interpreter"]}, compiler={status["compiler"]}, vm={status["vm"]}')
print('All tests passed!')
