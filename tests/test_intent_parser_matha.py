# -*- coding: utf-8 -*-
"""intent_parser 改产 Matha 代码的行为锁（AI 补全计划阶段 2 第 2 项）。

历史缺陷：CodeGenerator 只有 Python 通道，且算术恒 `nums[0] + nums[1]`、
数学函数恒 `math.sqrt`——与用户说的运算无关；REPL nl 模式拿这段 Python
进 Matha 主链执行，必碎或假对。本轮新增 `generate_matha`：映射只落内核
builtin（src/kernel/math_builtin.py）与纯算术，歧义/不支持一律空代码 +
errors 如实下沉；两个 REPL 的 nl 通道改传 target_lang="matha" 并经
exec_api 执行（repl_v23 不再走 legacy 诊断解释器）。

本文件锁定：
  1. 代码生成逐句对拍（含 `#1：[result]` 输出指令——exec_api 只收集输出）；
  2. 生成代码经主链 exec_api 真算的数值锁；
  3. 拒绝矩阵（多运算歧义/范围语义/无映射函数/整数约束/不支持类型）；
  4. python 旧轨（main.py / parser_pool 的 exec 通道）形态不被本轮改动；
  5. 两个 REPL 的 nl 模式端到端（干净子进程）：真算 + 诚实降级可见。

口径遵 docs/KNOWN_ISSUES.md §7c：自然语言→答案的输出正确性仅就本文件
列举的受限句式背书，不背书开放域理解。
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.intent_parser import IntentParser, IntentType  # noqa: E402
from src.kernel import exec_api  # noqa: E402


def _parse(text: str):
    return IntentParser().parse(text, target_lang="matha")


# ============================================================
# 1. 代码生成逐句对拍
# ============================================================

@pytest.mark.parametrize("text,code", [
    ("计算 3 加 5", "result = 3 + 5\n#1：[result]"),
    ("计算 10 减去 4", "result = 10 - 4\n#1：[result]"),
    ("计算 6 乘以 7", "result = 6 * 7\n#1：[result]"),
    ("计算 7 除以 2", "result = 7 / 2\n#1：[result]"),
    ("计算 2.5 加 4", "result = 2.5 + 4\n#1：[result]"),
    ("计算 -3 加 5", "result = -3 + 5\n#1：[result]"),
    ("计算 1 加 2 加 3", "result = 1 + 2 + 3\n#1：[result]"),
    ("计算 2 的 3 次方", "result = 2 ** 3\n#1：[result]"),
    ("计算 5 的平方", "result = 5 ** 2\n#1：[result]"),
    ("求 9 的平方根", "result = sqrt(9)\n#1：[result]"),
    ("求和 1 2 3", "result = sum([1, 2, 3])\n#1：[result]"),
    ("求平均 2 4 6", "result = 平均值([2, 4, 6])\n#1：[result]"),
    ("最大 3 7 5", "result = max([3, 7, 5])\n#1：[result]"),
    ("最低 3 7 5", "result = min([3, 7, 5])\n#1：[result]"),
    ("计算 0.5 的正弦", "result = sin(0.5)\n#1：[result]"),
    ("求 5 的阶乘", "result = 阶乘(5)\n#1：[result]"),
    ("求 12 和 18 的 gcd", "result = 最大公约数(12, 18)\n#1：[result]"),
    ("求 12 和 18 的 lcm", "result = 最小公倍数(12, 18)\n#1：[result]"),
    ("判断 7 是否素数", "result = 素数判定(7)\n#1：[result]"),
])
def test_generated_matha_code_is_exact(text, code):
    intent = _parse(text)
    assert intent.target_lang == "matha"
    assert intent.suggested_code == code
    assert intent.errors == []


# ============================================================
# 2. 主链真算数值锁（exec_api：lexer → parser → mbc.compiler → vm）
# ============================================================

@pytest.mark.parametrize("text,expected", [
    ("计算 3 加 5", [8]),
    ("计算 7 除以 2", [3.5]),
    ("计算 2 的 3 次方", [8]),
    ("计算 5 的平方", [25]),
    ("求 9 的平方根", [3.0]),
    ("计算 1 加 2 加 3", [6]),
    ("求和 1 2 3", [6]),
    ("求平均 2 4 6", [4.0]),
    ("最大 3 7 5", [7]),
    ("最小 3 7 5", [3]),
    ("求 5 的阶乘", [120]),
    ("求 12 和 18 的 gcd", [6]),
    ("求 12 和 18 的 lcm", [36]),
    ("判断 7 是否素数", [True]),
    ("判断 8 是否素数", [False]),
    ("计算 -16 的绝对值", [16]),
    ("计算 3.7 的取整", [3]),
    ("计算 3.7 的舍入", [4]),
    ("计算 1 的对数", [0.0]),
    ("计算 0 的指数", [1.0]),
    ("计算 -3 加 5", [2]),
])
def test_generated_code_executes_on_mainline(text, expected):
    intent = _parse(text)
    assert intent.suggested_code, f"应生成代码：{intent.errors}"
    assert exec_api.run(intent.suggested_code) == expected


def test_trig_value_matches_math():
    intent = _parse("计算 0.5 的正弦")
    out = exec_api.run(intent.suggested_code)
    assert out[0] == pytest.approx(math.sin(0.5), abs=1e-12)


# ============================================================
# 3. 拒绝矩阵：空代码 + 原因下沉，绝不产占位代码
# ============================================================

@pytest.mark.parametrize("text,reason", [
    ("计算 3 加 5 乘 2", "含多种运算"),
    ("计算 3 5", "未识别到具体运算"),
    ("求 1 到 100 的总和", "范围语义"),
    ("反转字符串 abc", "意图类型 STRING_OP"),
    ("求斐波那契 10", "暂无内核 builtin 映射"),
    ("计算 5.5 的阶乘", "只接受整数参数"),
    ("计算正弦和余弦 30", "含多个函数"),
    ("计算正弦", "需要恰好 1 个数字"),
    ("最大和最小 3 5", "无法确定唯一比较方向"),
    ("计算 2 3 4 的幂", "幂运算需要恰好两个数字"),
    ("计算 3 和 5 的平方", "平方需要恰好一个数字"),
])
def test_ambiguous_or_unsupported_is_honestly_rejected(text, reason):
    intent = _parse(text)
    assert intent.suggested_code == ""
    assert any(reason in str(e) for e in intent.errors), intent.errors


def test_unknown_intent_stays_empty_without_code():
    intent = _parse("你好世界")
    assert intent.intent_type == IntentType.UNKNOWN
    assert intent.suggested_code == ""


def test_explain_surfaces_rejection_reason():
    parser = IntentParser()
    intent = parser.parse("计算 3 加 5 乘 2", target_lang="matha")
    report = parser.explain(intent)
    assert "代码生成拒绝" in report and "含多种运算" in report


def test_dui_shu_does_not_match_dui_shu_zu():
    # 「对数组求阶乘」不得把「对数」当成 log（分类器同款边界）
    intent = _parse("对数组求阶乘")
    assert intent.suggested_code == ""
    assert not any("log" in str(e) for e in intent.errors)


# ============================================================
# 4. python 旧轨不被本轮改动（main.py / parser_pool 的 exec 通道）
# ============================================================

def test_default_target_lang_stays_python():
    intent = IntentParser().parse("计算 3 加 5")
    assert intent.target_lang == "python"
    assert intent.suggested_code.startswith("result =")


def test_python_track_execute_intent_still_works():
    from src.enhanced_intent import execute_intent

    result = execute_intent("计算 3 加 5")
    assert result.is_ok()
    assert result.unwrap() == 8.0


def test_enhanced_parser_matha_target_and_exec_guard():
    from src.enhanced_intent import EnhancedIntentParser

    parser = EnhancedIntentParser()
    result = parser.parse("计算 3 加 5", target_lang="matha")
    assert result.is_ok()
    intent = result.unwrap()
    assert intent.suggested_code == "result = 3 + 5\n#1：[result]"
    # execute_and_verify 是 python 旧轨的 exec 通道：matha 目标必须显式拒绝
    exec_result = parser.execute_and_verify(intent)
    assert exec_result.is_err()
    assert "仅支持 python 目标" in exec_result.err().message


# ============================================================
# 5. 两个 REPL 的 nl 模式端到端（干净子进程）
# ============================================================

_REPL_SNIPPET = """
import contextlib, io, json, sys
sys.path.insert(0, %r)
from src.repl import MathaREPL as R1
from src.repl_v23 import MathaREPL as R2
report = {}
for name, cls in (("repl", R1), ("repl_v23", R2)):
    r = cls()
    r.state.mode = "nl"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r._process_natural_language("计算 3 加 5")
    ok_out = buf.getvalue()
    success_after_ok = r.state.success_count
    errors_after_ok = r.state.error_count
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        r._process_natural_language("计算 3 加 5 乘 2")
    report[name] = {
        "result_line": any("结果" in l and "8" in l for l in ok_out.splitlines()),
        "success": success_after_ok,
        "errors": errors_after_ok,
        "reject_visible": "代码生成拒绝" in buf2.getvalue(),
        "success_after_reject": r.state.success_count,
    }
print(json.dumps(report))
""" % str(ROOT)


def test_both_repls_nl_mode_end_to_end():
    proc = subprocess.run([sys.executable, "-c", _REPL_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    report = json.loads(proc.stdout.strip().splitlines()[-1])
    for name, payload in report.items():
        assert payload["result_line"], f"{name} 未打印真算结果：{payload}"
        assert payload["success"] == 1 and payload["errors"] == 0, payload
        assert payload["reject_visible"], f"{name} 拒绝原因未下沉到界面"
        assert payload["success_after_reject"] == 1, f"{name} 把拒绝记成了成功"