"""Matha 构建系统与软件能力测试。

验证 Matha 能否表达操作系统/软件的构建流程，覆盖：
  1. Windows 系统构建（意图块 + 配置 + 命令链式 + 子文件 + 文件路径）
  2. Android 系统构建（意图块 + 配置 + 多段命令 + 端口烧录 + 子文件）
  3. 软件应用构建（代码块多模块 + 段循环 + 子文件 + 文件结束标记）
  4. CI/CD 流水线（链式命令 + URL + 端口资源识别）

设计理念：Matha 是规格语言，用三层架构组合表达构建流程——
自然语言意图块描述构建目标，数学核心用命令链式/段/循环描述步骤，
子文件引用实现模块化构建，文件路径指向构建产物。

运行：python -m tests.test_system_build
"""

from src.parser import parse, ParseError
from src.semantic import analyze_source


def _check(src: str, label: str) -> None:
    """通用校验：解析 + 语义分析，断言无 error。"""
    print(f"\n--- {label} ---")
    print(src.rstrip())
    try:
        program = parse(src)
    except ParseError as ex:
        print(f"  ✗ 解析失败: {ex}")
        raise
    decl_types = [type(d).__name__ for d in program.decls]
    _, errors = analyze_source(src, verbose=False)
    err_n = len([e for e in errors if e.severity == "error"])
    print(f"  → 解析 OK: {decl_types}，语义 error 数: {err_n}")
    assert err_n == 0, f"{label} 存在 error: {[e.msg for e in errors if e.severity=='error']}"
    print(f"  ✓ {label} 通过")


# ============================================================
# 1. Windows 系统构建
# ============================================================

def test_windows_build():
    """Windows 系统构建：意图块 + 配置 + 下载/编译/生成链式 + 子文件 + 文件路径。"""
    src = (
        "【*/构建系统/*】生成 Windows 11 系统镜像\n"
        "@:版本=11，架构=x64，镜像=windows.iso\n"
        "#1：【下载源码 https://github.com/microsoft/windows】\n"
        "#2：【编译内核】>>【打包驱动】>>【生成镜像】\n"
        "#3：[windows.iso]…（0/1）【kernel.mod|drivers.mod】00001……（0/2）【win_part2.matha】"
    )
    _check(src, "1. Windows 系统构建")


# ============================================================
# 2. Android 系统构建
# ============================================================

def test_android_build():
    """Android 系统构建：意图块 + 配置 + 多段命令 + 端口烧录 + 子文件。"""
    src = (
        "【*/构建系统/*】构建 Android 系统并烧录到设备\n"
        "@:版本=14，目标=arm64，镜像=android.img\n"
        "#1：【拉取 AOSP https://android.googlesource.com】\n"
        "#2：【编译框架】>>【打包系统应用】>>【生成 OTA 包】\n"
        "#3：【烧录设备 localhost:5555】\n"
        "#4：[android.img]…（0/1）【framework.mod|apps.mod】00002……（0/2）【android_part2.matha】"
    )
    _check(src, "2. Android 系统构建")


# ============================================================
# 3. 软件应用构建（多模块代码块）
# ============================================================

def test_app_build():
    """软件应用构建：代码块多模块 + 段循环 + 子文件 + 文件结束标记。"""
    src = (
        "#：{\n"
        "   #1：【初始化项目】\n"
        "   @1:名称=MyApp，版本=1.0\n"
        "   #2：【编译前端】>>【编译后端】>>【打包发布】\n"
        "   #3：[MyApp.exe]…（0/1）【frontend.mod|backend.mod】00003……（0/2）【app_part2.matha】\n"
        "   #：【文件】\n"
        "}"
    )
    _check(src, "3. 软件应用构建（多模块）")


# ============================================================
# 4. CI/CD 流水线（链式 + 端口 + URL）
# ============================================================

def test_cicd_pipeline():
    """CI/CD 流水线：链式命令 + URL 源码拉取 + 端口测试服务。"""
    src = "#1：【拉取代码 https://gitlab.com/repo.git】>>【运行测试 localhost:8080】>>【部署生产】"
    _check(src, "4. CI/CD 流水线")


if __name__ == "__main__":
    test_windows_build()
    test_android_build()
    test_app_build()
    test_cicd_pipeline()
    print("\n=== 全部系统构建测试完成 ===")
