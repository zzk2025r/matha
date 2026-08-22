# -*- coding: utf-8 -*-
"""v1.3.0 全模块健康检查"""
import urllib.request
import json

def fetch(url, method='GET', data=None):
    headers = {'Content-Type': 'application/json'} if data else {}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.loads(r.read().decode())
    except Exception as e:
        return None, str(e)

print('=' * 50)
print('  Matha v1.3.0 全模块健康检查报告')
print('=' * 50)

all_ok = True
checks = [
    ('健康检查', 'GET', 'http://127.0.0.1:8080/api/health', None),
    ('驱动列表', 'GET', 'http://127.0.0.1:8080/api/drivers/list', None),
    ('FFI 函数', 'GET', 'http://127.0.0.1:8080/api/ffi/list', None),
    ('内循环状态', 'GET', 'http://127.0.0.1:8080/api/inner_loop/status', None),
    ('成长统计', 'GET', 'http://127.0.0.1:8080/api/growth/stats', None),
]

for name, method, url, data in checks:
    code, body = fetch(url, method, data)
    ok = code == 200
    if not ok: all_ok = False
    print(f'\n[{"OK" if ok else "FAIL"}] {name} (HTTP {code})')
    print(json.dumps(body, ensure_ascii=False, indent=2))

# POST 测试
post_checks = [
    ('符号解析', 'POST', 'http://127.0.0.1:8080/api/symbolic/parse',
     {'expression': 'x^2 + 3*x - 5', 'params': {'x': 3}}),
    ('多范式计算', 'POST', 'http://127.0.0.1:8080/api/paradigm/compute',
     {'type': 'functional', 'expr': ['let', ['x', 5], ['let', ['y', 3], ['+', ['x'], ['*', ['y'], ['y']]]]]}),
    ('代码生成', 'POST', 'http://127.0.0.1:8080/api/codegen/python',
     {'expr': 'x^2 + 3*x - 5', 'func_name': 'compute'}),
    ('驱动执行', 'POST', 'http://127.0.0.1:8080/api/drivers/execute',
     {'driver': 'linear_algebra', 'op': 'mat_det', 'args': [[1, 2], [3, 4]]}),
]

for name, method, url, data in post_checks:
    code, body = fetch(url, method, data)
    ok = code == 200
    if not ok: all_ok = False
    print(f'\n[POST {"OK" if ok else "FAIL"}] {name} (HTTP {code})')
    print(json.dumps(body, ensure_ascii=False, indent=2))

print()
print('=' * 50)
print(f'  总体状态: {"ALL OK" if all_ok else "HAS FAILURES"}')
print('=' * 50)
