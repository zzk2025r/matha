# -*- coding: utf-8 -*-
"""Matha v4.3 一键发布脚本

功能：
1. 检查前置条件（Git、gh CLI）
2. 创建 Git 标签
3. 推送标签到远程
4. 创建 GitHub Release
5. 生成发布说明

用法：
  python release_oneclick.py
  python release_oneclick.py --version 4.3.1
  python release_oneclick.py --verbose
"""
import subprocess
import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime


# ============================================================
# 日志配置
# ============================================================

def setup_logging(verbose: bool = False):
    """配置日志输出。"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    return logging.getLogger("matha.release")


logger = setup_logging()


class ReleaseScript:
    """一键发布脚本。"""

    def __init__(self, version: str = "4.3.0", dry_run: bool = False, verbose: bool = False):
        self.version = version
        self.dry_run = dry_run
        self.verbose = verbose
        self.project_root = Path(__file__).parent
        self.tag_name = f"v{version}"
        self.release_notes_file = self.project_root / "docs" / "RELEASE_NOTES_v4.3.md"
        self.steps = []  # 记录执行步骤

    def log_step(self, step_num: int, description: str, status: str = "pending"):
        """记录执行步骤。"""
        icon = {
            "pending": "⏳",
            "running": "🔄",
            "success": "✅",
            "failed": "❌",
            "skipped": "⏭️"
        }.get(status, "⏳")
        logger.info(f"  [{step_num:02d}] {icon} {description} ({status})")
        self.steps.append({
            "num": step_num,
            "desc": description,
            "status": status
        })

    def run_command(self, cmd: str, check: bool = True, description: str = "") -> subprocess.CompletedProcess:
        """运行命令。"""
        if self.verbose:
            logger.debug(f"\n$ {cmd}")
        else:
            logger.info(f"  执行: {description or cmd}")

        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        if self.verbose and result.stdout:
            logger.debug(f"  输出:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"  警告: {result.stderr.strip()}")

        if check and result.returncode != 0:
            raise RuntimeError(f"命令失败 (exit code {result.returncode}): {cmd}")

        return result

    def check_prerequisites(self, log: logging.Logger) -> bool:
        """检查前置条件。"""
        log.info("\n" + "=" * 60)
        log.info("  Matha v4.3 一键发布脚本")
        log.info("=" * 60)
        log.info(f"\n版本: {self.tag_name}")
        log.info(f"模式: 执行模式")
        log.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 检查 Git
        log.info("\n【步骤 01】检查前置条件")
        git_ok = False
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                git_version = result.stdout.strip()
                log.info(f"  ✅ Git: {git_version}")
                git_ok = True
            else:
                log.info(f"  ❌ Git 未安装")
        except FileNotFoundError:
            log.info(f"  ❌ Git 未安装")
            log.info(f"  💡 请安装 Git: https://git-scm.com/downloads")

        # 检查 gh CLI
        gh_ok = False
        try:
            result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                gh_version = result.stdout.strip().split('\n')[0]
                log.info(f"  ✅ GitHub CLI: {gh_version}")
                gh_ok = True
            else:
                log.info(f"  ⚠️  GitHub CLI 未安装（将跳过 Release 创建）")
        except FileNotFoundError:
            log.info(f"  ⚠️  GitHub CLI 未安装（将跳过 Release 创建）")
            log.info(f"  💡 请安装 gh: https://cli.github.com")

        # 检查 Release Notes
        notes_ok = self.release_notes_file.exists()
        if notes_ok:
            size_kb = self.release_notes_file.stat().st_size / 1024
            log.info(f"  ✅ 发布说明: {self.release_notes_file.name} ({size_kb:.1f} KB)")
        else:
            log.info(f"  ⚠️  发布说明文件不存在: {self.release_notes_file}")
            log.info(f"  💡 请先创建发布说明: docs/RELEASE_NOTES_v4.3.md")

        all_ok = git_ok and notes_ok
        if all_ok:
            log.info("\n  ✅ 前置条件检查通过")
        else:
            log.info("\n  ⚠️  前置条件检查失败，请修复后重试")

        return all_ok

    def create_tag(self, log: logging.Logger) -> bool:
        """创建 Git 标签。"""
        self.log_step(2, f"创建 Git 标签: {self.tag_name}")

        try:
            # 检查标签是否已存在
            result = subprocess.run(
                ["git", "tag", "-l", self.tag_name],
                capture_output=True, text=True
            )
            if result.stdout.strip():
                log.info(f"  ⚠️  标签已存在: {self.tag_name}")
                self.log_step(2, f"创建 Git 标签: {self.tag_name}", "skipped")
                return True

            # 创建标签
            msg = f"Matha {self.version}: VS Code 插件 + Jupyter 集成 + 包管理器"
            self.run_command(
                f'git tag -a {self.tag_name} -m "{msg}"',
                description=f"创建标签 {self.tag_name}"
            )
            log.info(f"  ✅ 标签创建成功: {self.tag_name}")
            self.log_step(2, f"创建 Git 标签: {self.tag_name}", "success")
            return True

        except Exception as e:
            log.info(f"  ❌ 标签创建失败: {e}")
            self.log_step(2, f"创建 Git 标签: {self.tag_name}", "failed")
            return False

    def push_tag(self, log: logging.Logger) -> bool:
        """推送标签到远程。"""
        self.log_step(3, "推送标签到远程")

        if self.dry_run:
            log.info(f"  [预览] 将执行: git push origin {self.tag_name}")
            log.info(f"  [预览] 远程仓库: origin")
            self.log_step(3, "推送标签到远程", "success")
            return True

        try:
            self.run_command(
                f"git push origin {self.tag_name}",
                description=f"推送标签 {self.tag_name}"
            )
            log.info(f"  ✅ 标签推送成功")
            self.log_step(3, "推送标签到远程", "success")
            return True
        except Exception as e:
            log.info(f"  ❌ 标签推送失败: {e}")
            self.log_step(3, "推送标签到远程", "failed")
            return False

    def create_github_release(self, log: logging.Logger) -> bool:
        """创建 GitHub Release。"""
        self.log_step(4, "创建 GitHub Release")

        # 检查 gh CLI
        try:
            subprocess.run(["gh", "--version"], capture_output=True)
        except FileNotFoundError:
            log.info(f"  ⚠️  GitHub CLI 未安装，跳过 Release 创建")
            log.info(f"  💡 请手动执行:")
            log.info(f'    gh release create {self.tag_name} --title "Matha {self.version}" --notes-file docs/RELEASE_NOTES_v4.3.md')
            self.log_step(4, "创建 GitHub Release", "skipped")
            return False

        if not self.release_notes_file.exists():
            log.info(f"  ❌ 发布说明文件不存在: {self.release_notes_file}")
            self.log_step(4, "创建 GitHub Release", "failed")
            return False

        try:
            self.run_command(
                f'gh release create {self.tag_name} --title "Matha {self.version}" --notes-file "{self.release_notes_file}"',
                description=f"创建 Release {self.tag_name}"
            )
            log.info(f"  ✅ Release 创建成功")
            log.info(f"  🔗 Release URL: https://github.com/your-org/matha/releases/tag/{self.tag_name}")
            self.log_step(4, "创建 GitHub Release", "success")
            return True
        except Exception as e:
            log.info(f"  ❌ Release 创建失败: {e}")
            self.log_step(4, "创建 GitHub Release", "failed")
            return False

    def generate_release_summary(self, log: logging.Logger) -> str:
        """生成发布摘要。"""
        summary_lines = [
            "\n" + "=" * 60,
            f"  Matha v{self.version} 发布完成",
            "=" * 60,
            "",
            f"版本: {self.tag_name}",
            f"日期: {datetime.now().strftime('%Y-%m-%d')}",
            f"模式: {'预览' if self.dry_run else '正式'}",
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

        return "\n".join(summary_lines)

    def run(self) -> bool:
        """执行发布流程。"""
        log = logger

        # 1. 检查前置条件
        if not self.check_prerequisites(log):
            log.info("\n❌ 前置条件检查失败，请安装 Git 和 GitHub CLI")
            return False

        # 2. 创建标签
        if not self.create_tag(log):
            log.info("\n❌ 标签创建失败")
            return False

        # 3. 推送标签
        if not self.push_tag(log):
            log.info("\n❌ 标签推送失败")
            return False

        # 4. 创建 Release
        self.create_github_release(log)

        # 5. 生成摘要
        summary = self.generate_release_summary(log)
        log.info(summary)

        return True


def main():
    """主入口。"""
    parser = argparse.ArgumentParser(
        description="Matha v4.3 一键发布脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python release_oneclick.py              # 执行发布
  python release_oneclick.py --dry-run    # 预览模式
  python release_oneclick.py --verbose    # 详细日志
  python release_oneclick.py --version 4.3.1  # 指定版本
        """
    )
    parser.add_argument("--version", default="4.3.0", help="版本号（默认: 4.3.0）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际执行")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志输出")
    args = parser.parse_args()

    script = ReleaseScript(
        version=args.version,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    result = script.run()

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
