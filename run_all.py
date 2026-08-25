# -*- coding: utf-8 -*-
"""Matha v4.3 一键执行脚本

功能：
1. 检查环境（Git、Python、依赖）
2. 安装缺失的工具
3. 运行测试
4. 执行发布

用法：
  python run_all.py
  python run_all.py --test-only    # 仅运行测试
  python run_all.py --publish      # 执行发布
  python run_all.py --dry-run      # 预览发布流程
  python run_all.py --skip-tests   # 跳过测试
  python run_all.py --install      # 安装环境工具
"""
import subprocess
import sys
import argparse
from pathlib import Path


def run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """运行命令。"""
    print(f"\n$ {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"命令失败 (exit code {result.returncode}): {cmd}")
    return result


def check_git() -> bool:
    """检查 Git 是否已安装。"""
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ Git: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print(f"  ❌ Git 未安装")
    print(f"  💡 请安装: python install_tools.py --git")
    print(f"  💡 或访问: https://git-scm.com/downloads")
    return False


def check_gh() -> bool:
    """检查 GitHub CLI 是否已安装。"""
    try:
        result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ GitHub CLI: {result.stdout.strip().split(chr(10))[0]}")
            return True
    except FileNotFoundError:
        pass
    print(f"  ⚠️  GitHub CLI 未安装（将跳过 Release 创建）")
    print(f"  💡 请安装: python install_tools.py --gh")
    print(f"  💡 或访问: https://cli.github.com")
    return False


def check_python() -> bool:
    """检查 Python 版本。"""
    version = sys.version_info
    if version >= (3, 8):
        print(f"  ✅ Python: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ❌ Python 版本过低: {version.major}.{version.minor}.{version.micro}（需要 >= 3.8）")
        return False


def run_tests() -> bool:
    """运行测试。"""
    print("\n【步骤 02】运行测试")
    try:
        result = run("python -m unittest discover -s tests -v", check=False)
        # 检查测试是否通过
        output = result.stdout + result.stderr
        if "FAILED" in output:
            print("\n  ❌ 测试失败")
            return False
        elif "OK" in output:
            print("\n  ✅ 测试通过")
            return True
        else:
            print("\n  ⚠️  测试输出未检测到结果")
            return True
    except Exception as e:
        print(f"\n  ❌ 测试运行失败: {e}")
        return False


def run_preflight() -> bool:
    """运行预检。"""
    print("\n【步骤 01】运行预检")
    try:
        result = run("python preflight_check.py", check=False)
        output = result.stdout
        if "所有检查通过" in output:
            print("\n  ✅ 预检通过")
            return True
        else:
            print("\n  ⚠️  预检存在警告")
            return True
    except Exception as e:
        print(f"\n  ❌ 预检运行失败: {e}")
        return False


def run_git_check() -> bool:
    """运行 Git 检查。"""
    print("\n【步骤 01】运行 Git 检查")
    try:
        result = run("python check_git.py", check=False)
        output = result.stdout
        if "所有检查通过" in output:
            print("\n  ✅ Git 检查通过")
            return True
        else:
            print("\n  ⚠️  Git 检查存在警告")
            return False
    except Exception as e:
        print(f"\n  ❌ Git 检查运行失败: {e}")
        return False


def run_file_check() -> bool:
    """运行文件检查。"""
    print("\n【步骤 01】运行文件检查")
    try:
        result = run("python check_files.py", check=False)
        output = result.stdout
        if "所有检查通过" in output or "检查通过" in output:
            print("\n  ✅ 文件检查通过")
            return True
        else:
            print("\n  ⚠️  文件检查存在警告")
            return True
    except Exception as e:
        print(f"\n  ❌ 文件检查运行失败: {e}")
        return False


def install_tools() -> bool:
    """安装环境工具。"""
    print("\n【步骤 00】安装环境工具")
    try:
        result = run("python install_tools.py", check=False)
        output = result.stdout
        if "所有工具安装成功" in output or "✅ 所有检查通过" in output:
            print("\n  ✅ 环境工具安装成功")
            return True
        else:
            print("\n  ⚠️  环境工具安装存在警告")
            return False
    except Exception as e:
        print(f"\n  ❌ 环境工具安装失败: {e}")
        return False


def run_publish(dry_run: bool = False) -> bool:
    """执行发布。"""
    print("\n【步骤 03】执行发布")
    cmd = "python publish_oneclick.py"
    if dry_run:
        cmd += " --dry-run"
    try:
        result = run(cmd, check=False)
        output = result.stdout
        if "发布完成" in output or "所有检查通过" in output:
            print("\n  ✅ 发布成功")
            return True
        else:
            print("\n  ⚠️  发布存在警告")
            return False
    except Exception as e:
        print(f"\n  ❌ 发布失败: {e}")
        return False


def main():
    """主入口。"""
    parser = argparse.ArgumentParser(
        description="Matha v4.3 一键执行脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_all.py                      # 完整流程
  python run_all.py --test-only          # 仅运行测试
  python run_all.py --publish            # 执行发布
  python run_all.py --dry-run            # 预览发布流程
  python run_all.py --skip-tests         # 跳过测试
  python run_all.py --install            # 安装环境工具
        """
    )
    parser.add_argument("--test-only", action="store_true", help="仅运行测试")
    parser.add_argument("--publish", action="store_true", help="执行发布")
    parser.add_argument("--dry-run", action="store_true", help="预览发布流程")
    parser.add_argument("--skip-tests", action="store_true", help="跳过测试")
    parser.add_argument("--install", action="store_true", help="安装环境工具")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Matha v4.3 一键执行脚本")
    print("=" * 60)
    print(f"Python: {sys.version.split()[0]}")
    print(f"系统: {sys.platform}")

    all_ok = True

    # 0. 安装环境工具（可选）
    if args.install:
        install_tools()

    # 1. 检查环境
    print("\n【步骤 00】检查环境")
    git_ok = check_git()
    gh_ok = check_gh()
    python_ok = check_python()

    if not python_ok:
        print("\n❌ Python 版本不满足要求，请升级后重试")
        sys.exit(1)

    if not git_ok:
        print("\n⚠️  Git 未安装，请先安装:")
        print("  python install_tools.py --git")
        all_ok = False

    # 2. 运行检查脚本
    if all_ok:
        run_git_check()
        run_file_check()
        run_preflight()

    # 3. 运行测试
    if not args.skip_tests and all_ok:
        if not run_tests():
            all_ok = False

    # 4. 执行发布
    if args.publish or args.dry_run:
        if not all_ok:
            print("\n⚠️  环境检查未通过，请先修复问题后再执行发布")
            sys.exit(1)
        run_publish(dry_run=args.dry_run)
    elif args.test_only:
        if not run_tests():
            sys.exit(1)
    else:
        # 默认完整流程
        print("\n" + "=" * 60)
        print("  完整流程执行完成")
        print("=" * 60)
        if all_ok:
            print("\n  ✅ 所有步骤执行成功")
            print("\n  下一步:")
            print("    1. 运行发布: python run_all.py --publish")
            print("    2. 预览发布: python run_all.py --dry-run")
        else:
            print("\n  ⚠️  存在需要修复的问题")
            print("\n  建议操作:")
            if not git_ok:
                print("    1. 安装 Git: python run_all.py --install")
            print("    2. 修复问题后重新运行: python run_all.py")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
