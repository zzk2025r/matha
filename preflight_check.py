# -*- coding: utf-8 -*-
"""Matha v4.3 预检脚本

功能：
1. 检测 Python 版本
2. 检测必需依赖
3. 检测可选依赖（LLM SDK、Jupyter 等）
4. 检测 VS Code 插件依赖
5. 生成安装建议

用法：
  python preflight_check.py
  python preflight_check.py --strict  # 严格模式，缺少依赖时退出码为 1
"""
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


class PreflightChecker:
    """预检检查器。"""

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.results: Dict[str, Tuple[bool, str]] = {}
        self.suggestions: List[str] = []

    def check_python_version(self) -> bool:
        """检查 Python 版本。"""
        version = sys.version_info
        required = (3, 8)

        if version >= required:
            self.results['python'] = (True, f"Python {version.major}.{version.minor}.{version.micro}")
            return True
        else:
            self.results['python'] = (False, f"需要 Python >= 3.8，当前 {version.major}.{version.minor}.{version.micro}")
            self.suggestions.append(f"请升级 Python 到 >= 3.8（当前：{version.major}.{version.minor}.{version.micro}）")
            return False

    def check_required_dependencies(self) -> bool:
        """检查必需依赖。"""
        required = [
            ('math', 'math（标准库）'),
            ('multiprocessing', 'multiprocessing（标准库）'),
            ('queue', 'queue（标准库）'),
            ('json', 'json（标准库）'),
            ('re', 're（标准库）'),
            ('hashlib', 'hashlib（标准库）'),
            ('pathlib', 'pathlib（标准库）'),
        ]

        all_ok = True
        for module, desc in required:
            try:
                __import__(module)
                self.results[module] = (True, desc)
            except ImportError:
                self.results[module] = (False, f"缺少 {desc}")
                self.suggestions.append(f"请安装 {desc}（通常是 Python 标准库，无需额外安装）")
                all_ok = False

        return all_ok

    def check_llm_dependencies(self) -> Dict[str, Tuple[bool, str]]:
        """检查 LLM 相关依赖。"""
        llm_deps = [
            ('anthropic', 'anthropic', 'Claude API'),
            ('openai', 'openai', 'GPT API'),
            ('ollama', 'ollama', 'Ollama 本地模型'),
        ]

        results = {}
        for import_name, pkg_name, desc in llm_deps:
            try:
                __import__(import_name)
                results[import_name] = (True, f"{desc} ✅")
            except ImportError:
                results[import_name] = (False, f"{desc} ⚠️ 未安装")
                self.suggestions.append(f"如需使用 {desc}，请运行: pip install {pkg_name}")

        return results

    def check_jupyter_dependencies(self) -> Dict[str, Tuple[bool, str]]:
        """检查 Jupyter 相关依赖。"""
        jupyter_deps = [
            ('IPython', 'ipython', 'IPython'),
            ('jupyter', 'jupyter', 'Jupyter'),
        ]

        results = {}
        for import_name, pkg_name, desc in jupyter_deps:
            try:
                __import__(import_name.lower() if import_name == 'IPython' else import_name)
                results[import_name] = (True, f"{desc} ✅")
            except ImportError:
                results[import_name] = (False, f"{desc} ⚠️ 未安装")
                self.suggestions.append(f"如需使用 {desc}，请运行: pip install {pkg_name}")

        return results

    def check_vscode_dependencies(self) -> Dict[str, Tuple[bool, str]]:
        """检查 VS Code 插件相关依赖。"""
        results = {}

        # 检查 Node.js
        try:
            node_version = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if node_version.returncode == 0:
                results['node'] = (True, f"Node.js {node_version.stdout.strip()}")
            else:
                results['node'] = (False, "Node.js 未安装")
                self.suggestions.append("如需构建 VS Code 插件，请安装 Node.js: https://nodejs.org")
        except FileNotFoundError:
            results['node'] = (False, "Node.js 未安装")
            self.suggestions.append("如需构建 VS Code 插件，请安装 Node.js: https://nodejs.org")

        # 检查 npm
        try:
            npm_version = subprocess.run(['npm', '--version'], capture_output=True, text=True)
            if npm_version.returncode == 0:
                results['npm'] = (True, f"npm {npm_version.stdout.strip()}")
            else:
                results['npm'] = (False, "npm 不可用")
        except FileNotFoundError:
            results['npm'] = (False, "npm 未安装")

        # 检查 vsce
        try:
            vsce_version = subprocess.run(['vsce', '--version'], capture_output=True, text=True)
            if vsce_version.returncode == 0:
                results['vsce'] = (True, f"vsce {vsce_version.stdout.strip()}")
            else:
                results['vsce'] = (False, "vsce 未安装")
                self.suggestions.append("如需发布 VS Code 插件，请运行: npm install -g vsce")
        except FileNotFoundError:
            results['vsce'] = (False, "vsce 未安装")
            self.suggestions.append("如需发布 VS Code 插件，请运行: npm install -g vsce")

        return results

    def check_project_structure(self) -> bool:
        """检查项目结构。"""
        required_files = [
            'src/intent/llm_parser.py',
            'src/intent/intent_decomposer.py',
            'src/intent/mir_generator.py',
            'src/stdlib/arithmetic.py',
            'src/stdlib/algebra.py',
            'src/stdlib/calculus.py',
            'src/stdlib/logic.py',
            'src/hardware/hal.py',
            'src/pkg_manager.py',
            'src/jupyter/matha_magic.py',
            'tests/test_llm_parser.py',
            'tests/test_arithmetic.py',
            'tests/test_jupyter_magic.py',
            'extensions/vscode-matha/package.json',
            'extensions/vscode-matha/publish.py',
            'docs/RELEASE_NOTES_v4.3.md',
        ]

        all_exist = True
        for file_path in required_files:
            full_path = Path(file_path)
            if full_path.exists():
                self.results[file_path] = (True, f"✅ {file_path}")
            else:
                self.results[file_path] = (False, f"❌ 缺少 {file_path}")
                self.suggestions.append(f"请确保文件存在: {file_path}")
                all_exist = False

        return all_exist

    def run_checks(self) -> bool:
        """运行所有检查。"""
        print("\n" + "=" * 60)
        print("  Matha v4.3 预检报告")
        print("=" * 60)

        # 1. Python 版本
        print("\n【1. Python 版本】")
        python_ok = self.check_python_version()
        status = "✅" if python_ok else "❌"
        print(f"  {status} {self.results['python'][1]}")

        # 2. 必需依赖
        print("\n【2. 必需依赖】")
        deps_ok = self.check_required_dependencies()
        for module, (ok, desc) in self.results.items():
            if module in ['math', 'multiprocessing', 'queue', 'json', 're', 'hashlib', 'pathlib']:
                status = "✅" if ok else "❌"
                print(f"  {status} {desc}")

        # 3. LLM 依赖
        print("\n【3. LLM 依赖】")
        llm_results = self.check_llm_dependencies()
        for module, (ok, desc) in llm_results.items():
            status = "✅" if ok else "⚠️"
            print(f"  {status} {desc}")

        # 4. Jupyter 依赖
        print("\n【4. Jupyter 依赖】")
        jupyter_results = self.check_jupyter_dependencies()
        for module, (ok, desc) in jupyter_results.items():
            status = "✅" if ok else "⚠️"
            print(f"  {status} {desc}")

        # 5. VS Code 依赖
        print("\n【5. VS Code 插件依赖】")
        vscode_results = self.check_vscode_dependencies()
        for module, (ok, desc) in vscode_results.items():
            status = "✅" if ok else "⚠️"
            print(f"  {status} {desc}")

        # 6. 项目结构
        print("\n【6. 项目结构】")
        structure_ok = self.check_project_structure()
        missing_files = [k for k, v in self.results.items() if not v[0] and k not in ['python', 'math', 'multiprocessing', 'queue', 'json', 're', 'hashlib', 'pathlib']]
        if not missing_files:
            print("  ✅ 所有必需文件存在")
        else:
            print(f"  ⚠️ 缺少 {len(missing_files)} 个文件")

        # 7. 总结
        print("\n" + "=" * 60)
        print("  检查总结")
        print("=" * 60)

        all_ok = python_ok and deps_ok and structure_ok
        if all_ok:
            print("\n  ✅ 所有检查通过！可以运行 Matha v4.3")
        else:
            print("\n  ⚠️ 存在需要修复的问题")

        if self.suggestions:
            print("\n  建议操作:")
            for i, suggestion in enumerate(self.suggestions, 1):
                print(f"    {i}. {suggestion}")

        print("\n" + "=" * 60)

        return all_ok


def main():
    """主入口。"""
    import argparse

    parser = argparse.ArgumentParser(description="Matha v4.3 预检脚本")
    parser.add_argument("--strict", action="store_true", help="严格模式：缺少依赖时退出码为 1")
    args = parser.parse_args()

    checker = PreflightChecker(strict=args.strict)
    result = checker.run_checks()

    if args.strict and not result:
        sys.exit(1)


if __name__ == "__main__":
    main()
