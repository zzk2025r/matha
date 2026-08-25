# -*- coding: utf-8 -*-
"""Matha 依赖一键安装脚本

功能：
1. 检测并安装 SymPy（符号微积分）
2. 检测并安装 NumPy（矩阵运算，可选）
3. 验证安装结果
4. 提供手动安装指引

用法：
  python install_dependencies.py
  python install_dependencies.py --all
  python install_dependencies.py --sympy
  python install_dependencies.py --numpy
  python install_dependencies.py --verify
"""
import subprocess
import sys
import platform
from pathlib import Path


class DependencyInstaller:
    """依赖安装器。"""

    def __init__(self):
        self.results = {}
        self.os_name = platform.system().lower()

    def run_command(self, cmd: str) -> subprocess.CompletedProcess:
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
        return result

    def check_installed(self, module_name: str) -> bool:
        """检查模块是否已安装。"""
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False

    def install_sympy(self) -> bool:
        """安装 SymPy。"""
        print("\n" + "=" * 60)
        print("  安装 SymPy（符号微积分）")
        print("=" * 60)

        if self.check_installed("sympy"):
            import sympy
            version = sympy.__version__
            print(f"  ✅ SymPy 已安装: {version}")
            self.results['sympy'] = True
            return True

        print("  ⚠️  SymPy 未安装")
        print("  正在安装...")

        result = self.run_command("pip install sympy")
        if result.returncode == 0:
            print("  ✅ SymPy 安装成功")
            self.results['sympy'] = True
            return True
        else:
            print("  ❌ SymPy 安装失败")
            print("  💡 请手动安装: pip install sympy")
            self.results['sympy'] = False
            return False

    def install_numpy(self) -> bool:
        """安装 NumPy。"""
        print("\n" + "=" * 60)
        print("  安装 NumPy（矩阵运算，可选）")
        print("=" * 60)

        if self.check_installed("numpy"):
            import numpy
            version = numpy.__version__
            print(f"  ✅ NumPy 已安装: {version}")
            self.results['numpy'] = True
            return True

        print("  ⚠️  NumPy 未安装（可选依赖）")
        print("  正在安装...")

        result = self.run_command("pip install numpy")
        if result.returncode == 0:
            print("  ✅ NumPy 安装成功")
            self.results['numpy'] = True
            return True
        else:
            print("  ⚠️  NumPy 安装失败（可稍后手动安装）")
            self.results['numpy'] = False
            return False

    def verify_installation(self) -> bool:
        """验证安装结果。"""
        print("\n" + "=" * 60)
        print("  验证安装")
        print("=" * 60)

        all_ok = True

        # 验证 SymPy
        if self.check_installed("sympy"):
            import sympy
            print(f"  ✅ SymPy: {sympy.__version__}")
            self.results['sympy'] = True
        else:
            print(f"  ❌ SymPy: 未安装")
            self.results['sympy'] = False
            all_ok = False

        # 验证 NumPy
        if self.check_installed("numpy"):
            import numpy
            print(f"  ✅ NumPy: {numpy.__version__}")
            self.results['numpy'] = True
        else:
            print(f"  ⚠️  NumPy: 未安装（可选）")
            self.results['numpy'] = False

        return all_ok

    def run(self, target: str = "all") -> bool:
        """运行安装流程。"""
        print("\n" + "=" * 60)
        print("  Matha 依赖安装脚本")
        print("=" * 60)
        print(f"Python: {sys.version.split()[0]}")
        print(f"系统: {platform.system()} {platform.release()}")

        if target in ("all", "sympy"):
            self.install_sympy()

        if target in ("all", "numpy"):
            self.install_numpy()

        # 验证
        ok = self.verify_installation()

        # 总结
        print("\n" + "=" * 60)
        print("  安装总结")
        print("=" * 60)

        if ok:
            print("\n  ✅ 所有依赖安装成功！")
            print("\n  下一步:")
            print("    运行测试: python -m unittest tests.test_calculus_symbolic -v")
            print("    运行 Demo: python src/stdlib/calculus_symbolic.py")
        else:
            print("\n  ⚠️  部分依赖安装失败")
            print("\n  建议操作:")
            if not self.results.get('sympy'):
                print("    1. 安装 SymPy: pip install sympy")
            if not self.results.get('numpy'):
                print("    2. 安装 NumPy: pip install numpy（可选）")

        print("\n" + "=" * 60)

        return ok


def main():
    """主入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Matha 依赖安装脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python install_dependencies.py              # 安装所有依赖
  python install_dependencies.py --all        # 安装所有依赖
  python install_dependencies.py --sympy      # 仅安装 SymPy
  python install_dependencies.py --numpy      # 仅安装 NumPy
  python install_dependencies.py --verify     # 仅验证安装
        """
    )
    parser.add_argument("--sympy", action="store_true", help="仅安装 SymPy")
    parser.add_argument("--numpy", action="store_true", help="仅安装 NumPy")
    parser.add_argument("--verify", action="store_true", help="仅验证安装")
    args = parser.parse_args()

    installer = DependencyInstaller()

    if args.verify:
        ok = installer.verify_installation()
    else:
        target = "all"
        if args.sympy:
            target = "sympy"
        elif args.numpy:
            target = "numpy"
        ok = installer.run(target=target)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
