# -*- coding: utf-8 -*-
"""Matha Git 环境检查脚本

功能：
1. 检测 Git 是否已安装
2. 检测 Git 版本
3. 检测 GitHub CLI (gh) 是否已安装
4. 提供安装步骤提示
5. 验证 Git 配置（用户名、邮箱）

用法：
  python check_git.py
  python check_git.py --install    # 显示安装命令
  python check_git.py --verbose    # 详细输出
"""
import subprocess
import sys
import os
import platform
from pathlib import Path


class GitChecker:
    """Git 环境检查器。"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {}
        self.install_commands = {}

    def check_git_installed(self) -> bool:
        """检查 Git 是否已安装。"""
        print("\n【1. 检查 Git】")

        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"  ✅ Git 已安装: {version}")
                self.results['git'] = True
                self.install_commands['git'] = None
                return True
            else:
                print(f"  ❌ Git 未安装或命令失败")
                self.results['git'] = False
                self._provide_install_instructions('git')
                return False
        except FileNotFoundError:
            print(f"  ❌ Git 未安装")
            self.results['git'] = False
            self._provide_install_instructions('git')
            return False
        except Exception as e:
            print(f"  ⚠️  检查 Git 时出错: {e}")
            self.results['git'] = False
            return False

    def check_gh_installed(self) -> bool:
        """检查 GitHub CLI 是否已安装。"""
        print("\n【2. 检查 GitHub CLI (gh)】")

        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                print(f"  ✅ GitHub CLI 已安装: {version}")
                self.results['gh'] = True
                self.install_commands['gh'] = None
                return True
            else:
                print(f"  ❌ GitHub CLI 未安装或命令失败")
                self.results['gh'] = False
                self._provide_install_instructions('gh')
                return False
        except FileNotFoundError:
            print(f"  ❌ GitHub CLI 未安装")
            self.results['gh'] = False
            self._provide_install_instructions('gh')
            return False
        except Exception as e:
            print(f"  ⚠️  检查 GitHub CLI 时出错: {e}")
            self.results['gh'] = False
            return False

    def check_git_config(self) -> bool:
        """检查 Git 配置。"""
        print("\n【3. 检查 Git 配置】")

        if not self.results.get('git'):
            print("  ⏭️  跳过（Git 未安装）")
            return False

        config_ok = True

        # 检查用户名
        result = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            name = result.stdout.strip()
            print(f"  ✅ Git 用户名: {name}")
        else:
            print(f"  ⚠️  Git 用户名未配置")
            config_ok = False

        # 检查邮箱
        result = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            email = result.stdout.strip()
            print(f"  ✅ Git 邮箱: {email}")
        else:
            print(f"  ⚠️  Git 邮箱未配置")
            config_ok = False

        self.results['git_config'] = config_ok
        return config_ok

    def check_git_repo(self) -> bool:
        """检查是否为 Git 仓库。"""
        print("\n【4. 检查 Git 仓库】")

        if not self.results.get('git'):
            print("  ⏭️  跳过（Git 未安装）")
            return False

        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )
        if result.returncode == 0 and result.stdout.strip() == "true":
            print(f"  ✅ 当前目录是 Git 仓库")
            self.results['is_repo'] = True

            # 检查远程仓库
            result = subprocess.run(
                ["git", "remote", "-v"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                print(f"  ✅ 已配置远程仓库")
                self.results['has_remote'] = True
            else:
                print(f"  ⚠️  未配置远程仓库")
                self.results['has_remote'] = False
            return True
        else:
            print(f"  ⚠️  当前目录不是 Git 仓库")
            self.results['is_repo'] = False
            return False

    def check_git_status(self) -> bool:
        """检查 Git 状态。"""
        print("\n【5. 检查 Git 状态】")

        if not self.results.get('git'):
            print("  ⏭️  跳过（Git 未安装）")
            return False

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )
        if result.returncode == 0:
            changes = result.stdout.strip()
            if changes:
                print(f"  ⚠️  有未提交的更改")
                print(f"     变更文件数: {len(changes.splitlines())}")
                self.results['has_changes'] = True
            else:
                print(f"  ✅ 工作区干净")
                self.results['has_changes'] = False
            return True
        else:
            print(f"  ⚠️  检查 Git 状态时出错")
            return False

    def _provide_install_instructions(self, tool: str):
        """提供安装指令。"""
        print(f"\n  💡 安装 {tool} 的步骤:")
        print(f"  {'='*50}")

        os_name = platform.system().lower()

        if tool == 'git':
            if os_name == 'windows':
                print("""
  Windows:
    1. 下载 Git for Windows: https://git-scm.com/download/win
    2. 运行安装程序，使用默认设置
    3. 重启终端，验证安装:
       git --version
  """)
            elif os_name == 'darwin':  # macOS
                print("""
  macOS:
    方法 1: 使用 Homebrew
      brew install git

    方法 2: 下载安装包
      https://git-scm.com/download/mac
  """)
            elif os_name == 'linux':
                print("""
  Linux:
    Ubuntu/Debian:
      sudo apt-get install git

    CentOS/RHEL:
      sudo yum install git

    Arch Linux:
      sudo pacman -S git
  """)
            else:
                print(f"""
  {os_name.capitalize()}:
    请访问: https://git-scm.com/downloads
  """)

        elif tool == 'gh':
            if os_name == 'windows':
                print("""
  Windows:
    方法 1: 使用 Scoop
      scoop install gh

    方法 2: 使用 Chocolatey
      choco install gh

    方法 3: 下载安装包
      https://github.com/cli/cli/releases
  """)
            elif os_name == 'darwin':
                print("""
  macOS:
    使用 Homebrew:
      brew install gh
  """)
            elif os_name == 'linux':
                print("""
  Linux:
    Ubuntu/Debian:
      sudo apt-get install gh

    其他发行版:
      https://github.com/cli/cli#installation
  """)
            else:
                print(f"""
  {os_name.capitalize()}:
    请访问: https://cli.github.com
  """)

        print(f"  {'='*50}")
        self.install_commands[tool] = self._get_install_command(tool, os_name)

    def _get_install_command(self, tool: str, os_name: str) -> str:
        """获取安装命令。"""
        commands = {
            'git': {
                'windows': 'https://git-scm.com/download/win',
                'darwin': 'brew install git',
                'linux': 'sudo apt-get install git'
            },
            'gh': {
                'windows': 'scoop install gh',
                'darwin': 'brew install gh',
                'linux': 'sudo apt-get install gh'
            }
        }
        return commands.get(tool, {}).get(os_name, f'请访问 {tool} 官网')

    def run_checks(self) -> bool:
        """运行所有检查。"""
        print("\n" + "=" * 60)
        print("  Matha Git 环境检查")
        print("=" * 60)
        print(f"系统: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version.split()[0]}")

        # 运行检查
        git_ok = self.check_git_installed()
        gh_ok = self.check_gh_installed()
        config_ok = self.check_git_config() if git_ok else False
        repo_ok = self.check_git_repo() if git_ok else False
        status_ok = self.check_git_status() if git_ok else False

        # 总结
        print("\n" + "=" * 60)
        print("  检查总结")
        print("=" * 60)

        checks = [
            ("Git 安装", git_ok),
            ("GitHub CLI", gh_ok),
            ("Git 配置", config_ok),
            ("Git 仓库", repo_ok),
            ("工作区状态", status_ok),
        ]

        all_ok = True
        for name, ok in checks:
            status = "✅" if ok else "❌"
            print(f"  {status} {name}")
            if not ok:
                all_ok = False

        print("\n" + "=" * 60)

        if all_ok:
            print("  ✅ 所有检查通过！可以执行发布命令。")
        else:
            print("  ⚠️  存在需要修复的问题")
            print("\n  建议操作:")
            if not self.results.get('git'):
                print("    1. 安装 Git（见上方安装步骤）")
            if not self.results.get('gh'):
                print("    2. 安装 GitHub CLI（见上方安装步骤）")
            if self.results.get('git') and not config_ok:
                print("    3. 配置 Git 用户信息:")
                print("       git config --global user.name \"Your Name\"")
                print("       git config --global user.email \"your@email.com\"")

        print("=" * 60)

        return all_ok


def main():
    """主入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Matha Git 环境检查脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python check_git.py              # 运行检查
  python check_git.py --verbose    # 详细输出
        """
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    checker = GitChecker(verbose=args.verbose)
    result = checker.run_checks()

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
