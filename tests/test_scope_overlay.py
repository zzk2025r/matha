# -*- coding: utf-8 -*-
"""叠加式作用域 ``Scope``（src/interp_engine.py）的语义与缓存失效测试。

``Scope`` 用「本地写层 + 只读父链」替代整表拷贝：

- 读取：本地层 → 父链回溯；
- 写入：只落本地层（退帧即丢弃）；
- 解析缓存：命中父链结果后缓存（含负缓存），避免深递归时 O(n²) 回溯。

本文件锁定缓存失效的正确性：任何层的内容变化（写入 / 删除 / 新增 / 改值）
都不能让其它层读到**过期值**，尤其要覆盖「负缓存被后续定义打破」的场景。

运行：python -m tests.test_scope_overlay
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interp_engine import Scope, VersionedDict


# ============================================================
# 基本语义：写入隔离 / 读取沿父链
# ============================================================

def test_local_write_does_not_leak_to_parent():
    parent = Scope(parent={"a": 1})
    child = Scope(parent=parent)
    child["a"] = 99
    assert child["a"] == 99
    assert parent["a"] == 1


def test_read_walks_parent_chain():
    root = Scope(parent={"x": 1})
    mid = Scope(parent=root)
    leaf = Scope(parent=mid)
    assert leaf["x"] == 1
    mid["x"] = 2
    assert leaf["x"] == 2


def test_missing_key_raises():
    scope = Scope(parent={})
    assert "nope" not in scope
    assert scope.get("nope") is None
    assert scope.get("nope", 7) == 7
    try:
        scope["nope"]
    except KeyError:
        pass
    else:
        raise AssertionError("缺失键应抛 KeyError")


# ============================================================
# 缓存失效：祖先层变化必须对后代层可见
# ============================================================

def test_parent_delete_invalidates_child_cache():
    parent = Scope(parent={"g": 1})
    child = Scope(parent=parent)
    assert child["g"] == 1          # 预热缓存
    del parent["g"]
    assert "g" not in child          # 子层不得返回陈旧值


def test_parent_update_visible_in_child():
    parent = Scope(parent={"v": 1})
    child = Scope(parent=parent)
    assert child["v"] == 1
    parent["v"] = 2
    assert child["v"] == 2


def test_ancestor_new_binding_breaks_negative_cache():
    parent = Scope(parent={})
    child = Scope(parent=parent)
    assert "w" not in child          # 负缓存预热
    parent["w"] = 42
    assert child["w"] == 42


def test_grandparent_change_visible_in_leaf():
    root = Scope(parent={"d": 1})
    mid = Scope(parent=root)
    leaf = Scope(parent=mid)
    assert leaf["d"] == 1
    root["d"] = 7
    assert leaf["d"] == 7


def test_versioned_root_change_visible_at_depth():
    root = VersionedDict({"q": 1})
    s1 = Scope(parent=root)
    s2 = Scope(parent=s1)
    s3 = Scope(parent=s2)
    assert s3["q"] == 1
    root["q"] = 5
    assert s3["q"] == 5
    assert "zz" not in s3
    root["zz"] = 9
    assert s3["zz"] == 9


# ============================================================
# 变更方法与缓存的一致性
# ============================================================

def test_pop_invalidates_cache():
    scope = Scope(parent={"h": 5})
    assert scope["h"] == 5
    assert scope.pop("h") == 5
    assert "h" not in scope


def test_pop_from_parent_scope_invalidates_descendant_cache():
    parent = Scope(parent={"h": 5})
    child = Scope(parent=parent)
    assert child["h"] == 5
    assert child.pop("h") == 5
    assert "h" not in child
    assert "h" not in parent


def test_setdefault_and_update_consistent_with_cache():
    scope = Scope(parent={"a": 1})
    assert scope["a"] == 1
    scope.setdefault("b", 2)
    assert scope["b"] == 2
    scope.update({"a": 10})
    assert scope["a"] == 10
    scope.update(c=3)
    assert scope["c"] == 3


def test_delitem_local_does_not_touch_parent_value():
    parent = Scope(parent={"a": 1})
    child = Scope(parent=parent)
    child["a"] = 2
    del child["a"]
    assert child["a"] == 1          # 回落到父层值
    assert parent["a"] == 1


# ============================================================
# dict-like 接口：合并父链
# ============================================================

def test_items_keys_values_merge_parent_chain():
    parent = Scope(parent={"a": 1, "b": 2})
    child = Scope(parent=parent, local={"b": 20, "c": 3})
    assert dict(child.items()) == {"a": 1, "b": 20, "c": 3}
    assert sorted(child.keys()) == ["a", "b", "c"]
    assert sorted(child.values()) == [1, 3, 20]
    assert sorted(child) == ["a", "b", "c"]
    assert len(child) == 3


# ============================================================
# 端到端：Matha 程序在两种引擎模式下结果一致
# ============================================================

def test_matha_scope_semantics_parity():
    """函数体内的赋值只落本地层（叠加语义）——两种引擎模式结果一致。"""
    from src import features
    from src.parser import parse
    from src.interp import Interpreter

    src = (
        "var g = 1\n"
        "func bump() -> Int = () =>\n"
        "  g = g + 1\n"
        "  g\n"
        "输出(bump())\n"
        "输出(bump())\n"
        "输出(g)\n"
    )

    def _run(engine_on):
        features.set_feature("STACK_ENGINE", bool(engine_on))
        try:
            return Interpreter().run(parse(src))[0]
        finally:
            features.clear_feature()

    classic = _run(False)
    engine = _run(True)
    assert classic == engine, (classic, engine)
    # 函数内的写入不泄漏到全局：g 仍为 1
    assert classic[-1] == 1, classic


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✓ {name}")
    print("✓ Scope 叠加语义与缓存失效验证通过")
