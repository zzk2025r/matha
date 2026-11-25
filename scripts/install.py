# -*- coding: utf-8 -*-
"""
Matha 统一安装脚本（版本号取 src/__version__.py，见下方 _repo_version）

设计理念：
  - 单一入口：一个桌面图标启动完整环境
  - 自动更新：开发者推送GitHub → 用户一键更新
  - 内部双实例对用户透明：dev=源码，client=运行时
  - 独立文件夹：~/Matha/
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_version() -> str:
    """版本单一来源 = src/__version__.py（安装脚本不各自硬编发行号）。"""
    vf = _REPO_ROOT / "src" / "__version__.py"
    if vf.exists():
        m = re.search(r'^__version__\s*=\s*"([^"]+)"',
                      vf.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    return "未知"


VERSION = _repo_version()
REPO_SSH = "git@github.com:zzk2025r/matha.git"
REPO_HTTPS = "https://github.com/zzk2025r/matha.git"

# ─────────────────────────────────────────────────────────────
# 目录结构（内部双实例，对用户透明）
# ─────────────────────────────────────────────────────────────
# ~/Matha/
# ├── matha.exe          ← 主入口（一键启动）
# ├── src/               ← 当前版本源码（只读，自动更新）
# ├── workspace/         ← 用户数据（项目/公式/笔记）
# ├── config.json        ← 配置（版本/更新设置）
# └── .cache/            ← 运行时缓存
#
# 开发端（~/Matha/dev/）由 git 管理，用户不直接接触
# ─────────────────────────────────────────────────────────────

def get_matha_home() -> Path:
    env = Path.home() / ".matha-home"
    alt = Path.home() / "Matha"
    if env.exists(): return env
    if alt.exists(): return alt
    return alt  # 默认新建到 ~/Matha/

def check_git() -> bool:
    try:
        r = subprocess.run(["git", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except: return False

def clone_repo(dest: Path, repo: str) -> bool:
    for url in [repo, REPO_HTTPS if "github" in repo else REPO_SSH]:
        r = subprocess.run(["git", "clone", "--depth", "1", url, str(dest)],
                          capture_output=True, timeout=120)
        if r.returncode == 0: return True
    return False

def copy_src(src_dir: Path, dst_dir: Path) -> int:
    """复制源码到 client，跳过 __pycache__ 和 .pyc"""
    count = 0
    if not src_dir.exists(): return 0
    if dst_dir.exists(): shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    for item in src_dir.iterdir():
        if item.name in ("__pycache__",) or item.name.endswith(".pyc"):
            continue
        dest = dst_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            count += sum(1 for _ in dest.rglob("*.py"))
        else:
            shutil.copy2(item, dest)
            count += 1
    return count

def create_launcher(matha_home: Path) -> Path:
    """创建主入口启动器（跨平台）"""
    launcher = matha_home / "matha"
    launcher.write_text(f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Matha v{VERSION} — 统一入口"""
import sys, os
from pathlib import Path

# 自动定位 client/src
home = Path(__file__).parent
src = home / "src"
if not src.exists():
    print(f"Matha 工作空间不完整，请重新安装。", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(src))
os.chdir(src)

# 转发所有参数到 matha_main
from src.matha_main import main
sys.exit(main())
''', encoding="utf-8")
    return launcher

def create_autoupdate(matha_home: Path) -> Path:
    """创建自动更新脚本"""
    autoupdate = matha_home / "matha-update"
    autoupdate.write_text(f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Matha 自动更新器"""
from pathlib import Path
import subprocess, sys, shutil, tempfile

MATHA_HOME = Path(__file__).parent
CLIENT_SRC = MATHA_HOME / "src"
REPO_SSH = "{REPO_SSH}"
REPO_HTTPS = "{REPO_HTTPS}"

def main():
    print("检查更新...")
    temp = Path(tempfile.mkdtemp(prefix="matha_upd_"))
    try:
        for url in [REPO_SSH, REPO_HTTPS]:
            r = subprocess.run(["git","clone","--depth","1",url,str(temp)],
                             capture_output=True, timeout=120)
            if r.returncode == 0: break
        else:
            print("无法连接 GitHub，请检查网络或 SSH 配置。")
            return 1

        new_src = temp / "src"
        if not new_src.exists():
            print("新版本无 src 目录")
            return 1

        # 备份当前版本
        if CLIENT_SRC.exists():
            backup = MATHA_HOME / ".cache" / "backup"
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copytree(CLIENT_SRC, backup / CLIENT_SRC.name, dirs_exist_ok=True)

        # 复制新版本
        if CLIENT_SRC.exists():
            shutil.rmtree(CLIENT_SRC)
        shutil.copytree(new_src, CLIENT_SRC)

        print(f"✓ 已更新到最新版本")
        return 0
    except Exception as e:
        print(f"更新失败: {e}")
        return 1
    finally:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
''', encoding="utf-8")
    return autoupdate

def copy_frozen_entry(matha_home: Path) -> str:
    """冻结入口优先：仓库 `dist/` 有冻结产物就装它，返回文件名。

    没有则返回空串——安装仍可用（源码模式），但对外必须说清「本次不是独立
    进程入口」，否则使用端会以为自己拿到的是 matha.exe。
    """
    stem = "matha.exe" if os.name == "nt" else "matha"
    src = _REPO_ROOT / "dist" / stem
    if not src.is_file():
        return ""
    shutil.copy2(src, matha_home / stem)
    return stem

def create_windows_wrappers(matha_home: Path, frozen_entry: str) -> None:
    """Windows 下无后缀脚本无法被 CMD 调用，需要 .bat 包装器。

    `matha` / `matha-update` 本身带 shebang，POSIX 可执行；CMD 只认 PATHEXT，
    所以这里生成的 .bat 才是使用端真正敲得通的命令名。
    """
    def write_bat(name: str, exe: str) -> None:
        if exe:
            body = f'@echo off\r\n"%~dp0{exe}" %*\r\n'
        else:
            body = f'@echo off\r\n"{sys.executable}" "%~dp0{name}" %*\r\n'
        (matha_home / f"{name}.bat").write_text(body, encoding="utf-8")

    write_bat("matha", frozen_entry)
    write_bat("matha-update", "")

def create_config(matha_home: Path, dev_path: Path) -> dict:
    """创建配置文件"""
    config = {
        "name": "Matha",
        "version": VERSION,
        "description": "自举式领域专用编程语言",
        "install_time": datetime.now().isoformat(),
        "auto_update": True,
        "update_interval_hours": 24,
        "dev_path": str(dev_path),
        "github_repo": REPO_SSH,
        "github_repo_https": REPO_HTTPS,
    }
    (matha_home / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return config

def create_workspace(matha_home: Path) -> None:
    """创建用户工作区"""
    ws = matha_home / "workspace"
    for sub in ["projects", "formulas", "notebooks", ".cache"]:
        (ws / sub).mkdir(parents=True, exist_ok=True)

def create_ide(matha_home: Path) -> None:
    """创建 Matha IDE 配置（自举开发环境）"""
    ide = matha_home / "MathaIDE"
    ide.mkdir(parents=True, exist_ok=True)
    config = {
        "name": "Matha IDE",
        "version": VERSION,
        "type": "matha-ide",
        "description": "以Matha为基础的开发环境",
        "features": ["syntax_highlighting", "realtime_diagnostic",
                     "code_completion", "formula_editor", "repl"],
        "languages": ["matha", "python", "c", "rust", "go", "js"],
        "auto_update": True,
    }
    (ide / "matha_ide.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

def create_readme(matha_home: Path) -> None:
    """创建使用说明"""
    readme = f"""# Matha v{VERSION}

**安装时间：** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**安装位置：** {matha_home}

## 使用

以下命令在安装目录内直接可敲：Windows 走 `matha.bat`（有冻结产物时走
`matha.exe`），POSIX 走 `./matha`。本安装器不修改 PATH，需要全局命令请
自行把安装目录加入 PATH。

```powershell
matha                # 一键启动 REPL
matha eval "sin(3.14) + cos(1.57)"
matha run demo.matha
matha --version
matha-update         # 检查更新
```

## 目录

- `src/` — 当前版本源码（可更新）
- `workspace/` — 您的项目、公式、笔记
- `MathaIDE/` — 开发环境配置

## 更新

开发者推送 GitHub 后，运行：
```powershell
matha-update
```
"""
    (matha_home / "README.md").write_text(readme, encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(
        description=f"Matha v{VERSION} 统一安装器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python install.py                 # 默认安装到 ~/Matha/
  python install.py --dev D:/trae   # 指定开发源码路径
  python install.py --force         # 强制重装
        """
    )
    parser.add_argument("--dev", help="开发源码路径（符号链接目标）")
    parser.add_argument("--force", action="store_true", help="强制重装")
    args = parser.parse_args()

    home = get_matha_home()
    print(f"Matha v{VERSION} 安装器")
    print(f"安装路径: {home}\n")

    # 检查冲突
    if home.exists() and not args.force:
        print(f"[信息] {home} 已存在")
        print(f"添加 --force 强制重装\n")
        return 0

    # 创建目录
    home.mkdir(parents=True, exist_ok=True)

    # 创建工作区
    print("创建用户工作区...")
    create_workspace(home)

    # 创建 IDE
    print("创建 Matha IDE...")
    create_ide(home)

    # 创建说明
    print("创建使用说明...")
    create_readme(home)

    # 获取开发源码
    dev_src = Path(args.dev) if args.dev else None
    dev_dir = home / "dev"
    client_src = home / "src"

    if dev_src and dev_src.exists():
        print(f"使用本地源码: {dev_src}")
        count = copy_src(dev_src, client_src)
        # 创建符号链接
        if dev_dir.exists():
            if dev_dir.is_symlink(): dev_dir.unlink()
            else: shutil.rmtree(dev_dir)
        try:
            dev_dir.symlink_to(dev_src, target_is_directory=True)
        except OSError as e:
            # Windows 非开发者模式/无特权时 symlink 会失败；此前异常直接冒泡，
            # 安装半途中断（src 已复制、启动器与配置未建）。改落指针文件并如实说明。
            dev_dir.mkdir(parents=True, exist_ok=True)
            (dev_dir / "DEV_SOURCE.txt").write_text(
                f"符号链接不可用（{e}）\n开发端源码路径: {dev_src}\n", encoding="utf-8")
            print(f"[提示] 未能创建 {dev_dir} 符号链接，已改落指针文件")
    else:
        print("从 GitHub 克隆开发端...")
        if dev_dir.exists():
            if dev_dir.is_symlink(): dev_dir.unlink()
            else: shutil.rmtree(dev_dir)
        if clone_repo(dev_dir, REPO_SSH) or clone_repo(dev_dir, REPO_HTTPS):
            print(f"已克隆到 {dev_dir}")
            count = copy_src(dev_dir / "src", client_src)
        else:
            print("警告: GitHub 克隆失败，创建空开发端")
            (dev_dir / "README.md").write_text(
                "# Matha 开发端\n请手动克隆:\ngit clone git@github.com:zzk2025r/matha.git\n",
                encoding="utf-8"
            )
            count = 0

    # 创建启动器
    print("创建启动器...")
    frozen_entry = copy_frozen_entry(home)
    launcher = create_launcher(home)
    autoupdate = create_autoupdate(home)
    if os.name != "nt":
        for p in (launcher, autoupdate):
            p.chmod(0o755)
    else:
        create_windows_wrappers(home, frozen_entry)
    create_mcp_config(home)

    # 创建配置
    config = create_config(home, dev_dir)

    print(f"\n{'='*50}")
    print(f"  Matha v{VERSION} 安装完成！")
    print(f"{'='*50}")
    run_cmd_name = "matha" if os.name == "nt" else "./matha"
    upd_cmd_name = "matha-update" if os.name == "nt" else "./matha-update"
    print(f"\n安装位置: {home}")
    print(f"源码文件: {count} 个 Python 文件")
    print(f"入口模式: {f'冻结独立进程 {frozen_entry}' if frozen_entry else '源码模式（本机 dist/ 无冻结产物，构建: python scripts/build_exe.py --matha）'}")
    print(f"\n开始使用:")
    print(f"  cd {home}")
    print(f"  {run_cmd_name}            # 启动 REPL")
    print(f"  {run_cmd_name} eval '2+3' # 计算")
    print(f"  {upd_cmd_name}           # 检查更新")
    print(f"\n环境变量: MATHA_HOME={home}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
