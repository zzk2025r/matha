# -*- coding: utf-8 -*-
"""29d Track B：自举执行面全语料 sweep（boot 面 5 文件链 + 宿主面对拍）。

语料枚举与 ast_vm_matrix 同口径（matha/examples/golden_tests/tests/stdlib
五目录 rglob("*.matha")）。逐文件统一判据：

  boot 面   输出清空 → 扫描 → parse → 注册内建(空环境) → 执行语句 → 输出快照
            （每文件 fresh env0，输出槽复位；bootvm 每 worker 构建一次复用）
  宿主面    host_interp.interpret（每文件新解释器）
  双 ok     输出归一（数值 float 化 / dict 键字符串化）相等 → equal=true；
            不等 → equal=false 记首分歧下标
  单边错误  boot_err / host_err 诚实记录（截断 240 字符）
  超时      per-file get 超时 + 全局轮预算；uncollected 下一轮重试，
            三轮未收 → honest "timeout"（含 worker 崩溃丢任务面）

用法：
  python scripts/selfhost_matrix.py --write [--workers N] [--timeout 秒] [--filter 子串] [--limit N]
  python scripts/selfhost_matrix.py --check        # 全量重跑与快照对拍（重档 lane）
  python scripts/selfhost_matrix.py --structure    # 快结构锁：文件清单一致 + 汇总算术闭合（pytest 门禁用）

快照 docs/selfhost_matrix.json：summary 计数闭合 + files 按路径排序；
不含时间戳（确定性）。known 双面一致遗留语义（输出追踪双记/空输出记 0）
不改判据——equal 只问 boot 与宿主是否一致，不问语义"应该"是什么。
"""
import argparse
import json
import multiprocessing as mp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SNAPSHOT = ROOT / "docs" / "selfhost_matrix.json"
CORPUS_DIRS: tuple[str, ...] = ("matha", "examples", "golden_tests", "tests", "stdlib")
BOOT_FILES: tuple[str, ...] = ("matha/lexer.matha", "matha/stdlib.matha",
                               "matha/parser.matha",
                               "matha/runtime/matha_runtime.matha",
                               "matha/interp_matha.matha")
_ERR_TRUNC = 240


def corpus_files(filter_sub: str | None = None, limit: int | None = None) -> list[str]:
    files: list[str] = []
    for d in CORPUS_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.matha")):
            rel = path.relative_to(ROOT).as_posix()
            if rel in BOOT_FILES:
                continue
            files.append(rel)
    if filter_sub:
        files = [f for f in files if filter_sub in f]
    if limit:
        files = files[:limit]
    return files


def _norm(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    return v


def _first_div(a, b):
    """首分歧下标（归一层），无分歧返回 None。"""
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return None
    if isinstance(na, list) and isinstance(nb, list):
        for i in range(min(len(na), len(nb))):
            if na[i] != nb[i]:
                return i
        return min(len(na), len(nb))
    return "?"


# ---------------- worker ----------------

_worker_vm = None


def _worker_init():
    global _worker_vm
    sys.setrecursionlimit(20000)
    sys.set_int_max_str_digits(0)
    from src import ast_nodes as ast
    from src.kernel.errors import MathaRuntimeError
    from src.mbc.compiler import Compiler
    from src.mbc.vm import VM
    from src.parser import parse as py_parse

    def _strip_bom(src):
        return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src

    comp = Compiler()
    decls = []
    for rel in BOOT_FILES:
        decls.extend(py_parse(_strip_bom(
            (ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(ast.Program(decls=decls))
    _worker_vm = VM(comp.mod)
    _worker_vm.run()
    _worker_vm.globals["MathaRuntimeError"] = MathaRuntimeError
    # 链模块 ns 预绑定（driver 面，29d）：只绑定在场的链模块命名空间。
    global _worker_nss
    _worker_nss = {nm: _worker_vm.globals[nm]
                   for nm in ("词法器", "标准库", "语法器", "运行时引擎", "解释器")
                   if isinstance(_worker_vm.globals.get(nm), dict)}


_worker_nss = {}


def _run_one(rel: str) -> dict:
    src = (ROOT / rel).read_text(encoding="utf-8")
    src = src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src
    entry = {"path": rel}
    b_outs = b_err = None
    try:
        _worker_vm.call("输出清空")
        toks = _worker_vm.call("扫描", src, 0, 1, 1, [])
        prog = _worker_vm.call("parse", toks)
        env0 = _worker_vm.call("注册内建", _worker_vm.call("空环境"))
        for nm, ns in _worker_nss.items():
            env0 = _worker_vm.call("绑定环境", env0, nm, ns)
        _worker_vm.call("执行语句", prog, env0)
        b_outs = list(_worker_vm.call("输出快照"))
    except Exception as e:
        b_err = f"{type(e).__name__}: {e}"[:_ERR_TRUNC]
    h_outs = h_err = None
    try:
        from src import interp as host_interp
        h_outs, _trace = host_interp.interpret(src)
    except Exception as e:
        h_err = f"{type(e).__name__}: {e}"[:_ERR_TRUNC]
    entry["boot"] = "ok" if b_err is None else "err"
    entry["host"] = "ok" if h_err is None else "err"
    if b_err is not None:
        entry["boot_err"] = b_err
    if h_err is not None:
        entry["host_err"] = h_err
    if b_err is None and h_err is None:
        equal = _norm(b_outs) == _norm(h_outs)
        entry["equal"] = equal
        if not equal:
            entry["first_div"] = _first_div(b_outs, h_outs)
            entry["n_boot_outs"] = len(b_outs)
            entry["n_host_outs"] = len(h_outs)
        elif b_outs:
            entry["n_outs"] = len(b_outs)
    return entry


def _classify(entry: dict) -> str:
    if entry.get("boot") == "timeout" or entry.get("host") == "timeout":
        return "timeout"
    b, h = entry.get("boot"), entry.get("host")
    if b == "ok" and h == "ok":
        return "both_ok_equal" if entry.get("equal") else "both_ok_differ"
    if b == "err" and h == "err":
        return "both_err"
    if b == "err":
        return "boot_err_host_ok"
    if h == "err":
        return "boot_ok_host_err"
    return "unknown"


# ---------------- sweep driver ----------------

def run_sweep(files: list[str], workers: int, timeout: float) -> list[dict]:
    results: dict[str, dict] = {}
    pending = list(files)
    rounds = 0
    while pending and rounds < 3:
        rounds += 1
        ctx = mp.get_context("spawn")
        pool = ctx.Pool(processes=workers, initializer=_worker_init)
        try:
            asyncs = [(rel, pool.apply_async(_run_one, (rel,))) for rel in pending]
            uncollected = []
            for rel, a in asyncs:
                try:
                    results[rel] = a.get(timeout=timeout)
                except mp.TimeoutError:
                    uncollected.append(rel)
            pending = [rel for rel in uncollected if rel not in results]
        finally:
            pool.terminate()
            pool.join()
    for rel in pending:
        results[rel] = {"path": rel, "boot": "timeout", "host": "timeout"}
    return [results[rel] for rel in files]


def summarize(entries: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for e in entries:
        c = _classify(e)
        counts[c] = counts.get(c, 0) + 1
    summary = {"files": len(entries)}
    for key in ("both_ok_equal", "both_ok_differ", "boot_err_host_ok",
                "boot_ok_host_err", "both_err", "timeout"):
        summary[key] = counts.get(key, 0)
    return summary


def build_snapshot(files, entries) -> dict:
    # 条目按 corpus_files 枚举序输出（目录分组序）——与 structure_check 的
    # 文件清单逐位对拍同源；worker 完成序不稳定，全局字母序与枚举序不一致。
    by = {e["path"]: e for e in entries}
    return {
        "version": 1,
        "corpus_dirs": list(CORPUS_DIRS),
        "boot_files": list(BOOT_FILES),
        "summary": summarize(entries),
        "files": [by[rel] for rel in files],
        "enumerated": len(files),
    }


def write_snapshot(args) -> int:
    files = corpus_files(args.filter, args.limit)
    print(f"[selfhost_matrix] 语料 {len(files)} 文件，workers={args.workers} "
          f"timeout={args.timeout}s")
    entries = run_sweep(files, args.workers, args.timeout)
    snap = build_snapshot(files, entries)
    print("[selfhost_matrix] 汇总:", json.dumps(snap["summary"], ensure_ascii=False))
    differs = [e for e in snap["files"] if _classify(e) == "both_ok_differ"]
    for e in differs[:20]:
        print(f"  [differ] {e['path']} first_div={e.get('first_div')} "
              f"n_boot={e.get('n_boot_outs')} n_host={e.get('n_host_outs')}")
    errs = [e for e in snap["files"] if _classify(e).endswith("host_ok")]
    for e in errs[:10]:
        print(f"  [boot_err] {e['path']} {e.get('boot_err')}")
    if args.filter or args.limit:
        print("[selfhost_matrix] 子集试跑（--filter/--limit）：不写快照")
        return 0
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"[selfhost_matrix] 快照写入 {SNAPSHOT}")
    return 0


def load_snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def check_snapshot(args) -> tuple[bool, str]:
    snap = load_snapshot()
    files = corpus_files(args.filter, args.limit)
    if args.filter or args.limit:
        return False, "--check 不支持 --filter/--limit（全量对拍口径）"
    if snap.get("enumerated") != len(files) or \
       [e["path"] for e in snap["files"]] != files:
        return False, "快照文件清单与当前语料枚举不一致（需 --write 重生成）"
    entries = run_sweep(files, args.workers, args.timeout)
    problems = []
    old_by = {e["path"]: e for e in snap["files"]}
    for e in entries:
        old = old_by.get(e["path"])
        if old is None:
            problems.append(f"{e['path']}: 快照缺条目")
            continue
        if _classify(old) != _classify(e):
            problems.append(f"{e['path']}: 分类漂移 {_classify(old)} -> {_classify(e)}")
        elif _classify(e) == "both_ok_differ":
            if old.get("first_div") != e.get("first_div"):
                problems.append(f"{e['path']}: 首分歧漂移 "
                                f"{old.get('first_div')} -> {e.get('first_div')}")
    new_summary = summarize(entries)
    if new_summary != snap["summary"]:
        problems.append(f"汇总漂移: {snap['summary']} -> {new_summary}")
    return (not problems), ("；".join(problems[:20]) if problems else "一致")


def structure_check() -> tuple[bool, str]:
    """快结构锁（pytest 门禁）：文件清单一致 + 汇总算术闭合 + 条目形态。"""
    if not SNAPSHOT.exists():
        return False, "快照缺失 docs/selfhost_matrix.json（先 --write）"
    snap = load_snapshot()
    files = corpus_files()
    if snap.get("enumerated") != len(files) or \
       [e["path"] for e in snap["files"]] != files:
        return False, "快照文件清单与当前语料枚举不一致（需 --write 重生成）"
    s = snap["summary"]
    total = (s["both_ok_equal"] + s["both_ok_differ"] + s["boot_err_host_ok"]
             + s["boot_ok_host_err"] + s["both_err"] + s["timeout"])
    if total != s["files"] or s["files"] != len(snap["files"]):
        return False, f"汇总算术不闭合: {s}"
    for e in snap["files"]:
        if _classify(e) == "unknown":
            return False, f"{e['path']}: 条目形态未知"
        if e["path"] in BOOT_FILES:
            return False, f"{e['path']}: boot 链文件不应入 sweep"
    return True, f"结构闭合 files={s['files']}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="29d 自举执行面全语料 sweep")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--structure", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--filter", type=str, default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    if args.write:
        return write_snapshot(args)
    if args.check:
        ok, msg = check_snapshot(args)
        print(f"[selfhost_matrix --check] {'一致' if ok else '漂移'}: {msg}")
        return 0 if ok else 1
    ok, msg = structure_check()
    print(f"[selfhost_matrix --structure] {'闭合' if ok else '不闭合'}: {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
