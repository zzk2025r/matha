# -*- coding: utf-8 -*-
"""Matha v4.3 文件权限和依赖检查脚本

功能：
1. 检查所有新增文件的权限
2. 检查文件路径是否正确
3. 检查依赖项是否完整
4. 生成检查报告

用法：
  python check_files.py
  python check_files.py --verbose
"""
import subprocess
import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple


class FileChecker:
    """文件检查器。"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent
        self.results = {
            "files": [],
            "dependencies": [],
            "errors": [],
            "warnings": []
        }

    def check_file_exists(self, file_path: Path, description: str) -> Tuple[bool, str]:
        """检查文件是否存在。"""
        if file_path.exists():
            return True, f"✅ {description}: {file_path.relative_to(self.project_root)}"
        else:
            return False, f"❌ {description}: {file_path.relative_to(self.project_root)} (不存在)"

    def check_file_permissions(self, file_path: Path, expected_executable: bool = False) -> Tuple[bool, str]:
        """检查文件权限。"""
        if not file_path.exists():
            return False, f"⚠️  文件不存在: {file_path.name}"

        # 检查可读性
        if not os.access(file_path, os.R_OK):
            return False, f"❌ 文件不可读: {file_path.name}"

        # 检查可执行性
        is_executable = os.access(file_path, os.X_OK)
        if expected_executable and not is_executable:
            return False, f"⚠️  脚本文件缺少执行权限: {file_path.name}"

        return True, f"✅ 权限正常: {file_path.name}"

    def check_python_import(self, module_path: str) -> Tuple[bool, str]:
        """检查 Python 模块是否可以导入。"""
        try:
            # 添加到路径
            sys.path.insert(0, str(self.project_root))
            __import__(module_path)
            return True, f"✅ 模块可导入: {module_path}"
        except ImportError as e:
            return False, f"❌ 模块导入失败: {module_path} ({e})"
        except Exception as e:
            return False, f"⚠️  模块检查出错: {module_path} ({e})"

    def check_dependency(self, package: str, import_name: str = None) -> Tuple[bool, str]:
        """检查依赖包是否安装。"""
        if import_name is None:
            import_name = package

        try:
            __import__(import_name)
            return True, f"✅ {package} 已安装"
        except ImportError:
            return False, f"❌ {package} 未安装 (pip install {package})"

    def run_checks(self) -> bool:
        """运行所有检查。"""
        print("\n" + "=" * 60)
        print("  Matha v4.3 文件与依赖检查")
        print("=" * 60)
        print(f"项目根目录: {self.project_root}")
        print(f"Python 版本: {sys.version.split()[0]}")

        all_ok = True

        # 1. 检查新增文件
        print("\n【1. 检查新增文件】")
        new_files = [
            # 核心源码
            ("src/intent/mir_generator.py", "MIR 代码生成器"),
            ("src/stdlib/algebra.py", "代数标准库"),
            ("src/stdlib/calculus.py", "微积分标准库"),
            ("src/stdlib/logic.py", "逻辑标准库"),
            ("src/jupyter/matha_magic.py", "Jupyter 魔法命令"),
            ("src/jupyter/notebook_example.py", "Jupyter 示例"),
            ("src/pkg_manager.py", "包管理器"),
            # 测试文件
            ("tests/test_jupyter_magic.py", "Jupyter 测试"),
            ("tests/test_pkg_manager_dependency.py", "依赖解析测试"),
            # VS Code 插件
            ("extensions/vscode-matha/package.json", "扩展 manifest"),
            ("extensions/vscode-matha/publish.py", "发布脚本"),
            ("extensions/vscode-matha/build.py", "构建脚本"),
            # 文档
            ("docs/RELEASE_NOTES_v4.3.md", "发布说明"),
            ("docs/KNOWN_ISSUES.md", "已知问题"),
            ("docs/KNOWN_ISSUES_TABLE.md", "已知问题表格"),
            # 脚本
            ("preflight_check.py", "预检脚本"),
            ("install_dependencies.py", "依赖安装脚本"),
            ("release_oneclick.py", "一键发布脚本"),
            ("check_git.py", "Git 检查脚本"),
            ("publish_oneclick.py", "发布脚本"),
        ]

        for file_path, description in new_files:
            full_path = self.project_root / file_path
            exists, msg = self.check_file_exists(full_path, description)
            print(f"  {msg}")
            self.results["files"].append({"path": file_path, "exists": exists, "desc": description})
            if not exists:
                all_ok = False
                self.results["errors"].append(f"文件不存在: {file_path}")

        # 2. 检查 Python 模块导入
        print("\n【2. 检查 Python 模块导入】")
        modules = [
            "src.intent.mir_generator",
            "src.stdlib.algebra",
            "src.stdlib.calculus",
            "src.stdlib.logic",
            "src.jupyter.matha_magic",
            "src.pkg_manager",
        ]

        for module in modules:
            ok, msg = self.check_python_import(module)
            print(f"  {msg}")
            self.results["dependencies"].append({"module": module, "ok": ok})
            if not ok:
                all_ok = False
                self.results["errors"].append(f"模块导入失败: {module}")

        # 3. 检查依赖包
        print("\n【3. 检查依赖包】")
        dependencies = [
            ("math", None),  # 标准库
            ("multiprocessing", None),  # 标准库
            ("queue", None),  # 标准库
            ("anthropic", None),  # LLM
            ("openai", None),  # LLM
            ("IPython", "IPython"),  # Jupyter
        ]

        for package, import_name in dependencies:
            ok, msg = self.check_dependency(package, import_name)
            print(f"  {msg}")
            self.results["dependencies"].append({"package": package, "ok": ok})
            if not ok:
                self.results["warnings"].append(msg)

        # 4. 检查文件权限
        print("\n【4. 检查文件权限】")
        script_files = [
            "preflight_check.py",
            "install_dependencies.py",
            "release_oneclick.py",
            "check_git.py",
            "publish_oneclick.py",
            "extensions/vscode-matha/build.py",
            "extensions/vscode-matha/publish.py",
        ]

        for script in script_files:
            full_path = self.project_root / script
            if full_path.exists():
                ok, msg = self.check_file_permissions(full_path, expected_executable=True)
                print(f"  {msg}")
            else:
                print(f"  ⚠️  文件不存在: {script}")

        # 5. 检查配置文件
        print("\n【5. 检查配置文件】")
        config_files = [
            ("extensions/vscode-matha/package.json", "JSON"),
            ("extensions/vscode-matha/language-configuration.json", "JSON"),
            ("extensions/vscode-matha/syntaxes/matha.tmGrammar.json", "JSON"),
        ]

        for file_path, fmt in config_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    print(f"  ✅ {file_path} 格式正确")
                except json.JSONDecodeError as e:
                    print(f"  ❌ {file_path} JSON 格式错误: {e}")
                    all_ok = False
                    self.results["errors"].append(f"JSON 格式错误: {file_path}")
            else:
                print(f"  ⚠️  文件不存在: {file_path}")

        # 6. 检查测试文件
        print("\n【6. 检查测试文件】")
        test_files = [
            "tests/test_jupyter_magic.py",
            "tests/test_pkg_manager_dependency.py",
        ]

        for test in test_files:
            full_path = self.project_root / test
            ok, msg = self.check_file_exists(full_path, "测试文件")
            print(f"  {msg}")

        # 总结
        print("\n" + "=" * 60)
        print("  检查总结")
        print("=" * 60)

        if self.results["errors"]:
            print(f"\n  ❌ 发现 {len(self.results['errors'])} 个错误:")
            for error in self.results["errors"]:
                print(f"    - {error}")
            all_ok = False

        if self.results["warnings"]:
            print(f"\n  ⚠️  发现 {len(self.results['warnings'])} 个警告:")
            for warning in self.results["warnings"]:
                print(f"    - {warning}")

        if all_ok and not self.results["warnings"]:
            print("\n  ✅ 所有检查通过！")
        elif all_ok:
            print("\n  ⚠️  检查通过，但有警告")
        else:
            print("\n  ❌ 存在需要修复的问题")

        print("=" * 60)

        return all_ok


def main():
    """主入口。"""
    import argparse

    parser = argparse.ArgumentParser(description="Matha v4.3 文件与依赖检查")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    checker = FileChecker(verbose=args.verbose)
    result = checker.run_checks()

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
