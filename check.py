p = r'D:\trae\src\parser.py'
s = open(p, encoding='utf-8').read()
if '[x*x for' in s:
    pass
# simpler approach - just note we need proper fix; for now skip listcomp full support, document as remaining
print('ok')
