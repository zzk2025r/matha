"""OFF 态逐字节等价的**可信**对照：把 HEAD 版 compiler.py 作为独立模块加载，
与当前工作树编译器在同一 src 包环境下编译同一语料，逐指令比对 + 运行值比对。

先前用 worktree 取参照的尝试无效（cd 到工作区外失败 → 参照其实来自工作树自身，
等于自己对自己），本脚本改用 importlib 从磁盘加载指定修订的文件，
不改动工作树任何一个字节。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\trae")
sys.path.insert(0, str(ROOT))
sys.path.pop(0)
sys.path.insert(0, str(ROOT))

REF_FILE = ROOT / ".trae" / "p4_b09_preview" / "compiler_ref.py"


def load_ref():
    spec = importlib.util.spec_from_file_location("compiler_ref", str(REF_FILE))
    mod = importlib.util.module_from_spec(spec)
    # 必须先注册进 sys.modules：dataclass 处理时需要从 sys.modules 回查定义模块。
    sys.modules["compiler_ref"] = mod
    spec.loader.exec_module(mod)
    return mod


def dump_from(comp_mod, cases):
    from src.mbc import opcodes as OP
    from src.mbc.vm import run_module
    out = {}
    for name, src in cases.items():
        mod = comp_mod.compile_source(src)
        codes = {"main": [list(i) for i in mod.main_code]}
        for fn, f in mod.functions.items():
            codes[fn] = [list(i) for i in f.code]
        argcs = [i[1] for v in codes.values() for i in v
                 if len(i) >= 2 and i[0] == OP.CALL]
        outs = [str(o) for o in run_module(mod)]
        out[name] = {"codes": codes, "call_argcs": argcs, "outputs": outs}
    return out


def main() -> int:
    sys.path.insert(0, str(ROOT))
    try:
        subprocess.run(["git", "show", "9b5606b:src/mbc/compiler.py"],
                       cwd=ROOT, check=True,
                       stdout=open(REF_FILE, "wb"))
        sys.argv = ["x"]
        import importlib
        comp_mod = load_ref()

        # 语料复用 b09_fuse_compare 的 10 例
        ns: dict = {}
        exec((ROOT / ".trae" / "p4_b09_preview" / "b09_fuse_compare.py").read_text(
            encoding="utf-8").split("def _compile_dump")[0].replace(
            'sys.path.insert(0, str(Path.cwd()))', ''), ns)
        cases = ns["CASES"]

        ref = dump_from(comp_mod, cases)
        from src.mbc.compiler import compile_source as cur_compile  # noqa: F401
        cur = dump_from(importlib.import_module("src.mbc.compiler"), cases)

        bad_b, bad_v = [], []
        for name in cases:
            if json.dumps(ref[name]["codes"], sort_keys=True) != \
               json.dumps(cur[name]["codes"], sort_keys=True):
                bad_b.append(name)
            if ref[name]["outputs"] != cur[name]["outputs"]:
                bad_v.append(name)
        print(f"ref=9b5606b(仅 b09 休眠开关) vs cur=工作树(sys_env 折叠, 两开关 OFF)")
        print(f"cases={len(cases)} byte_mismatch={bad_b or '无'} value_mismatch={bad_v or '无'}")
        for name in cases:
            print(f"  {name:20s} argcs_ref={ref[name]['call_argcs']} "
                  f"argcs_cur={cur[name]['call_argcs']} out={cur[name]['outputs']}")
        return 1 if (bad_b or bad_v) else 0
    finally:
        # 参照文件与其编译缓存属可再生成物，用完即清（只删自己的模块缓存）。
        REF_FILE.unlink(missing_ok=True)
        for p in (REF_FILE.parent / "__pycache__").glob("compiler_ref.*.pyc"):
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
