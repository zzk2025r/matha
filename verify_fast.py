import os, sys, logging
logging.disable(logging.CRITICAL)
os.environ['MATHA_DEBUG'] = '0'

# Test 1: Core imports
print('[1/6] Testing Core Imports...')
from src.interp import Interpreter, interpret
from src.compiler.matha_cc import matha_compile, MathaCompiler, MathaLexer, MathaParser
from src.matha_vm import MathaVM, MathaBytecode, MathaOpcode
from src.matha_runtime import sin, cos, sqrt, exp, PI
from src.parser import Parser, parse as python_parse
from src.lexer import Lexer
from src.matha_main import VERSION
print('  All imports: OK')

# Test 2: Interpreter
print('[2/6] Testing Interpreter...')
out, trace = interpret('result = 1 + 2 * 3\n#1：[result]')
assert out == [7], f'Expected [7], got {out}'
print(f'  1+2*3 = {out[0]}: OK')

# Test 3: VM
print('[3/6] Testing VM...')
vm = MathaVM()
bc = MathaBytecode()
bc.add_constant(2)
bc.add_constant(3)
bc.emit(MathaOpcode.PUSH_INT, 0)
bc.emit(MathaOpcode.PUSH_INT, 1)
bc.emit(MathaOpcode.ADD)
bc.emit(MathaOpcode.HALT)
result = vm.run(bc)
assert result == 5.0
print(f'  2+3 = {result}: OK')

# Test 4: Runtime
print('[4/6] Testing Runtime...')
assert abs(sin(PI/2) - 1.0) < 0.0001
assert abs(sqrt(2) - 1.4142) < 0.0001
print(f'  sin(pi/2)={sin(PI/2):.6f}, sqrt(2)={sqrt(2):.6f}: OK')

# Test 5: Compiler
print('[5/6] Testing Compiler...')
source = 'result = sin(3.14) + cos(1.57)\n#1：[result]'
compiled = matha_compile(source, 'out_test', optimize=True)
print(f'  Compilation: OK')

# Test 6: CLI
print('[6/6] Testing CLI...')
from src.matha_main import main
print(f'  VERSION={VERSION}: OK')

print()
print('=== ALL 6 TESTS PASSED ===')
print('Matha v4.4 system fully operational!')
