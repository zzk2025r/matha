# -*- coding: utf-8 -*-
"""阶段 7 锁：verify_password 恒真假验证清除 + symbolic.simplify 崩溃根治。

背景（阶段 6 登记、探针坐实）：① security_enhanced.verify_password 恒真
（len(hashed)>0，错误密码也通过），且 hash_password 随机盐不嵌入输出——
真验证必须改哈希格式；② symbolic.simplify 数字折叠与 _is_zero 对 parse
产出的裸数节点取 .value（simplify(parse('1+2')) AttributeError）。
本轮：hash_password 改 hex(salt)$hex(dk) 嵌入盐，verify_password 重算
PBKDF2 + hmac.compare_digest（格式非法一律 False 不裸抛，口径同
src/auth/password.py 既有真实现）；simplify/_is_zero 经 _number_value
兼容裸数与 Symbol 值节点。

本文件锁：
  1. 手算对拍：哈希摘要与独立 hashlib.pbkdf2_hmac 重算逐值一致；
     simplify 折叠/消零手算值；
  2. 闭环：hash→verify 正确密码通过（跨实例）、错误密码/篡改拒绝；
     内建 哈希密码 注册接线产出可验证哈希；matha_system 门面闭环；
  3. 显式拒绝：非法格式矩阵一律 False 不裸抛；simplify 非 '+' 透传
     不过度简化。
安全纪律：本文件仅使用假密钥（test-key / fake-key-abc）。
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.security_enhanced import (  # noqa: E402
    MathaSecurity, _register_security_enhanced,
)
from src.symbolic import (  # noqa: E402
    Expression, MathaSymbolic, Symbol, SymbolType,
)


# ============================================================
# 1. verify_password：手算对拍 + 闭环 + 显式拒绝
# ============================================================

class TestVerifyPassword:

    def test_hash_digest_matches_independent_pbkdf2(self):
        h = MathaSecurity().hash_password("fake-key-abc")
        salt, dk = h.split("$")
        expected = hashlib.pbkdf2_hmac(
            "sha256", b"fake-key-abc", salt.encode(), 100000).hex()
        assert dk == expected

    def test_hash_format_lock(self):
        h = MathaSecurity().hash_password("fake-key-abc")
        assert re.fullmatch(r"[0-9a-f]{32}\$[0-9a-f]{64}", h)

    def test_correct_password_verifies(self):
        sec = MathaSecurity()
        h = sec.hash_password("fake-key-abc")
        assert sec.verify_password("fake-key-abc", h) is True

    def test_wrong_password_rejected(self):
        sec = MathaSecurity()
        h = sec.hash_password("fake-key-abc")
        assert sec.verify_password("wrong-key", h) is False

    def test_empty_password_roundtrip(self):
        sec = MathaSecurity()
        h = sec.hash_password("")
        assert sec.verify_password("", h) is True
        assert sec.verify_password("x", h) is False

    def test_cross_instance_verify(self):
        h = MathaSecurity().hash_password("test-key")
        assert MathaSecurity().verify_password("test-key", h) is True

    def test_salted_hashes_both_verify(self):
        sec = MathaSecurity()
        h1 = sec.hash_password("fake-key-abc")
        h2 = sec.hash_password("fake-key-abc")
        assert h1 != h2
        assert sec.verify_password("fake-key-abc", h1) is True
        assert sec.verify_password("fake-key-abc", h2) is True

    def test_tampered_digest_rejected(self):
        sec = MathaSecurity()
        h = sec.hash_password("fake-key-abc")
        salt, dk = h.split("$")
        flipped = ("0" if dk[-1] != "0" else "1")
        assert sec.verify_password(
            "fake-key-abc", f"{salt}${dk[:-1]}{flipped}") is False

    def test_tampered_salt_rejected(self):
        sec = MathaSecurity()
        h = sec.hash_password("fake-key-abc")
        salt, dk = h.split("$")
        flipped = ("0" if salt[0] != "0" else "1")
        assert sec.verify_password(
            "fake-key-abc", f"{flipped}{salt[1:]}${dk}") is False

    @pytest.mark.parametrize("malformed", [
        "", "deadbeef", "$", "a$b",
        "0" * 31 + "$" + "0" * 64,      # 盐长度不足
        "0" * 32 + "$" + "0" * 63,      # 摘要长度不足
        "g" * 32 + "$" + "0" * 64,      # 盐非 hex
        "0" * 32 + "$" + "g" * 64,      # 摘要非 hex
        "0" * 32 + "$" + "0" * 64 + "$x",  # 多段
    ])
    def test_malformed_hash_rejected_without_crash(self, malformed):
        assert MathaSecurity().verify_password(
            "fake-key-abc", malformed) is False

    def test_builtin_registration_produces_verifiable_hash(self):
        builtins = {}
        _register_security_enhanced(builtins)
        h = builtins["哈希密码"]("fake-key-abc")
        assert MathaSecurity().verify_password("fake-key-abc", h) is True
        assert MathaSecurity().verify_password("wrong-key", h) is False

    def test_matha_system_facade_closed_loop(self):
        from src.matha_system import MathaSystem
        s = MathaSystem.__new__(MathaSystem)
        s.debug = False
        s._init_domains()
        h = s.hash_password("test-key")
        assert MathaSecurity().verify_password("test-key", h) is True
        assert MathaSecurity().verify_password("wrong-key", h) is False


# ============================================================
# 2. simplify：崩溃回归 + 手算对拍 + 不过度简化
# ============================================================

class TestSimplifyCrashFix:

    def test_fold_numbers_hand_value(self):
        ms = MathaSymbolic()
        r = ms.simplify(ms.parse("1+2"))
        assert r.operator == "number"
        assert r.operands == [3.0]

    def test_fold_nested_hand_value(self):
        ms = MathaSymbolic()
        r = ms.simplify(ms.parse("1+2+3"))
        assert r.operator == "number"
        assert r.operands == [6.0]

    def test_zero_plus_x_hand(self):
        ms = MathaSymbolic()
        r = ms.simplify(ms.parse("0+x"))
        assert r.operator == "symbol"
        assert r.operands[0].name == "x"

    def test_x_plus_zero_hand(self):
        ms = MathaSymbolic()
        r = ms.simplify(ms.parse("x+0"))
        assert r.operator == "symbol"
        assert r.operands[0].name == "x"

    def test_symbol_sum_not_over_simplified(self):
        ms = MathaSymbolic()
        r = ms.simplify(ms.parse("x+y"))
        assert r.operator == "+"
        assert r.operands[0].operands[0].name == "x"
        assert r.operands[1].operands[0].name == "y"

    def test_non_plus_passthrough(self):
        ms = MathaSymbolic()
        r = ms.simplify(ms.parse("x^2"))
        assert r.operator == "**"

    def test_symbol_valued_number_nodes_compat(self):
        ms = MathaSymbolic()
        five = Expression(operator="number", operands=[
            Symbol("c", SymbolType.CONSTANT, 5)])
        two = Expression(operator="number", operands=[2.0])
        r = ms.simplify(Expression(operator="+", operands=[five, two]))
        assert r.operator == "number"
        assert r.operands == [7.0]

    def test_symbol_valued_zero_node_compat(self):
        ms = MathaSymbolic()
        zero = Expression(operator="number", operands=[
            Symbol("z", SymbolType.CONSTANT, 0)])
        r = ms.simplify(Expression(operator="+",
                                   operands=[zero, ms.parse("x")]))
        assert r.operator == "symbol"
        assert r.operands[0].name == "x"

    def test_simplify_idempotent_reentry(self):
        ms = MathaSymbolic()
        once = ms.simplify(ms.parse("1+2"))
        twice = ms.simplify(once)
        assert twice.operator == "number"
        assert twice.operands == [3.0]