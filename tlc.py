import sys
sys.path.insert(0, r'D:\trae')
from src.parser import parse
try:
    r = parse('输出([x*x for x in [1,2,3]])')
    print(r)
except Exception as e:
    print(e)
