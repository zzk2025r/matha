# -*- coding: utf-8 -*-
"""Matha 环境安装脚本

功能：
1. 自动检测操作系统
2. 安装 Git（如未安装）
3. 安装 GitHub CLI（如未安装）
4. 验证安装结果
5. 提供手动安装指引

用法：
  python install_tools.py
  python install_tools.py --git      # 仅安装 Git
  python install_tools.py --gh       # 仅安装 GitHub CLI
  python install_tools.py --all      # 安装所有工具
"""
import subprocess
import sys
import platform
import os
from pathlib import Path


class ToolInstaller:
    """工具安装器。"""

    def __init__(self):
        self.os_name = platform.system().lower()
        self.results = {}

    def run_command(self, cmd: str, check: bool = True) -> subprocess.CompletedProcess:
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

    def check_installed(self, command: str) -> bool:
        """检查命令是否已安装。"""
        try:
            result = subprocess.run(
                [command, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def install_git_windows(self) -> bool:
        """Windows 安装 Git。"""
        print("\n【Windows】安装 Git")
        print("  方式 1: 使用 Scoop（推荐）")
        print("    scoop install git")
        print("\n  方式 2: 使用 Chocolatey")
        print("    choco install git")
        print("\n  方式 3: 手动下载")
        print("    https://git-scm.com/download/win")
        print("\n  ⚠️  自动安装 Git 需要管理员权限或使用包管理器")
        print("  💡 请手动安装后重新运行此脚本")
        return False

    def install_git_macos(self) -> bool:
        """macOS 安装 Git。"""
        print("\n【macOS】安装 Git")

        # 检查 Homebrew
        if self.check_installed("brew"):
            print("  使用 Homebrew 安装...")
            result = self.run_command("brew install git")
            if result.returncode == 0:
                print("  ✅ Git 安装成功")
                return True
        else:
            print("  未找到 Homebrew，请手动安装:")
            print("    /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
            print("    brew install git")

        return False

    def install_git_linux(self) -> bool:
        """Linux 安装 Git。"""
        print("\n【Linux】安装 Git")

        # 检测发行版
        if "ubuntu" in self.os_name or "debian" in self.os_name:
            print("  使用 apt 安装...")
            result = self.run_command("sudo apt-get update && sudo apt-get install -y git")
            if result.returncode == 0:
                print("  ✅ Git 安装成功")
                return True
        elif "centos" in self.os_name or "rhel" in self.os_name or "fedora" in self.os_name:
            print("  使用 yum/dnf 安装...")
            result = self.run_command("sudo dnf install -y git || sudo yum install -y git")
            if result.returncode == 0:
                print("  ✅ Git 安装成功")
                return True
        elif "arch" in self.os_name:
            print("  使用 pacman 安装...")
            result = self.run_command("sudo pacman -S git")
            if result.returncode == 0:
                print("  ✅ Git 安装成功")
                return True
        else:
            print("  请根据您的发行版手动安装:")
            print("    https://git-scm.com/download/linux")

        return False

    def install_git(self) -> bool:
        """安装 Git。"""
        print("\n" + "=" * 60)
        print("  安装 Git")
        print("=" * 60)

        if self.check_installed("git"):
            result = subprocess.run(["git", "--version"], capture_output=True, text=True)
            print(f"  ✅ Git 已安装: {result.stdout.strip()}")
            self.results['git'] = True
            return True

        print(f"  ⚠️  Git 未安装")
        print(f"  系统: {self.os_name.capitalize()}")

        if self.os_name == "windows":
            return self.install_git_windows()
        elif self.os_name == "darwin":
            return self.install_git_macos()
        elif self.os_name == "linux":
            return self.install_git_linux()
        else:
            print(f"  💡 请访问: https://git-scm.com/downloads")
            return False

    def install_gh_windows(self) -> bool:
        """Windows 安装 GitHub CLI。"""
        print("\n【Windows】安装 GitHub CLI")
        print("  方式 1: 使用 Scoop（推荐）")
        print("    scoop install gh")
        print("\n  方式 2: 使用 Chocolatey")
        print("    choco install gh")
        print("\n  方式 3: 手动下载")
        print("    https://github.com/cli/cli/releases")
        print("\n  ⚠️  自动安装需要管理员权限或使用包管理器")
        return False

    def install_gh_macos(self) -> bool:
        """macOS 安装 GitHub CLI。"""
        print("\n【macOS】安装 GitHub CLI")

        if self.check_installed("brew"):
            print("  使用 Homebrew 安装...")
            result = self.run_command("brew install gh")
            if result.returncode == 0:
                print("  ✅ GitHub CLI 安装成功")
                return True
        else:
            print("  未找到 Homebrew")

        return False

    def install_gh_linux(self) -> bool:
        """Linux 安装 GitHub CLI。"""
        print("\n【Linux】安装 GitHub CLI")

        # 检测包管理器
        if "ubuntu" in self.os_name or "debian" in self.os_name:
            print("  使用 apt 安装...")
            result = self.run_command("""
                (curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg) &&
                sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg &&
                echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null &&
                sudo apt update &&
                sudo apt install gh -y
            """)
            if result.returncode == 0:
                print("  ✅ GitHub CLI 安装成功")
                return True
        elif "centos" in self.os_name or "rhel" in self.os_name or "fedora" in self.os_name:
            print("  使用 dnf 安装...")
            result = self.run_command("""
                sudo dnf install 'dnf-command(curl)' -y &&
                sudo dnf install https://github.com/cli/cli/releases/download/v2.42.1/gh_2.42.1_linux_amd64.rpm -y
            """)
            if result.returncode == 0:
                print("  ✅ GitHub CLI 安装成功")
                return True
        elif "arch" in self.os_name:
            print("  使用 pacman 安装...")
            result = self.run_command("sudo pacman -S gh")
            if result.returncode == 0:
                print("  ✅ GitHub CLI 安装成功")
                return True
        else:
            print("  请访问: https://github.com/cli/cli#installation")

        return False

    def install_gh(self) -> bool:
        """安装 GitHub CLI。"""
        print("\n" + "=" * 60)
        print("  安装 GitHub CLI")
        print("=" * 60)

        if self.check_installed("gh"):
            result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
            print(f"  ✅ GitHub CLI 已安装: {result.stdout.strip().split(chr(10))[0]}")
            self.results['gh'] = True
            return True

        print(f"  ⚠️  GitHub CLI 未安装")
        print(f"  系统: {self.os_name.capitalize()}")

        if self.os_name == "windows":
            return self.install_gh_windows()
        elif self.os_name == "darwin":
            return self.install_gh_macos()
        elif self.os_name == "linux":
            return self.install_gh_linux()
        else:
            print(f"  💡 请访问: https://github.com/cli/cli#installation")
            return False

    def verify_installation(self) -> bool:
        """验证安装结果。"""
        print("\n" + "=" * 60)
        print("  验证安装")
        print("=" * 60)

        all_ok = True

        # 验证 Git
        if self.check_installed("git"):
            result = subprocess.run(["git", "--version"], capture_output=True, text=True)
            print(f"  ✅ Git: {result.stdout.strip()}")
            self.results['git'] = True
        else:
            print(f"  ❌ Git: 未安装")
            self.results['git'] = False
            all_ok = False

        # 验证 gh CLI
        if self.check_installed("gh"):
            result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
            print(f"  ✅ GitHub CLI: {result.stdout.strip().split(chr(10))[0]}")
            self.results['gh'] = True
        else:
            print(f"  ❌ GitHub CLI: 未安装")
            self.results['gh'] = False
            all_ok = False

        return all_ok

    def run(self, target: str = "all") -> bool:
        """运行安装流程。"""
        print("\n" + "=" * 60)
        print("  Matha 环境安装脚本")
        print("=" * 60)
        print(f"系统: {platform.system()} {platform.release()}")
        print(f"架构: {platform.machine()}")
        print(f"Python: {sys.version.split()[0]}")

        if target in ("all", "git"):
            self.install_git()

        if target in ("all", "gh"):
            self.install_gh()

        # 验证
        ok = self.verify_installation()

        # 总结
        print("\n" + "=" * 60)
        print("  安装总结")
        print("=" * 60)

        if ok:
            print("\n  ✅ 所有工具安装成功！")
            print("\n  下一步:")
            print("    1. 配置 Git 用户信息:")
            print("       git config --global user.name \"Your Name\"")
            print("       git config --global user.email \"your@email.com\"")
            print("    2. 登录 GitHub CLI:")
            print("       gh auth login")
            print("    3. 执行发布:")
            print("       python publish_oneclick.py")
        else:
            print("\n  ⚠️  部分工具安装失败")
            print("\n  请手动安装后重新运行此脚本")

        print("\n" + "=" * 60)

        return ok


def main():
    """主入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Matha 环境安装脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python install_tools.py              # 安装所有工具
  python install_tools.py --git        # 仅安装 Git
  python install_tools.py --gh         # 仅安装 GitHub CLI
  python install_tools.py --verify     # 仅验证安装
        """
    )
    parser.add_argument("--git", action="store_true", help="仅安装 Git")
    parser.add_argument("--gh", action="store_true", help="仅安装 GitHub CLI")
    parser.add_argument("--verify", action="store_true", help="仅验证安装")
    args = parser.parse_args()

    installer = ToolInstaller()

    if args.verify:
        ok = installer.verify_installation()
    else:
        target = "all"
        if args.git:
            target = "git"
        elif args.gh:
            target = "gh"
        ok = installer.run(target=target)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
