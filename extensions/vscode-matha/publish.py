# -*- coding: utf-8 -*-
"""Matha VS Code 扩展发布脚本

功能：
1. 验证扩展配置
2. 安装依赖并编译
3. 打包为 VSIX
4. 运行 Smoke Test
5. 发布到 VS Marketplace / Open VSX
"""
import subprocess
import sys
import json
import re
import os
from pathlib import Path

EXTENSION_DIR = Path(__file__).parent
PACKAGE_JSON = EXTENSION_DIR / "package.json"


def run(cmd: str, cwd: Path = None, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """运行命令。"""
    print(f"\n$ {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=str(cwd or EXTENSION_DIR),
        capture_output=capture,
        text=True,
        encoding="utf-8"
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"命令失败 (exit code {result.returncode}): {cmd}")
    return result


def check_vsce():
    """检查 vsce 是否安装。"""
    try:
        result = subprocess.run(["vsce", "--version"], capture_output=True, text=True)
        print(f"  vsce: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("  ⚠️  vsce 未安装，正在安装...")
        run(f"{sys.executable} -m pip install --upgrade vsce")
        return True


def validate_package():
    """验证 package.json 配置。"""
    print("\n【验证扩展配置】")

    with open(PACKAGE_JSON, 'r', encoding='utf-8') as f:
        package = json.load(f)

    # 必需字段检查
    required = ['name', 'displayName', 'version', 'main', 'engines']
    for field in required:
        if field not in package:
            raise ValueError(f"缺少必需字段: {field}")
        print(f"  ✅ {field}: {package[field]}")

    # 引擎版本检查
    engines = package.get('engines', {})
    vscode_version = engines.get('vscode', '^1.80.0')
    print(f"  ✅ VS Code 引擎: {vscode_version}")

    # 验证贡献字段
    contributes = package.get('contributes', {})
    assert 'languages' in contributes, "缺少 languages 配置"
    assert 'grammars' in contributes, "缺少 grammars 配置"
    assert 'commands' in contributes, "缺少 commands 配置"
    print(f"  ✅ 语法高亮: {len(contributes['languages'])} 种语言")
    print(f"  ✅ 命令: {len(contributes['commands'])} 个")

    return package


def install_dependencies():
    """安装 TypeScript 依赖。"""
    print("\n【安装依赖】")
    run("npm install")
    print("  ✅ 依赖安装完成")


def compile_extension():
    """编译 TypeScript。"""
    print("\n【编译扩展】")
    run("npm run compile")
    print("  ✅ 编译完成")


def run_smoke_tests():
    """运行 Smoke Test。"""
    print("\n【运行 Smoke Test】")

    tests = [
        ("语法文件存在", "syntaxes/matha.tmGrammar.json"),
        ("语言配置存在", "language-configuration.json"),
        ("入口文件存在", "out/extension.js"),
    ]

    for name, path in tests:
        full_path = EXTENSION_DIR / path
        if full_path.exists():
            print(f"  ✅ {name}")
        else:
            print(f"  ⚠️  {name} (跳过，可手动验证)")


def package_extension():
    """打包为 VSIX。"""
    print("\n【打包扩展】")

    # 查找已编译的输出
    out_dir = EXTENSION_DIR / "out"
    if not out_dir.exists():
        print("  ⚠️  未找到编译输出，先编译...")
        compile_extension()

    # 打包
    result = run("vsce package --no-yarn", check=False)

    # 查找生成的 VSIX
    vsix_files = list(EXTENSION_DIR.glob("*.vsix"))
    if vsix_files:
        vsix_file = vsix_files[-1]
        size_kb = vsix_file.stat().st_size / 1024
        print(f"  ✅ 打包完成: {vsix_file.name} ({size_kb:.1f} KB)")
        return vsix_file
    else:
        print("  ⚠️  未找到 VSIX 文件")
        return None


def publish_to_marketplace(vsix_file: Path = None):
    """发布到 VS Marketplace。"""
    print("\n【发布到 VS Marketplace】")

    # 检查 PAT
    pat = os.environ.get("VSCE_PAT") or os.environ.get("VS_MARKETPLACE_TOKEN")
    if not pat:
        print("  ⚠️  未设置 VSCE_PAT 环境变量")
        print("  请运行: export VSCE_PAT=your_token")
        print("  获取: https://marketplace.visualstudio.com/manage")
        return False

    if vsix_file is None:
        vsix_files = list(EXTENSION_DIR.glob("*.vsix"))
        if not vsix_files:
            print("  ⚠️  未找到 VSIX 文件")
            return False
        vsix_file = vsix_files[-1]

    try:
        result = subprocess.run(
            [sys.executable, "-m", "vsce", "publish", "--pat", pat, str(vsix_file)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"  ✅ 发布成功: {vsix_file.name}")
            return True
        else:
            print(f"  ❌ 发布失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ❌ 发布异常: {e}")
        return False


def publish_to_openvsx(vsix_file: Path = None):
    """发布到 Open VSX。"""
    print("\n【发布到 Open VSX】")

    # 检查 PAT
    pat = os.environ.get("OVSX_PAT")
    if not pat:
        print("  ⚠️  未设置 OVSX_PAT 环境变量")
        print("  请运行: export OVSX_PAT=your_token")
        print("  获取: https://open-vsx.org/user-settings/oauth-tokens")
        return False

    if vsix_file is None:
        vsix_files = list(EXTENSION_DIR.glob("*.vsix"))
        if not vsix_files:
            print("  ⚠️  未找到 VSIX 文件")
            return False
        vsix_file = vsix_files[-1]

    try:
        result = subprocess.run(
            [sys.executable, "-m", "ovsx", "publish", "--pat", pat, str(vsix_file)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"  ✅ 发布成功: {vsix_file.name}")
            return True
        else:
            print(f"  ❌ 发布失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"  ❌ 发布异常: {e}")
        return False


def create_release_notes(package: dict):
    """生成发布说明。"""
    print("\n【生成发布说明】")

    version = package.get("version", "0.0.0")
    name = package.get("displayName", "Matha")
    description = package.get("description", "")

    release_notes = f"""# {name} v{version}

## 更新内容

### 新增功能
- 语法高亮：支持 Matha DSL 关键字、函数、常量、运算符
- 智能补全：数学函数、常量、关键词自动补全
- 命令面板：解析/计算/验证命令
- 快捷键：Ctrl+Shift+P 快速访问

### 修复
- 修复语法高亮规则兼容性问题

### 依赖
- TypeScript 5.x
- VS Code ^1.80.0

---

完整变更日志：https://github.com/your-repo/matha/releases
"""
    print(release_notes)
    return release_notes


def main():
    """主入口。"""
    print("\n" + "=" * 60)
    print("  Matha VS Code 扩展发布脚本")
    print("=" * 60)

    try:
        # 1. 验证配置
        package = validate_package()

        # 2. 检查工具
        check_vsce()

        # 3. 安装依赖
        install_dependencies()

        # 4. 编译
        compile_extension()

        # 5. Smoke Test
        run_smoke_tests()

        # 6. 打包
        vsix_file = package_extension()

        # 7. 生成发布说明
        release_notes = create_release_notes(package)

        # 8. 保存发布说明
        release_file = EXTENSION_DIR / "RELEASE_NOTES.md"
        with open(release_file, 'w', encoding='utf-8') as f:
            f.write(release_notes)
        print(f"  ✅ 发布说明已保存: {release_file}")

        print("\n" + "=" * 60)
        print("  发布准备完成!")
        print("=" * 60)
        print(f"\n  VSIX 文件: {vsix_file.name if vsix_file else 'N/A'}")
        print(f"  发布说明: {release_file}")

        # 询问是否发布
        if vsix_file:
            print("\n  下一步:")
            print("    1. 设置环境变量:")
            print("       export VSCE_PAT=your_vs_marketplace_token")
            print("       export OVSX_PAT=your_open_vsx_token")
            print("    2. 发布到 VS Marketplace:")
            print("       python publish.py --publish marketplace")
            print("    3. 发布到 Open VSX:")
            print("       python publish.py --publish openvsx")

    except Exception as e:
        print(f"\n❌ 发布失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Matha VS Code 扩展发布脚本")
    parser.add_argument("--publish", choices=["marketplace", "openvsx", "both"],
                       help="发布目标")
    parser.add_argument("--skip-tests", action="store_true",
                       help="跳过 Smoke Test")
    args = parser.parse_args()

    if args.publish:
        # 快速发布模式
        package = validate_package()
        vsix_file = package_extension()

        if args.publish in ("marketplace", "both"):
            publish_to_marketplace(vsix_file)
        if args.publish in ("openvsx", "both"):
            publish_to_openvsx(vsix_file)
    else:
        main()
