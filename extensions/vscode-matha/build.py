# -*- coding: utf-8 -*-
"""Matha VS Code 扩展打包脚本

功能：
1. 编译 TypeScript 源码
2. 打包为 VSIX 文件
3. 本地安装测试
4. 验证扩展功能
"""
import subprocess
import sys
import os
from pathlib import Path

EXTENSION_DIR = Path(__file__).parent.parent / "extensions" / "vscode-matha"


def run(cmd: str, cwd: Path = None, check: bool = True) -> subprocess.CompletedProcess:
    """运行命令并返回结果。"""
    print(f"\n$ {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=str(cwd or EXTENSION_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"命令失败: {cmd}")
    return result


def check_prerequisites():
    """检查前置条件。"""
    print("=" * 60)
    print("  检查前置条件")
    print("=" * 60)

    # 检查 Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        print(f"  Node.js: {result.stdout.strip()}")
    except FileNotFoundError:
        print("  ❌ Node.js 未安装")
        sys.exit(1)

    # 检查 npm
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        print(f"  npm: {result.stdout.strip()}")
    except FileNotFoundError:
        print("  ❌ npm 未安装")
        sys.exit(1)

    # 检查 TypeScript
    try:
        result = subprocess.run(["tsc", "--version"], capture_output=True, text=True)
        print(f"  TypeScript: {result.stdout.strip()}")
    except FileNotFoundError:
        print("  ⚠️  tsc 未全局安装，将使用 npx")

    # 检查 vsce
    try:
        result = subprocess.run(["vsce", "--version"], capture_output=True, text=True)
        print(f"  vsce: {result.stdout.strip()}")
    except FileNotFoundError:
        print("  ⚠️  vsce 未安装，将尝试本地安装")

    print("\n  ✅ 前置条件检查完成")


def install_dependencies():
    """安装依赖。"""
    print("\n" + "=" * 60)
    print("  安装依赖")
    print("=" * 60)

    # 安装 vsce（如果需要）
    try:
        subprocess.run(["vsce", "--version"], capture_output=True)
    except FileNotFoundError:
        print("  安装 vsce...")
        subprocess.run([sys.executable, "-m", "pip", "install", "vsce"], check=True)

    # 安装项目依赖
    print("  安装项目依赖...")
    run("npm install", check=False)


def compile_extension():
    """编译扩展。"""
    print("\n" + "=" * 60)
    print("  编译扩展")
    print("=" * 60)
    run("npm run compile")
    print("  ✅ 编译完成")


def package_extension():
    """打包为 VSIX。"""
    print("\n" + "=" * 60)
    print("  打包扩展")
    print("=" * 60)
    result = run("vsce package", check=False)

    # 查找生成的 VSIX 文件
    vsix_files = list(EXTENSION_DIR.glob("*.vsix"))
    if vsix_files:
        vsix_file = vsix_files[-1]
        print(f"\n  ✅ 打包完成: {vsix_file.name}")
        return vsix_file
    else:
        print("  ⚠️  未找到 VSIX 文件")
        return None


def test_extension(vsix_file: Path = None):
    """测试扩展。"""
    print("\n" + "=" * 60)
    print("  测试扩展")
    print("=" * 60)

    # 查找 VSIX 文件
    if vsix_file is None:
        vsix_files = list(EXTENSION_DIR.glob("*.vsix"))
        if vsix_files:
            vsix_file = vsix_files[-1]
        else:
            print("  ⚠️  未找到 VSIX 文件，跳过安装测试")
            return

    print(f"  安装包: {vsix_file.name}")

    # 使用 code 命令安装
    try:
        run(f"code --install-extension {vsix_file}")
        print("  ✅ 扩展安装成功")
    except Exception as e:
        print(f"  ⚠️  VS Code CLI 不可用: {e}")
        print(f"  请手动安装: code --install-extension {vsix_file}")


def verify_syntax():
    """验证语法文件。"""
    print("\n" + "=" * 60)
    print("  验证语法文件")
    print("=" * 60)

    grammar_file = EXTENSION_DIR / "syntaxes" / "matha.tmGrammar.json"
    if grammar_file.exists():
        import json
        with open(grammar_file, 'r', encoding='utf-8') as f:
            grammar = json.load(f)
        print(f"  ✅ 语法文件有效: {len(grammar.get('patterns', []))} 条规则")
    else:
        print("  ⚠️  语法文件不存在")

    package_file = EXTENSION_DIR / "package.json"
    if package_file.exists():
        with open(package_file, 'r', encoding='utf-8') as f:
            package = json.load(f)
        print(f"  ✅ 扩展 manifest 有效: {package.get('name', 'unknown')} v{package.get('version', '?')}")
    else:
        print("  ⚠️  package.json 不存在")


def run_lint():
    """运行 lint。"""
    print("\n" + "=" * 60)
    print("  运行代码检查")
    print("=" * 60)
    run("npm run lint", check=False)


def main():
    """主入口。"""
    print("\n" + "=" * 60)
    print("  Matha VS Code 扩展构建脚本")
    print("=" * 60)

    try:
        check_prerequisites()
        install_dependencies()
        compile_extension()
        verify_syntax()
        run_lint()
        vsix_file = package_extension()
        test_extension(vsix_file)

        print("\n" + "=" * 60)
        print("  构建完成!")
        print("=" * 60)
        print("\n  下一步:")
        print("    1. 打开 VS Code")
        print("    2. 按 Ctrl+Shift+P 打开命令面板")
        print("    3. 输入 'Matha: 解析当前文本为意图'")
        print("    4. 或在 .matha 文件中享受语法高亮")

    except Exception as e:
        print(f"\n❌ 构建失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
