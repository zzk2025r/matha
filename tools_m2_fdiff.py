"""Per-function M2 diff: resolves constant-index operands to values and
closure operands to function NAMES, so pool-index shifts and lambda
numbering differences show up as genuine emission differences."""
import sys
import pathlib

sys.path.insert(0, ".")
import tools_m2_probe as P  # noqa: E402

CONST_OPCODES = {0x01, 0x17, 0x18, 0x54}          # PUSH_CONST/LOAD_GLOBAL/STORE_GLOBAL/GET_ATTR
MAKE_CLOSURE = 0x20
HALT = 0xFF


def _names(mod):
    return {n: f[3] for n, f in mod["functions"].items()}


def resolve(mod):
    consts = mod["constants"]
    fns = _names(mod)

    def one(ins):
        if ins[0] == HALT or len(ins) == 1:
            return (ins[0],)
        if ins[0] == MAKE_CLOSURE:
            idx = ins[1]
            return (ins[0], fns.get(idx, f"<fn#{idx}>"))
        if ins[0] in CONST_OPCODES:
            return (ins[0], consts[ins[1]] if 0 <= ins[1] < len(consts) else f"?{ins[1]}")
        return tuple(ins)

    out = {"main": [one(i) for i in mod["main"]]}
    for n, code in mod["functions"].items():
        out[n] = [one(i) for i in code[3]]
    return out


def first_diff(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and type(a[i]) is type(b[i]) and a[i] == b[i]:
        i += 1
    if i == len(a) == len(b):
        return None
    return i, a[i:i + 4], b[i:i + 4]


def report(rel, vm):
    src = pathlib.Path(rel).read_text(encoding="utf-8")
    h = resolve(P.canon(P.host_compile(src)))
    s = resolve(P.canon(P.self_dict_to_module(vm.call("编译", src))))
    bad = []
    for name in sorted(set(h) | set(s)):
        a, b = h.get(name, []), s.get(name, [])
        d = first_diff(a, b)
        if d is not None:
            bad.append((name, d))
    total = sum(len(v) for v in h.values())
    print(f"== {rel}  instrs={total}  differing={len(bad)}")
    for name, (i, a, b) in bad[:6]:
        print(f"   {name} @{i}\n      H {a}\n      S {b}")
    return bad


if __name__ == "__main__":
    vm = P.build_stage1()
    for rel in (sys.argv[1:] or P.BOOT_FILES):
        report(rel, vm)
