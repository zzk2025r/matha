import sys
sys.path.insert(0, r'D:\trae')
from src.parser import Parser
p = Parser('[x*x for x in [1,2,3]]')
# manually trace
p._expect.__name__
# see
try:
    r = p._parse_list_literal()
    print(type(r))
except Exception as e:
    print(e)
