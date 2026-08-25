# -*- coding: utf-8 -*-
"""资源库测试：保护隔离 + 读取 + 自主成长扩展。

覆盖五个层次：
  1) Library 扫描与索引：list / has / read / disciplines
  2) 保护隔离：资源只读、is_protected
  3) 沙箱加载：load 单资源、load_discipline 分支加载
  4) 自主成长扩展：grow 生成新资源、入库、可调用
  5) Matha 侧内建：资源_列表 / 资源_读取 / 资源_加载 / 资源_成长

运行：python -m tests.test_library
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.parser import parse
from src.interp import Interpreter, interpret
from src.library import Library, get_library


def _interp_with(src: str = '') -> Interpreter:
    i = Interpreter()
    if src:
        i.run(parse(src))
    return i


# ============================================================
# 1) 扫描与索引
# ============================================================

def test_library_scan():
    """资源库扫描后有条目。"""
    print("\n--- 资源库: 扫描与索引 ---")
    lib = Library()
    lst = lib.list()
    assert len(lst) > 0, "资源库为空"
    paths = [e['路径'] for e in lst]
    assert 'core/arithmetic' in paths, paths
    assert 'mechanics/shaft' in paths, paths
    print(f"  ✓ 共 {len(lst)} 个资源")


def test_library_has_and_read():
    """has / read 查询资源。"""
    print("\n--- 资源库: has / read ---")
    lib = Library()
    assert lib.has('core/arithmetic') is True
    assert lib.has('nonexistent/path') is False
    content = lib.read('core/arithmetic')
    assert content is not None
    assert 'func 加' in content, content
    print(f"  ✓ core/arithmetic 含 func 加")


def test_library_disciplines():
    """disciplines 列出所有学科分支。"""
    print("\n--- 资源库: disciplines ---")
    lib = Library()
    discs = lib.disciplines()
    assert 'core' in discs
    assert 'mechanics' in discs
    assert 'structural' in discs
    assert 'physics' in discs
    print(f"  ✓ 学科分支: {discs}")


# ============================================================
# 2) 保护隔离
# ============================================================

def test_library_protected():
    """资源受保护（只读标记）。"""
    print("\n--- 资源库: 保护隔离 ---")
    lib = Library()
    assert lib.is_protected('core/arithmetic') is True
    assert lib.is_protected('mechanics/shaft') is True
    assert lib.is_protected('nonexistent') is False
    print(f"  ✓ core/arithmetic 受保护")


# ============================================================
# 3) 沙箱加载
# ============================================================

def test_library_load():
    """load 加载单个资源到解释器。"""
    print("\n--- 资源库: 沙箱加载 ---")
    i = _interp_with()
    lib = Library()
    r = lib.load('core/arithmetic', i)
    assert r['成功'] is True, r
    assert '加' in r['新函数'], r
    assert i.call('加', 3, 4) == 7
    assert i.call('平方', 5) == 25
    print(f"  ✓ 加(3,4)={i.call('加', 3, 4)}, 平方(5)={i.call('平方', 5)}")


def test_library_load_discipline():
    """load_discipline 加载整个学科分支。"""
    print("\n--- 资源库: 分支加载 ---")
    i = _interp_with()
    lib = Library()
    r = lib.load_discipline('mechanics', i)
    assert r['成功'] is True, r
    assert '转矩' in r['新函数'], r
    T = i.call('转矩', 5.0, 1440)
    assert T > 0
    print(f"  ✓ 转矩(5,1440)={T:.2f}")


def test_library_load_nonexistent():
    """加载不存在的资源返回失败。"""
    print("\n--- 资源库: 加载不存在 ---")
    i = _interp_with()
    lib = Library()
    r = lib.load('nonexistent/path', i)
    assert r['成功'] is False, r
    assert '不存在' in r['错误'], r
    print(f"  ✓ 正确报告不存在")


# ============================================================
# 4) 自主成长扩展
# ============================================================

def test_library_grow():
    """资源库自主成长：生成新资源。"""
    print("\n--- 资源库: 自主成长 ---")
    i = _interp_with()
    lib = Library()
    r = lib.grow(i, '计算球体积', 'core', '球体积')
    assert r.成功 is True, r
    assert r.新资源 == 'core/球体积', r
    # 验证可调用
    v = i.call('球体积', 2)
    assert v > 0, v
    print(f"  ✓ 生成 core/球体积, 球体积(2)={v:.4f}")


def test_library_grow_persists():
    """成长生成的资源持久化到资源库。"""
    print("\n--- 资源库: 成长持久化 ---")
    lib = Library()
    # 球体积可能由前一个测试生成
    if not lib.has('core/球体积'):
        i = _interp_with()
        lib.grow(i, '计算球体积', 'core', '球体积')
    # 重新扫描应能看到
    lib2 = Library()
    assert lib2.has('core/球体积'), "成长资源未持久化"
    print(f"  ✓ core/球体积 已持久化")


# ============================================================
# 5) Matha 侧内建
# ============================================================

def test_matha_library_list():
    """Matha 侧调用 资源_列表。"""
    print("\n--- Matha 侧: 资源_列表 ---")
    out, _ = interpret('#：{\n  lst = 资源_列表()\n  #：[lst]\n}')
    r = out[0]
    assert isinstance(r, list) and len(r) > 0
    print(f"  ✓ Matha 获取 {len(r)} 个资源")


def test_matha_library_load():
    """Matha 侧调用 资源_加载。"""
    print("\n--- Matha 侧: 资源_加载 ---")
    src = '''#：{
  资源_加载("core/arithmetic")(0)
  v = 加 10 20
  #：[v]
}'''
    out, _ = interpret(src)
    assert out[0] == 30, out
    print(f"  ✓ Matha 加载后 加(10,20)={out[0]}")


def test_matha_library_grow():
    """Matha 侧调用 资源_成长。"""
    print("\n--- Matha 侧: 资源_成长 ---")
    src = '''#：{
  报告 = 资源_成长("计算圆柱体积")("core")("圆柱体积")
  #：[报告]
}'''
    out, _ = interpret(src)
    r = out[0]
    assert r['成功'] is True, r
    assert r['新资源'] == 'core/圆柱体积', r
    print(f"  ✓ Matha 成长生成 {r['新资源']}")


# ============================================================
# 主入口
# ============================================================

def main():
    tests = [
        test_library_scan,
        test_library_has_and_read,
        test_library_disciplines,
        test_library_protected,
        test_library_load,
        test_library_load_discipline,
        test_library_load_nonexistent,
        test_library_grow,
        test_library_grow_persists,
        test_matha_library_list,
        test_matha_library_load,
        test_matha_library_grow,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as ex:
            failed += 1
            print(f"  ✗ {t.__name__}: {type(ex).__name__}: {ex}")
    print(f"\n{'='*40}")
    print(f"资源库测试: {passed}/{passed+failed} 通过")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
