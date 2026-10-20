import sys
sys.path.insert(0, r'D:\trae')
from src.mbc.vm import run_source
try:
    run_source('输出(错误("boom"))')
except RuntimeError as e:
    print('R')
