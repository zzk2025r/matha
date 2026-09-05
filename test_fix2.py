import sys
sys.path.insert(0, r'd:\trae')
from src.parser import parse

# Test: Simple list with tuples
source = '''
module Test {
  func 真值表_与() -> List =
    [(真, 真, 真), (真, 假, 假)]
}
'''
program = parse(source)
print('Parse OK')
