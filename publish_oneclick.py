# -*- coding: utf-8 -*-
"""Matha v4.3 一键发布脚本

功能：
1. 检查 Git 环境
2. 创建 Git 标签
3. 推送标签到远程
4. 创建 GitHub Release
5. 验证发布结果

用法：
  python publish_oneclick.py
  python publish_oneclick.py --dry-run    # 预览模式，不实际执行
  python publish_oneclick.py --version 4.3.1
  python publish_oneclick.py --verbose
"""
import subprocess
import sys
import os
import argparse
import platform
from pathlib import Path
from datetime import datetime
import logging


class PublishScript:
    """一键发布脚本。"""

    def __init__(self, version: str = "4.3.0", dry_run: bool = False, verbose: bool = False):
        self.version = version
        self.dry_run = dry_run
        self.verbose = verbose
        self.project_root = Path(__file__).parent
        self.tag_name = f"v{version}"
        self.release_notes_file = self.project_root / "docs" / "RELEASE_NOTES_v4.3.md"
        self.steps = []

        # 设置日志
        if verbose:
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%H:%M:%S'
            )
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logging.NullHandler()

    def log(self, level: str, message: str):
        """统一日志输出。"""
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)

    def log_step(self, step_num: int, description: str, status: str = "pending"):
        """记录执行步骤。"""
        icon = {
            "pending": "⏳",
            "running": "🔄",
            "success": "✅",
            "failed": "❌",
            "skipped": "⏭️"
        }.get(status, "⏳")
        print(f"  [{step_num:02d}] {icon} {description} ({status})")
        self.steps.append({
            "num": step_num,
            "desc": description,
            "status": status
        })
        self.log("DEBUG", f"Step {step_num}: {description} -> {status}")

    def run_command(self, cmd: str, check: bool = True, description: str = "") -> subprocess.CompletedProcess:
        """运行命令。"""
        self.log("DEBUG", f"运行命令: {description or cmd}")

        if self.verbose:
            print(f"\n$ {cmd}")

        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        if self.verbose and result.stdout:
            print(f"  输出:\n{result.stdout}")
        if result.stderr:
            print(f"  警告: {result.stderr.strip()}")

        self.log("DEBUG", f"命令执行完成: exit code {result.returncode}")

        if check and result.returncode != 0:
            raise RuntimeError(f"命令失败 (exit code {result.returncode}): {cmd}")

        return result

    def check_git(self) -> bool:
        """检查 Git 是否已安装。"""
        self.log("DEBUG", "检查 Git 是否安装")
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True)
            self.log("DEBUG", f"Git 检查: returncode={result.returncode}")
            if result.returncode == 0:
                self.log("DEBUG", f"Git 版本: {result.stdout.strip()}")
            return result.returncode == 0
        except FileNotFoundError as e:
            self.log("WARNING", f"Git 未找到: {e}")
            return False
        except Exception as e:
            self.log("ERROR", f"Git 检查出错: {e}")
            return False

    def check_gh(self) -> bool:
        """检查 GitHub CLI 是否已安装。"""
        self.log("DEBUG", "检查 GitHub CLI 是否安装")
        try:
            result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
            self.log("DEBUG", f"gh 检查: returncode={result.returncode}")
            if result.returncode == 0:
                self.log("DEBUG", f"gh 版本: {result.stdout.strip()}")
            return result.returncode == 0
        except FileNotFoundError as e:
            self.log("WARNING", f"GitHub CLI 未找到: {e}")
            return False
        except Exception as e:
            self.log("ERROR", f"gh 检查出错: {e}")
            return False

    def check_prerequisites(self) -> bool:
        """检查前置条件。"""
        mode = "预览模式 (Dry Run)" if self.dry_run else "执行模式"
        print("\n" + "=" * 60)
        print("  Matha v4.3 一键发布脚本")
        print("=" * 60)
        print(f"\n版本: {self.tag_name}")
        print(f"模式: {mode}")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"系统: {platform.system()} {platform.release()}")
        print(f"项目目录: {self.project_root}")
        self.log("DEBUG", f"项目目录: {self.project_root}")

        # 检查 Git
        print("\n【步骤 01】检查前置条件")
        git_ok = self.check_git()
        if git_ok:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True)
            print(f"  ✅ Git: {result.stdout.strip()}")
            self.log("DEBUG", f"Git 已安装: {result.stdout.strip()}")
        else:
            print(f"  ❌ Git 未安装")
            print(f"  💡 请安装 Git: https://git-scm.com/downloads")
            print(f"  💡 或运行: python install_tools.py --git")
            print(f"  💡 Windows 推荐使用: scoop install git")
            print(f"  💡 macOS 推荐使用: brew install git")
            print(f"  💡 Linux 推荐使用: sudo apt-get install git")
            self.log("WARNING", "Git 未安装")

        # 检查 gh CLI
        gh_ok = self.check_gh()
        if gh_ok:
            result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
            print(f"  ✅ GitHub CLI: {result.stdout.strip().split(chr(10))[0]}")
            self.log("DEBUG", f"GitHub CLI 已安装")
        else:
            print(f"  ⚠️  GitHub CLI 未安装（将跳过 Release 创建）")
            print(f"  💡 请安装: https://cli.github.com")
            print(f"  💡 或运行: python install_tools.py --gh")
            print(f"  💡 Windows 推荐使用: scoop install gh")
            print(f"  💡 macOS 推荐使用: brew install gh")
            print(f"  💡 Linux 推荐使用: sudo apt-get install gh")
            self.log("WARNING", "GitHub CLI 未安装（将跳过 Release 创建）")

        # 检查 Release Notes
        notes_ok = self.release_notes_file.exists()
        if notes_ok:
            size_kb = self.release_notes_file.stat().st_size / 1024
            print(f"  ✅ 发布说明: {self.release_notes_file.name} ({size_kb:.1f} KB)")
            self.log("DEBUG", f"发布说明文件存在: {size_kb:.1f} KB")
        else:
            print(f"  ❌ 发布说明文件不存在: {self.release_notes_file}")
            self.log("ERROR", f"发布说明文件不存在: {self.release_notes_file}")

        # 检查必要条件
        if not git_ok:
            print("\n  ❌ 缺少必要工具: Git")
            print("  💡 请先安装 Git 后重新运行此脚本")
            print("  💡 运行: python install_tools.py --git")
            self.log("ERROR", "缺少必要工具: Git")
            return False

        if not notes_ok:
            print("\n  ❌ 缺少必要文件: 发布说明")
            self.log("ERROR", "缺少必要文件: 发布说明")
            return False

        print("\n  ✅ 前置条件检查通过")
        self.log("INFO", "前置条件检查通过")
        return True

    def create_tag(self) -> bool:
        """创建 Git 标签。"""
        self.log("INFO", f"开始创建 Git 标签: {self.tag_name}")
        self.log_step(2, f"创建 Git 标签: {self.tag_name}")

        if self.dry_run:
            print(f"  [预览] 将执行: git tag -a {self.tag_name} -m \"Matha {self.version}: ...\"")
            print(f"  [预览] 标签内容: Matha {self.version}: VS Code 插件 + Jupyter 集成 + 包管理器")
            self.log("DEBUG", f"[预览] 将执行: git tag -a {self.tag_name} -m \"Matha {self.version}: ...\"")
            self.log_step(2, f"创建 Git 标签: {self.tag_name}", "success")
            return True

        try:
            # 检查标签是否已存在
            result = subprocess.run(
                ["git", "tag", "-l", self.tag_name],
                capture_output=True, text=True
            )
            self.log("DEBUG", f"检查标签是否存在: exit code {result.returncode}")
            if result.stdout.strip():
                print(f"  ⚠️  标签已存在: {self.tag_name}")
                self.log("WARNING", f"标签已存在: {self.tag_name}")
                self.log_step(2, f"创建 Git 标签: {self.tag_name}", "skipped")
                return True

            # 创建标签
            msg = f"Matha {self.version}: VS Code 插件 + Jupyter 集成 + 包管理器"
            self.run_command(
                f'git tag -a {self.tag_name} -m "{msg}"',
                description=f"创建标签 {self.tag_name}"
            )
            print(f"  ✅ 标签创建成功: {self.tag_name}")
            self.log("INFO", f"标签创建成功: {self.tag_name}")
            self.log_step(2, f"创建 Git 标签: {self.tag_name}", "success")
            return True

        except Exception as e:
            print(f"  ❌ 标签创建失败: {e}")
            self.log("ERROR", f"标签创建失败: {e}")
            self.log_step(2, f"创建 Git 标签: {self.tag_name}", "failed")
            return False

    def push_tag(self) -> bool:
        """推送标签到远程。"""
        self.log("INFO", f"开始推送标签到远程: {self.tag_name}")
        self.log_step(3, "推送标签到远程")

        if self.dry_run:
            print(f"  [预览] 将执行: git push origin {self.tag_name}")
            print(f"  [预览] 远程仓库: origin")
            self.log("DEBUG", f"[预览] 将执行: git push origin {self.tag_name}")
            self.log_step(3, "推送标签到远程", "success")
            return True

        try:
            self.run_command(
                f"git push origin {self.tag_name}",
                description=f"推送标签 {self.tag_name}"
            )
            print(f"  ✅ 标签推送成功")
            self.log("INFO", f"标签推送成功: {self.tag_name}")
            self.log_step(3, "推送标签到远程", "success")
            return True
        except Exception as e:
            print(f"  ❌ 标签推送失败: {e}")
            self.log("ERROR", f"标签推送失败: {e}")
            self.log_step(3, "推送标签到远程", "failed")
            return False

    def create_github_release(self) -> bool:
        """创建 GitHub Release。"""
        self.log("INFO", f"开始创建 GitHub Release: {self.tag_name}")
        self.log_step(4, "创建 GitHub Release")

        if self.dry_run:
            print(f"  [预览] 将执行:")
            print(f"    gh release create {self.tag_name} \\")
            print(f"      --title \"Matha {self.version}\" \\")
            print(f"      --notes-file docs/RELEASE_NOTES_v4.3.md")
            print(f"  [预览] Release URL: https://github.com/your-org/matha/releases/tag/{self.tag_name}")
            self.log("DEBUG", "[预览] 将执行 gh release create")

            # 检查 gh CLI
            if self.check_gh():
                self.log("INFO", "GitHub CLI 已安装，Release 创建将执行")
                self.log_step(4, "创建 GitHub Release", "success")
                return True
            else:
                print(f"  ⚠️  GitHub CLI 未安装，跳过 Release 创建")
                self.log("WARNING", "GitHub CLI 未安装，跳过 Release 创建")
                self.log_step(4, "创建 GitHub Release", "skipped")
                return False

        # 检查 gh CLI
        gh_ok = self.check_gh()

        if not gh_ok:
            print(f"  ⚠️  GitHub CLI 未安装，跳过 Release 创建")
            print(f"  💡 请手动执行:")
            print(f'    gh release create {self.tag_name} --title "Matha {self.version}" --notes-file docs/RELEASE_NOTES_v4.3.md')
            self.log("WARNING", "GitHub CLI 未安装，跳过 Release 创建")
            self.log_step(4, "创建 GitHub Release", "skipped")
            return False

        if not self.release_notes_file.exists():
            print(f"  ❌ 发布说明文件不存在: {self.release_notes_file}")
            self.log("ERROR", f"发布说明文件不存在: {self.release_notes_file}")
            self.log_step(4, "创建 GitHub Release", "failed")
            return False

        try:
            self.run_command(
                f'gh release create {self.tag_name} --title "Matha {self.version}" --notes-file "{self.release_notes_file}"',
                description=f"创建 Release {self.tag_name}"
            )
            print(f"  ✅ Release 创建成功")
            print(f"  🔗 Release URL: https://github.com/your-org/matha/releases/tag/{self.tag_name}")
            self.log("INFO", f"Release 创建成功: {self.tag_name}")
            self.log_step(4, "创建 GitHub Release", "success")
            return True
        except Exception as e:
            print(f"  ❌ Release 创建失败: {e}")
            self.log("ERROR", f"Release 创建失败: {e}")
            self.log_step(4, "创建 GitHub Release", "failed")
            return False

    def generate_summary(self) -> str:
        """生成发布摘要。"""
        mode = "预览" if self.dry_run else "正式"
        summary_lines = [
            "\n" + "=" * 60,
            f"  Matha v{self.version} 发布完成",
            "=" * 60,
            "",
            f"版本: {self.tag_name}",
            f"日期: {datetime.now().strftime('%Y-%m-%d')}",
            f"模式: {mode}",
            "",
            "已完成的步骤:",
        ]

        for step in self.steps:
            icon = {"pending": "⏳", "running": "🔄", "success": "✅", "failed": "❌", "skipped": "⏭️"}.get(step["status"], "⏳")
            summary_lines.append(f"  {icon} [{step['num']:02d}] {step['desc']}")

        summary_lines.extend([
            "",
            "下一步:",
            "  1. 查看 Release: https://github.com/your-org/matha/releases/tag/" + self.tag_name,
            "  2. 发布 VS Code 插件: cd extensions/vscode-matha && python publish.py --publish both",
            "  3. 通知用户: 通过邮件/社交媒体发布更新公告",
            "",
            "=" * 60,
        ])

        self.log("INFO", "生成发布摘要完成")
        return "\n".join(summary_lines)

    def run(self) -> bool:
        """执行发布流程。"""
        self.log("INFO", "开始执行发布流程")

        # 1. 检查前置条件
        self.log("INFO", "步骤 1: 检查前置条件")
        if not self.check_prerequisites():
            self.log("ERROR", "前置条件检查失败")
            print("\n❌ 前置条件检查失败，请修复后重试")
            return False

        # 2. 创建标签
        self.log("INFO", "步骤 2: 创建 Git 标签")
        if not self.create_tag():
            self.log("ERROR", "标签创建失败")
            print("\n❌ 标签创建失败")
            return False

        # 3. 推送标签
        self.log("INFO", "步骤 3: 推送标签到远程")
        if not self.push_tag():
            self.log("ERROR", "标签推送失败")
            print("\n❌ 标签推送失败")
            return False

        # 4. 创建 Release
        self.log("INFO", "步骤 4: 创建 GitHub Release")
        self.create_github_release()

        # 5. 生成摘要
        self.log("INFO", "步骤 5: 生成发布摘要")
        summary = self.generate_summary()
        print(summary)

        self.log("INFO", "发布流程执行完成")
        return True


def main():
    """主入口。"""
    parser = argparse.ArgumentParser(
        description="Matha v4.3 一键发布脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python publish_oneclick.py              # 执行发布
  python publish_oneclick.py --dry-run    # 预览模式
  python publish_oneclick.py --verbose    # 详细日志
  python publish_oneclick.py --version 4.3.1  # 指定版本
        """
    )
    parser.add_argument("--version", default="4.3.0", help="版本号（默认: 4.3.0）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际执行")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志输出")
    args = parser.parse_args()

    script = PublishScript(
        version=args.version,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    result = script.run()

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
