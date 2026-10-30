"""sys_env 编译期折叠 + 恒定条件剪枝验证（P4 预备资产，不进门禁）。

`_SYSENV_FOLD` 在模块导入时读取，故每个断言都在**带环境的子进程**里跑，
避免进程内状态污染，也顺带证明折叠值真的来自操作系统环境而非脚本自说自话。

判据：
  A 折叠正确性 —— sys_env("K","d") 在 K 未设时取 d、已设时取值；字节码里无 CALL
  B 用户形态   —— if sys_env("MATHA_FAST_B09","0") == "1" { 快 } else { 原 }
                  剪枝后只保留选中分支，且无 JZ/CALL 残留
  C 编译期闸门 —— 非字面量键在编译期报错（不退化成运行期未定义变量）
  D 休眠等价   —— 开关关闭时 sys_env 走历史「未定义变量」路径，且既有语料字节码不变
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = r"D:\trae"


def child(src: str, probe: str) -> dict:
    code = (
        "import json, sys\n"
        "sys.path.insert(0, r'D:\\trae')\n"
        "from src.mbc import opcodes as OP\n"
        "from src.mbc.compiler import compile_source, _SYSENV_FOLD\n"
        "from src.mbc import run_source\n"
        f"SRC = {src!r}\n"
        "try:\n"
        "    mod = compile_source(SRC)\n"
        "except Exception as e:\n"
        "    print(json.dumps({'fold': _SYSENV_FOLD, 'compile_error': f'{type(e).__name__}: {e}'}))\n"
        "    raise SystemExit(0)\n"
        "codes = {'main': [list(i) for i in mod.main_code]}\n"
        "for n, f in mod.functions.items():\n"
        "    codes[n] = [list(i) for i in f.code]\n"
        "flat = [i for v in codes.values() for i in v]\n"
        "argcs = [i[1] for i in flat if len(i) >= 2 and i[0] == OP.CALL]\n"
        "# LOAD_GLOBAL 第二项是常量池下标，故按常量池判定 sys_env 是否仍被引用\n"
        "has_sysenv_global = 'sys_env' in list(mod.constants)\n"
        "n_jz = sum(1 for i in flat if i[0] == OP.JZ)\n"
        "try:\n"
        "    outs = [str(o) for o in run_source(SRC)]\n"
        "except Exception as e:\n"
        "    outs = [f'RUN_ERROR {type(e).__name__}: {e}']\n"
        "print(json.dumps({'fold': _SYSENV_FOLD, 'outputs': outs, 'call_argcs': argcs,\n"
        "                  'has_sysenv_global': has_sysenv_global, 'n_jz': n_jz}))\n"
    )
    env = dict(os.environ)
    env.pop("MATHA_SYSENV_FOLD", None)
    if probe.get("fold"):
        env["MATHA_SYSENV_FOLD"] = "1"
    for k, v in probe.get("envs", {}).items():
        env[k] = v
    p = subprocess.run([sys.executable, "-u", "-c", code], capture_output=True,
                       text=True, cwd=ROOT, env=env, timeout=180)
    line = [ln for ln in p.stdout.splitlines() if ln.startswith("{")]
    if not line:
        raise AssertionError(f"子进程无 JSON 输出：\n{p.stdout}\n{p.stderr}")
    return json.loads(line[-1])


GATE_SRC = (
    "n = 0\n"
    "if sys_env(\"MATHA_FAST_B09\", \"0\") == \"1\" {\n"
    "  n = 99\n"
    "} else {\n"
    "  n = 1\n"
    "}\n"
    "输出(n)\n"
)
FOLD_SRC = "输出(sys_env(\"MATHA_SYSENV_PROBE\", \"dflt\"))\n"
VARKEY_SRC = "k = \"MATHA_SYSENV_PROBE\"\n输出(sys_env(k, \"dflt\"))\n"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


# —— A 折叠正确性 ——
r = child(FOLD_SRC, {"fold": True, "envs": {}})
check("A1 缺省取 default", r.get("outputs") == ["dflt"] and not r.get("has_sysenv_global")
      and r.get("call_argcs") == [1], json.dumps(r, ensure_ascii=False))

r = child(FOLD_SRC, {"fold": True, "envs": {"MATHA_SYSENV_PROBE": "hello"}})
check("A2 命中环境变量", r.get("outputs") == ["hello"], json.dumps(r, ensure_ascii=False))

# —— B 用户形态：门控剪枝 ——
r = child(GATE_SRC, {"fold": True, "envs": {}})
check("B1 未开启走原路径", r.get("outputs") == ["1"] and r.get("n_jz") == 0
      and r.get("call_argcs") == [1], json.dumps(r, ensure_ascii=False))

r = child(GATE_SRC, {"fold": True,
                     "envs": {"MATHA_FAST_B09": "1"}})
check("B2 开启走快路径", r.get("outputs") == ["99"] and r.get("n_jz") == 0
      and r.get("call_argcs") == [1], json.dumps(r, ensure_ascii=False))

# —— C 编译期闸门 ——
r = child(VARKEY_SRC, {"fold": True, "envs": {}})
check("C1 非字面量键编译期报错", "compile_error" in r
      and "字面量" in r["compile_error"], json.dumps(r, ensure_ascii=False))

# —— D 休眠等价 ——
r = child(GATE_SRC, {"fold": False, "envs": {}})
check("D1 关闭时 sys_env 仍是未定义名字（休眠）",
      r.get("has_sysenv_global") is True and any("RUN_ERROR" in o for o in r.get("outputs", [])),
      json.dumps(r, ensure_ascii=False))

r = child(FOLD_SRC, {"fold": False, "envs": {"MATHA_SYSENV_PROBE": "hello"}})
check("D2 关闭时不读环境（无副作用泄漏）",
      any("RUN_ERROR" in o for o in r.get("outputs", [])),
      json.dumps(r, ensure_ascii=False))

fails = [n for n, ok, _ in results if not ok]
print(f"\nSUMMARY {len(results) - len(fails)}/{len(results)} passed"
      + (f"，失败：{fails}" if fails else ""))
sys.exit(1 if fails else 0)
