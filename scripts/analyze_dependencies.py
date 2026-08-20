"""
matha-auth 依赖冲突分析工具

用法:
  python analyze_dependencies.py
"""
from __future__ import annotations
import sys
from pathlib import Path

# 读取 pyproject.toml 和 setup.py 中的依赖声明
PKG_DIR = Path(__file__).resolve().parent.parent / "packages"
PYPROJECT = PKG_DIR / "pyproject.toml"
SETUP_PY = PKG_DIR / "setup.py"


def parse_deps(filepath: Path) -> dict[str, list[str]]:
    """从 pyproject.toml / setup.py 解析依赖声明。"""
    content = filepath.read_text(encoding="utf-8") if filepath.exists() else ""
    deps: dict[str, list[str]] = {"install_requires": [], "extras": {}}

    # 解析 install_requires
    import re
    m = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if m:
        deps["install_requires"] = re.findall(r'"([^"]+)"', m.group(1))

    # 解析 extras
    extras = re.findall(r'"(\w+)"\s*=\s*\[(.*?)\]', content, re.DOTALL)
    for name, body in extras:
        deps["extras"][name] = re.findall(r'"([^"]+)"', body)

    return deps


def check_conflicts(deps: dict[str, list[str]]) -> list[dict]:
    """检查依赖冲突（简单版：版本号范围交叉检查）。"""
    conflicts = []
    all_deps: dict[str, str] = {}

    for pkg_spec in deps.get("install_requires", []):
        pkg, _, ver = pkg_spec.partition(">=")
        all_deps[pkg.strip()] = ver.strip() if ver else "*"

    for extra_name, pkg_specs in deps.get("extras", {}).items():
        for pkg_spec in pkg_specs:
            pkg, _, ver = pkg_spec.partition(">=")
            pkg = pkg.strip()
            if pkg in all_deps and all_deps[pkg] != "*" and ver.strip() != "*":
                if all_deps[pkg] != ver.strip():
                    conflicts.append({
                        "package": pkg,
                        "install_requires": all_deps[pkg],
                        f"extra_{extra_name}": ver.strip(),
                    })
    return conflicts


def main() -> None:
    print("=" * 60)
    print("  matha-auth 依赖冲突分析")
    print("=" * 60)

    # 分析 pyproject.toml
    pyproject_deps = parse_deps(PYPROJECT)
    print(f"\n  [pyproject.toml]")
    print(f"    install_requires: {pyproject_deps['install_requires'] or '（无，纯 stdlib）'}")
    for name, pkgs in pyproject_deps["extras"].items():
        print(f"    [{name}]: {pkgs}")

    # 分析 setup.py
    setup_deps = parse_deps(SETUP_PY)
    print(f"\n  [setup.py]")
    print(f"    install_requires: {setup_deps['install_requires'] or '（无，纯 stdlib）'}")
    for name, pkgs in setup_deps["extras"].items():
        print(f"    [{name}]: {pkgs}")

    # 检查冲突
    all_deps = {**pyproject_deps, **setup_deps}
    conflicts = check_conflicts(all_deps)

    print(f"\n  [冲突检查结果]")
    if conflicts:
        for c in conflicts:
            print(f"    ✗ {c['package']}: install_requires={c['install_requires']} "
                  f"!= extra={list(c.keys())[2]}={c[list(c.keys())[2]]}")
    else:
        print("    ✓ 未发现版本冲突")

    # 核心模块依赖检查
    print(f"\n  [核心模块依赖检查]")
    core_modules = [
        PKG_DIR / "matha_auth" / "service.py",
        PKG_DIR / "matha_auth" / "rbac.py",
        PKG_DIR / "matha_auth" / "jwt.py",
        PKG_DIR / "matha_auth" / "password.py",
        PKG_DIR / "matha_auth" / "api.py",
        PKG_DIR / "matha_auth" / "models.py",
        PKG_DIR / "matha_auth" / "exceptions.py",
    ]
    stdlib_only = True
    for mod in core_modules:
        if not mod.exists():
            continue
        content = mod.read_text(encoding="utf-8")
        imports = [line.strip() for line in content.splitlines()
                   if line.strip().startswith("import ") or line.strip().startswith("from ")]
        third_party = [i for i in imports
                       if not any(x in i for x in ["matha_auth", "typing", "dataclasses",
                                                    "logging", "uuid", "time", "base64",
                                                    "hashlib", "hmac", "json", "os"])]
        if third_party:
            stdlib_only = False
            print(f"    ⚠ {mod.name}: 含第三方依赖 {third_party}")
        else:
            print(f"    ✓ {mod.name}: 纯 stdlib")

    if stdlib_only:
        print("\n  ✓ 核心模块全部使用 Python 标准库，无第三方依赖")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
