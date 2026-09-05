# -*- coding: utf-8 -*-
"""
Matha 工作空间安装脚本

创建双实例架构：
  - ~/Matha/client/   (使用端)
  - ~/Matha/dev/      (更新端，符号链接到开发目录)
  - ~/Matha/workspace/ (用户工作区)
  - ~/Matha/MathaIDE/  (Matha IDE 开发环境)
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

VERSION = "4.4.57"
REPO_URL = "git@github.com:zzk2025r/matha.git"
REPO_URL_HTTPS = "https://github.com/zzk2025r/matha.git"


def get_matha_home() -> Path:
    """获取 Matha 工作空间根目录。"""
    env_home = os.environ.get("MATHA_HOME")
    if env_home:
        return Path(env_home)
    # 默认: ~/.matha-home (使用点前缀避免与项目目录混淆)
    return Path.home() / ".matha-home"


def ensure_directory(path: Path) -> Path:
    """创建目录并返回。"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_client_workspace(client_dir: Path) -> None:
    """创建使用端目录结构。"""
    subdirs = [
        "src",
        "src/compiler",
        "src/domains",
        "src/stdlib",
        "src/intent",
        "src/jupyter",
        "src/hardware",
        "docs",
        "config",
    ]
    for sub in subdirs:
        ensure_directory(client_dir / sub)

    # 创建 config.json
    config = {
        "version": VERSION,
        "name": "Matha",
        "description": "自举式领域专用编程语言",
        "auto_update": True,
        "update_interval_hours": 24,
        "github_repo": REPO_URL,
        "github_repo_https": REPO_URL_HTTPS,
        "branch": "main",
        "language": os.environ.get("MATHA_LANG", "zh-CN"),
        "ide_enabled": True,
        "ssl_backend": "schannel",
        "http_version": "HTTP/1.1",
    }
    (client_dir / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 创建 update.py (自举更新器)
    write_update_script(client_dir / "update.py")

    # 创建 README
    readme = f"""# Matha 使用端

**版本：** {VERSION}
**工作空间：** {client_dir}

## 快速开始

```powershell
# 启动 REPL
python -m src.matha_main

# 或使用快捷命令
matha
```

## 目录结构

- `src/` — 只读源码（随版本更新）
- `docs/` — 离线文档
- `config.json` — 使用端配置
- `update.py` — 自举更新器

## 更新

```powershell
# 手动检查更新
python update.py

# 或
matha update
```
"""
    (client_dir / "README.md").write_text(readme, encoding="utf-8")


def create_workspace_dir(workspace_dir: Path) -> None:
    """创建用户工作区。"""
    subdirs = [
        "projects",
        "formulas",
        "notebooks",
        ".matha_cache",
        ".matha_cache/python",
        ".matha_cache/rust",
    ]
    for sub in subdirs:
        ensure_directory(workspace_dir / sub)

    # 创建用户公式模板
    formula_template = """# 用户公式模板
# 格式: name | expr | params | domain | notes
牛顿第二定律 | m*a | F,m,a | 动力学 | F = m × a
动能 | 0.5*m*v^2 | Ek,m,v | 动力学 | 动能量公式
"""
    (workspace_dir / "formulas" / "user_formulas.matha").write_text(
        formula_template, encoding="utf-8"
    )

    # 创建项目模板
    project_template = """# 我的 Matha 项目
# 创建时间: {{date}}

func 平方(x) -> Float = (x) => x * x

#1：[平方(5)]
"""
    (workspace_dir / "projects" / "my_project.matha").write_text(
        project_template, encoding="utf-8"
    )


def create_dev_link(dev_dir: Path, dev_source: Optional[Path] = None) -> bool:
    """创建更新端目录（符号链接或克隆）。"""
    if dev_source and dev_source.exists():
        # 尝试符号链接
        try:
            if dev_dir.exists():
                if dev_dir.is_symlink():
                    dev_dir.unlink()
                else:
                    # 已存在且非链接，重命名为 .backup
                    backup = dev_dir.parent / f"dev.backup.{int(dev_dir.stat().st_mtime)}"
                    dev_dir.rename(backup)
            dev_dir.symlink_to(dev_source, target_is_directory=True)
            print(f"  ✓ 符号链接: {dev_dir} -> {dev_source}")
            return True
        except (OSError, NotImplementedError):
            # Windows 非管理员权限无法创建符号链接，使用目录复制
            pass

    # 尝试克隆
    print("  尝试克隆开发仓库...")
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(dev_dir)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print(f"  ✓ 已克隆到: {dev_dir}")
            return True
        # HTTPS 备用
        result = subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL_HTTPS, str(dev_dir)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print(f"  ✓ 已克隆到: {dev_dir} (HTTPS)")
            return True
    except Exception as e:
        print(f"  [警告] 克隆失败: {e}")

    # 创建空目录作为占位
    ensure_directory(dev_dir)
    (dev_dir / "README.md").write_text(
        "# Matha 开发端\n\n请先克隆仓库：\n```powershell\ngit clone git@github.com:zzk2025r/matha.git\n```\n",
        encoding="utf-8",
    )
    print(f"  ! 已创建空目录: {dev_dir}（请手动克隆仓库）")
    return False


def write_update_script(path: Path) -> None:
    """写入自举更新器脚本。"""
    script = r'''"""
Matha 自举更新器

使用端通过此脚本自动从 GitHub 或开发端更新。
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

VERSION = "4.4.57"
REPO_URL = "git@github.com:zzk2025r/matha.git"
REPO_URL_HTTPS = "https://github.com/zzk2025r/matha.git"

CLIENT_DIR = Path(__file__).parent
CONFIG_FILE = CLIENT_DIR / "config.json"
BACKUP_DIR = CLIENT_DIR / ".backup"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {"version": VERSION, "auto_update": True, "github_repo": REPO_URL}


def save_config(config: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def get_github_latest_tag() -> Optional[str]:
    """获取 GitHub 最新版本标签。"""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", REPO_URL, "refs/tags/v*"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["git", "ls-remote", "--tags", "--refs", REPO_URL_HTTPS, "refs/tags/v*"],
                capture_output=True, text=True, timeout=15,
            )
        lines = result.stdout.strip().split("\n")
        tags = [l.split("/")[-1] for l in lines if l.strip()]
        if tags:
            return sorted(tags, key=lambda t: tuple(int(x) for x in t.lstrip("v").split(".")))[-1]
    except Exception:
        pass
    return None


def get_installed_version() -> str:
    config = load_config()
    return config.get("version", VERSION)


def create_backup() -> Path:
    """创建当前 client/ 备份。"""
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)
    backup_path = BACKUP_DIR / "src"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if (CLIENT_DIR / "src").exists():
        shutil.copytree(CLIENT_DIR / "src", backup_path, dirs_exist_ok=True)
    return backup_path


def restore_backup(backup_path: Path) -> None:
    """恢复备份。"""
    if backup_path.exists():
        if (CLIENT_DIR / "src").exists():
            shutil.rmtree(CLIENT_DIR / "src")
        shutil.copytree(backup_path, CLIENT_DIR / "src")
        print(f"  ✓ 已回滚到备份: {backup_path}")


def verify_installation() -> bool:
    """验证安装是否完整。"""
    try:
        from src.interp import interpret
        outputs, _ = interpret("2 + 3")
        return outputs[-1] == 5 if outputs else False
    except Exception:
        return False


def run_tests() -> bool:
    """运行测试套件。"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest",
             "tests/test_matha_growth.py",
             "tests/test_unified_layers.py",
             "-q"],
            cwd=CLIENT_DIR.parent,  # 从 ~/Matha/ 运行
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0
    except Exception:
        return False


def update_from_dev(dev_dir: Path) -> bool:
    """从开发端更新。"""
    src_src = dev_dir / "src"
    if not src_src.exists():
        return False
    dst_src = CLIENT_DIR / "src"
    if dst_src.exists():
        shutil.rmtree(dst_src)
    shutil.copytree(src_src, dst_src)
    # 更新 docs
    src_docs = dev_dir / "docs"
    dst_docs = CLIENT_DIR / "docs"
    if src_docs.exists():
        if dst_docs.exists():
            shutil.rmtree(dst_docs)
        shutil.copytree(src_docs, dst_docs)
    return True


def update_from_github() -> bool:
    """从 GitHub 更新。"""
    temp_dir = Path(tempfile.mkdtemp(prefix="matha_update_"))
    try:
        # 克隆最新代码
        result = subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(temp_dir)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", REPO_URL_HTTPS, str(temp_dir)],
                capture_output=True, text=True, timeout=60,
            )
        if result.returncode != 0:
            print("  ✗ 无法从 GitHub 克隆")
            return False

        # 备份当前版本
        backup_path = create_backup()

        # 复制新源码
        src_src = temp_dir / "src"
        dst_src = CLIENT_DIR / "src"
        if src_src.exists():
            if dst_src.exists():
                shutil.rmtree(dst_src)
            shutil.copytree(src_src, dst_src)

        # 复制 docs
        src_docs = temp_dir / "docs"
        dst_docs = CLIENT_DIR / "docs"
        if src_docs.exists():
            if dst_docs.exists():
                shutil.rmtree(dst_docs)
            shutil.copytree(src_docs, dst_docs)

        # 验证
        if not verify_installation():
            print("  ✗ 安装验证失败，回滚...")
            restore_backup(backup_path)
            return False

        # 更新版本号
        config = load_config()
        latest = get_github_latest_tag()
        if latest:
            config["version"] = latest
            save_config(config)

        print(f"  ✓ 更新成功: {config['version']}")
        return True

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Matha 自举更新器")
    parser.add_argument("--from-dev", metavar="PATH", help="从开发端更新")
    parser.add_argument("--from-github", action="store_true", help="从 GitHub 更新")
    parser.add_argument("--check", action="store_true", help="仅检查更新")
    parser.add_argument("--force", action="store_true", help="强制更新")
    args = parser.parse_args()

    config = load_config()
    current_version = config.get("version", VERSION)
    print(f"Matha 更新器 v{current_version}")
    print(f"工作空间: {CLIENT_DIR}")

    if args.check:
        latest = get_github_latest_tag()
        if latest and latest != current_version:
            print(f"  发现新版本: {latest} (当前: {current_version})")
            print(f"  运行 'python update.py --from-github' 进行更新")
            sys.exit(0)
        else:
            print(f"  已是最新版本: {current_version}")
            sys.exit(0)

    if args.from_dev:
        dev_dir = Path(args.from_dev)
        if not dev_dir.exists():
            print(f"  ✗ 开发端目录不存在: {dev_dir}")
            sys.exit(1)
        print(f"  从开发端更新: {dev_dir}")
        if update_from_dev(dev_dir):
            print("  ✓ 更新完成")
        else:
            print("  ✗ 更新失败")
            sys.exit(1)

    elif args.from_github or (config.get("auto_update") and not args.force):
        print("  从 GitHub 更新...")
        if update_from_github():
            print("  ✓ 更新完成")
        else:
            print("  ✗ 更新失败")
            sys.exit(1)

    else:
        print("  无需更新（当前版本已是最新）")


if __name__ == "__main__":
    main()
'''
    path.write_text(script, encoding="utf-8")


def create_matha_ide(ide_dir: Path) -> None:
    """创建 Matha IDE 目录结构（以 Matha 为基础的开发环境）。"""
    subdirs = [
        "matha_ide",
        "matha_ide/themes",
        "matha_ide/extensions",
        "matha_ide/schemas",
    ]
    for sub in subdirs:
        ensure_directory(ide_dir / sub)

    # IDE 核心配置（JSON，可被任何系统识别）
    ide_config = {
        "name": "Matha IDE",
        "version": VERSION,
        "description": "以 Matha 为基础的开发环境",
        "type": "matha-ide",
        "syntax": {
            "file_extensions": [".matha"],
            "lexer": "src.lexer",
            "parser": "src.parser",
        },
        "languages": ["matha", "python", "c", "rust", "go", "js"],
        "features": [
            "syntax_highlighting",
            "realtime_diagnostic",
            "code_completion",
            "formula_editor",
            "version_control",
            "repl",
        ],
        "auto_update": True,
        "update_source": "github",
    }
    (ide_dir / "matha_ide.json").write_text(
        json.dumps(ide_config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # IDE 插件规范（标准 JSON Schema，可被任何 IDE 识别）
    plugin_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Matha IDE 插件规范",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "version": {"type": "string"},
            "description": {"type": "string"},
            "entry": {"type": "string", "description": "插件入口文件"},
            "commands": {"type": "array", "items": {"type": "string"}},
            "languages": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "version", "entry"],
    }
    (ide_dir / "matha_ide" / "schemas" / "plugin.schema.json").write_text(
        json.dumps(plugin_schema, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # README
    readme = f"""# Matha IDE

**版本：** {VERSION}  
**基础：** Matha 自举开发环境  

## 设计理念

> **Matha IDE 由 Matha 自身编写，任何系统可识别与使用。**

## 文件结构

```
MathaIDE/
├── matha_ide.json          ← IDE 配置（JSON，任何系统可读）
├── matha_ide/
│   ├── schemas/            ← JSON Schema 插件规范
│   ├── themes/             ← 语法高亮主题
│   └── extensions/         ← 插件目录
└── README.md
```

## 跨系统识别

| 系统 | 识别方式 |
|------|---------|
| VSCode | 安装 .vsix 插件（基于 JSON 配置） |
| JetBrains | 通过 language plugin 协议 |
| Flutter | 通过 pubspec.yaml 识别 |
| Web | 通过 manifest.json 识别 |
| 任何系统 | 读取 matha_ide.json 配置文件 |

## 使用

```powershell
# 启动 IDE（如果已配置）
matha ide
```
"""
    (ide_dir / "README.md").write_text(readme, encoding="utf-8")


def create_matha_config_root(matha_home: Path) -> None:
    """创建 Matha 根配置文件。"""
    config = {
        "matha_home": str(matha_home),
        "version": VERSION,
        "client_dir": str(matha_home / "client"),
        "dev_dir": str(matha_home / "dev"),
        "workspace_dir": str(matha_home / "workspace"),
        "ide_dir": str(matha_home / "MathaIDE"),
        "github_repo": REPO_URL,
        "github_repo_https": REPO_URL_HTTPS,
        "created_at": "",  # 将在安装时填充
    }
    (matha_home / "matha-home.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Matha 工作空间安装器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python setup_workspace.py                  # 使用默认路径 (~/.matha-home)
  python setup_workspace.py --dev-path D:/trae  # 指定开发端路径
  python setup_workspace.py --force          # 强制重新安装
        """,
    )
    parser.add_argument("--dev-path", help="开发端源码路径（符号链接目标）")
    parser.add_argument("--force", action="store_true", help="强制重新安装")
    parser.add_argument("--skip-dev", action="store_true", help="跳过开发端创建")
    parser.add_argument("--skip-ide", action="store_true", help="跳过 IDE 创建")
    args = parser.parse_args()

    matha_home = get_matha_home()
    print(f"Matha 工作空间安装器 v{VERSION}")
    print(f"目标目录: {matha_home}\n")

    # 检查是否已存在
    if matha_home.exists() and not args.force:
        existing = list(matha_home.iterdir())
        if existing:
            print(f"  [信息] 工作空间已存在: {matha_home}")
            print(f"  要重新安装，请添加 --force 参数")
            print(f"\n当前内容:")
            for item in existing:
                print(f"  - {item.name}")
            sys.exit(0)

    # 创建根目录
    ensure_directory(matha_home)
    create_matha_config_root(matha_home)

    # 创建 client（使用端）
    client_dir = ensure_directory(matha_home / "client")
    print(f"  创建使用端: {client_dir}")
    create_client_workspace(client_dir)

    # 创建 workspace（用户工作区）
    workspace_dir = ensure_directory(matha_home / "workspace")
    print(f"  创建工作区: {workspace_dir}")
    create_workspace_dir(workspace_dir)

    # 创建 dev（更新端）
    dev_dir = matha_home / "dev"
    if not args.skip_dev:
        print(f"  创建更新端: {dev_dir}")
        create_dev_link(dev_dir, Path(args.dev_path) if args.dev_path else None)
    else:
        ensure_directory(dev_dir)
        print(f"  跳过更新端创建（--skip-dev）")

    # 创建 IDE
    ide_dir = ensure_directory(matha_home / "MathaIDE")
    if not args.skip_ide:
        print(f"  创建 IDE: {ide_dir}")
        create_matha_ide(ide_dir)
    else:
        print(f"  跳过 IDE 创建（--skip-ide）")

    # 更新配置文件
    config = json.loads((matha_home / "matha-home.json").read_text(encoding="utf-8"))
    import datetime
    config["created_at"] = datetime.datetime.now().isoformat()
    (matha_home / "matha-home.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n{'='*50}")
    print(f"  Matha v{VERSION} 工作空间安装完成！")
    print(f"{'='*50}")
    print(f"\n目录结构:")
    print(f"  {matha_home}/")
    print(f"  ├── client/      ← 使用端（日常计算/学习）")
    print(f"  │   ├── src/     ← 只读源码")
    print(f"  │   ├── docs/    ← 离线文档")
    print(f"  │   ├── config.json")
    print(f"  │   └── update.py ← 自举更新器")
    print(f"  ├── dev/         ← 更新端（开发/测试/升级）")
    print(f"  ├── workspace/   ← 用户工作区（.matha 文件）")
    print(f"  │   ├── projects/")
    print(f"  │   └── formulas/")
    print(f"  ├── MathaIDE/    ← Matha IDE（自举开发环境）")
    print(f"  └── matha-home.json ← 工作空间配置")
    print(f"\n使用方法:")
    print(f"  cd {client_dir}")
    print(f"  python -m src.matha_main   # 启动 REPL")
    print(f"  python update.py           # 检查更新")
    print(f"\n开发者:")
    print(f"  git clone {REPO_URL}  # 克隆开发仓库")
    print(f"  # 或将 ~/trae 符号链接到 {dev_dir}")
    print(f"\n环境变量:")
    print(f"  MATHA_HOME={matha_home}")
    print(f"  MATHA_LANG=zh-CN           # 可选：设置语言")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
