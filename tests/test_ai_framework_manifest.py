# -*- coding: utf-8 -*-
"""ai_framework 接入 manifest 主链的防漂移锁（AI 补全计划阶段 2 第 1 项）。

背景：`src/ai_framework.py` 的数值腿已由 `test_ai_framework_numerics.py`（76 条）
背书，但其 `_register_ai_framework` 钩子历史上全是**平铺多参 lambda**——Matha
`f(a, b)` 在 VM 与 interp 两侧均编译为 `f(a)(b)`，平铺形态一进主链就崩；且旧钩子
注册的 `创建神经网络` 与 neural_network 领域插件重名（假插件曾坐实，阶段 1 已重写）。

本文件锁定四件事：

  1. **符号面四方一致**：钩子实注册 ↔ `_ai_framework_names()` ↔ registry 的
     AIFramework 模板 ↔ manifest 条目，任何一方漂移即红；
  2. **归属唯一**：`创建神经网络` 唯一归属 neural_network；ai_framework 的 14 枚
     符号各自唯一归属 ai_framework（不得再与任何插件重名）；
  3. **柯里化行为**：注册形态逐一手算/构造对拍（含「零参 f() 传常量 0」约定）；
  4. **主链端到端**：干净子进程经 exec_api 懒加载真算（auto 模式按需物化 +
     显式 `@：【加载领域】，AI框架` 别名加载），且物化 ai_framework 不带入任何
     src.domains.* 模块（域外插件的纯净性）。

sys.modules 相关断言一律起子进程，纪律见 test_plugin_contract.py 文档。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.ai_framework as ai  # noqa: E402
from src.plugin_api import get_resolver  # noqa: E402

MANIFEST = ROOT / "src" / "domains" / "manifest.json"


def _hook_table() -> dict:
    d: dict = {}
    ai._register_ai_framework(d)
    return d


def _manifest_entry() -> dict:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = [p for p in payload["plugins"] if p["name"] == "ai_framework"]
    assert len(entries) == 1, "manifest 里 ai_framework 条目缺失或重复"
    return entries[0]


# ============================================================
# 1. 符号面四方一致（钩子 ↔ names ↔ registry 模板 ↔ manifest）
# ============================================================

def test_hook_matches_names_list():
    d = _hook_table()
    assert sorted(d) == sorted(ai._ai_framework_names())
    assert len(d) == 14
    assert "创建神经网络" not in d, "创建神经网络 必须让位给 neural_network 插件"


def test_registry_template_matches_hook():
    from src.domains.registry import DomainRegistry

    tpl = DomainRegistry._DOMAIN_TEMPLATES["AIFramework"]
    assert tpl["module"] == "src.ai_framework"
    assert sorted(tpl["functions"]) == sorted(_hook_table()), \
        "registry 模板与钩子实注册漂移（改钩子必须同步模板并重生成 manifest）"


def test_manifest_entry_matches_hook():
    p = _manifest_entry()
    assert p["module"] == "src.ai_framework"
    assert p["registers"] == ["_register_ai_framework"]
    assert p["symbols"] == sorted(_hook_table()), \
        "manifest 与钩子漂移：请运行 python scripts/gen_domain_manifest.py"
    assert p["declared_symbols"] == []
    assert p["legacy"] is False
    assert p["category"] == "ai"
    assert p["display_name"] == "AI框架"
    assert "AI框架" in p["aliases"]


def test_generator_includes_ai_framework_as_extra_module():
    from scripts.gen_domain_manifest import EXTRA_PLUGIN_MODULES

    assert "src.ai_framework" in EXTRA_PLUGIN_MODULES


# ============================================================
# 2. 归属唯一（只读清单，不触发物化）
# ============================================================

def test_neural_network_symbol_owned_only_by_neural_network_plugin():
    assert get_resolver().owners_of("创建神经网络") == ["neural_network"]


def test_ai_framework_symbols_have_unique_ownership():
    r = get_resolver()
    for sym in _hook_table():
        assert r.owners_of(sym) == ["ai_framework"], f"{sym} 归属漂移"


# ============================================================
# 3. 柯里化注册形态的行为对拍
# ============================================================

def test_curried_matmul_hand_computed():
    d = _hook_table()
    got = d["矩阵乘法"]([[1, 2], [3, 4]])([[5, 6], [7, 8]])
    assert got == [[19, 22], [43, 50]]


def test_curried_linear_layer():
    layer = _hook_table()["创建线性层"](2)(3)
    assert isinstance(layer, ai.Linear)
    assert layer.in_features == 2 and layer.out_features == 3
    assert layer.weight.shape == (2, 3)


def test_zero_arg_creators_accept_dummy_zero():
    # Matha 零参调用 f() 编译为「压常量 0 再 CALL 1」，创建器必须吃哑参
    d = _hook_table()
    assert isinstance(d["创建ReLU"](0), ai.ReLU)
    assert isinstance(d["创建Sigmoid"](0), ai.Sigmoid)
    assert isinstance(d["创建Tanh"](0), ai.Tanh)
    assert isinstance(d["创建自动微分"](0), ai.AutoDiff)


def test_single_arg_creators():
    d = _hook_table()
    t = d["创建张量"]([2, 3])
    assert t.shape == (2, 3) and t.data == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    m = d["创建模型"]("net")
    assert isinstance(m, ai.Sequential) and m.name == "net"
    assert d["创建Softmax"](-1).dim == -1
    assert d["创建Dropout"](0.25).p == 0.25
    assert d["创建BatchNorm"](4).num_features == 4


def test_curried_optimizers_and_trainer():
    d = _hook_table()
    w = ai.Tensor(data=[1.0], shape=(1,), requires_grad=True)
    adam = d["创建Adam"]([w])(0.05)
    assert isinstance(adam, ai.Adam) and adam.lr == 0.05
    sgd = d["创建SGD"]([w])(0.1)
    assert isinstance(sgd, ai.SGD) and sgd.lr == 0.1
    model = ai.Sequential("net")
    trainer = d["创建训练器"](model)(7)
    assert isinstance(trainer, ai.Trainer)
    assert trainer.model is model and trainer.epochs == 7


# ============================================================
# 4. 主链端到端（干净子进程，exec_api 懒加载真算）
# ============================================================

_E2E_AUTO_SNIPPET = """
import json, sys
sys.path.insert(0, %r)
from src.kernel import exec_api
from src.plugin_api import get_resolver
src = '''a = 矩阵乘法([[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]])
#1：[a]
'''
out = exec_api.run(src)
assert out == [[[19.0, 22.0], [43.0, 50.0]]], out
r = get_resolver()
assert "ai_framework" in r.loaded(), sorted(r.loaded())
leaked = sorted(m for m in sys.modules if m.startswith("src.domains."))
assert leaked == [], leaked
assert "src.ai_framework" in sys.modules
print(json.dumps({"out": out}))
""" % str(ROOT)


def test_e2e_auto_mode_lazy_loads_ai_framework_and_computes():
    proc = subprocess.run([sys.executable, "-c", _E2E_AUTO_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["out"] == [[[19.0, 22.0], [43.0, 50.0]]]


_E2E_ALIAS_SNIPPET = """
import json, sys
sys.path.insert(0, %r)
from src.kernel import exec_api
from src.plugin_api import get_resolver
src = '''@：【加载领域】，AI框架
layer = 创建线性层(2, 3)
act = 创建Sigmoid()
#1：[矩阵乘法([[1.0, 2.0], [3.0, 4.0]], [[5.0, 6.0], [7.0, 8.0]])]
'''
out = exec_api.run(src)
assert out == [[[19.0, 22.0], [43.0, 50.0]]], out
assert "ai_framework" in get_resolver().loaded()
print(json.dumps({"out": out}))
""" % str(ROOT)


def test_e2e_explicit_alias_load_with_curried_and_zero_arg_calls():
    proc = subprocess.run([sys.executable, "-c", _E2E_ALIAS_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["out"] == [[[19.0, 22.0], [43.0, 50.0]]]