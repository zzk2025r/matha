# -*- coding: utf-8 -*-
"""SystemGenerator：把 Matha 规格编译为系统脚本成品。

输出文件：
  - run.sh   Unix/macOS 脚本
  - run.bat  Windows 批处理

系统脚本由 ["接口", 方法, 路径, 处理] 中的"方法"映射为命令类型：
  命令/exec → 执行命令
  文件/file → 创建文件（处理作为内容）
  目录/dir  → 创建目录
  默认       → echo 输出
"""

from __future__ import annotations
from src.codegen.base import Generator, CodegenResult


class SystemGenerator(Generator):
    """系统脚本生成器：AppSpec → .sh / .bat 脚本。"""

    def generate(self) -> CodegenResult:
        files: list[str] = []
        try:
            sh = self._build_sh()
            files.append(self._write("run.sh", sh))
            bat = self._build_bat()
            files.append(self._write("run.bat", bat))
        except Exception as e:
            return CodegenResult(成功=False, 类型="系统", 名称=self.app.name,
                                 错误=str(e))
        return CodegenResult(
            成功=True, 类型="系统", 名称=self.app.name,
            文件=files, 入口=files[0],
        )

    def _build_sh(self) -> str:
        title = self.app.title or self.app.name
        lines = [
            "#!/usr/bin/env bash",
            f"# 由 Matha codegen 生成：{title}",
            "set -e",
            "",
        ]
        for ep in self.app.endpoints:
            lines.append(self._ep_to_sh(ep))
        if not self.app.endpoints:
            lines.append(f'echo "{title}"')
        lines.append('echo "完成"')
        return "\n".join(lines) + "\n"

    def _build_bat(self) -> str:
        title = self.app.title or self.app.name
        lines = [
            "@echo off",
            "chcp 65001 >nul",
            f"REM 由 Matha codegen 生成：{title}",
            "",
        ]
        for ep in self.app.endpoints:
            lines.append(self._ep_to_bat(ep))
        if not self.app.endpoints:
            lines.append(f'echo {title}')
        lines.append("echo 完成")
        return "\r\n".join(lines) + "\r\n"

    def _safe_sh(self, text: str) -> str:
        """Escapes a string for safe embedding in shell commands."""
        return text.replace("'", "'\\''").replace("$", "\\$").replace("`", "\\`")

    def _ep_to_sh(self, ep) -> str:
        method = ep.method.lower()
        if method in ("命令", "exec", "run"):
            return f'echo "Executing: {self._safe_sh(ep.path)}" && {self._safe_sh(ep.handler)}'
        if method in ("文件", "file", "write"):
            # Use unique heredoc delimiter to avoid clashes
            return f'cat > "{ep.path}" <<\'MATHA_EOF\'\n{ep.handler}\nMATHA_EOF'
        if method in ("目录", "dir", "mkdir"):
            return f'mkdir -p "{ep.path}"'
        return f'echo "{self._safe_sh(ep.handler)}"'

    def _ep_to_bat(self, ep) -> str:
        method = ep.method.lower()
        if method in ("命令", "exec", "run"):
            return f'echo "Executing: {ep.path}" & {ep.handler.replace("&", "^&").replace("%", "%%")}'
        if method in ("文件", "file", "write"):
            return f'(echo {ep.handler}) > "{ep.path}"'
        if method in ("目录", "dir", "mkdir"):
            return f'if not exist "{ep.path}" mkdir "{ep.path}"'
        return f'echo {ep.handler}'
