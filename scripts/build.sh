#!/bin/bash
# ============================================================
# Matha 一键打包脚本 (Linux/macOS)
# ============================================================
# 用法:
#   ./build.sh              打包所有可执行文件
#   ./build.sh matha        仅打包 matha REPL
#   ./build.sh matha-cc     仅打包 matha-cc 编译器
#   ./build.sh clean        清理构建目录
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"
PYTHON="${PYTHON:-python3}"

echo "============================================================"
echo "Matha 可执行文件打包脚本"
echo "============================================================"
echo ""

# 检查 Python
$PYTHON --version || { echo "[ERROR] 未找到 Python"; exit 1; }
$PYTHON --version

# 检查 PyInstaller
$PYTHON -m pip show pyinstaller &>/dev/null || {
    echo "[INFO] 安装 PyInstaller..."
    $PYTHON -m pip install pyinstaller
}

# 处理参数
case "${1:-all}" in
    clean)
        echo "[INFO] 清理构建目录..."
        rm -rf "$BUILD_DIR" "$DIST_DIR"
        echo "[OK] 清理完成"
        exit 0
        ;;
    matha)
        TARGETS="matha"
        ;;
    matha-cc)
        TARGETS="matha-cc"
        ;;
    *)
        TARGETS="matha matha-cc"
        ;;
esac

# 清理旧构建
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$DIST_DIR"

echo ""
echo "[INFO] 开始构建..."
echo ""

for TARGET in $TARGETS; do
    echo "============================================================"
    echo "构建: $TARGET"
    echo "============================================================"

    if [ "$TARGET" = "matha" ]; then
        $PYTHON -m PyInstaller --clean --noconfirm \
            --distpath "$DIST_DIR/matha" \
            --workpath "$BUILD_DIR/matha" \
            --specpath "$PROJECT_ROOT" \
            "$PROJECT_ROOT/matha.spec"
    elif [ "$TARGET" = "matha-cc" ]; then
        $PYTHON -m PyInstaller --clean --noconfirm \
            --distpath "$DIST_DIR/matha-cc" \
            --workpath "$BUILD_DIR/matha-cc" \
            --specpath "$PROJECT_ROOT" \
            "$PROJECT_ROOT/matha-cc.spec"
    fi

    echo "[OK] $TARGET 构建成功"
    ls -lh "$DIST_DIR/$TARGET"/
    echo ""
done

echo "============================================================"
echo "构建完成！"
echo "============================================================"
echo ""
echo "可执行文件位置:"
for TARGET in $TARGETS; do
    echo "  $DIST_DIR/$TARGET/$TARGET"
done
echo ""
echo "使用方法:"
echo "  matha                          # 启动 REPL"
echo "  matha eval 'sin(pi)'           # 计算表达式"
echo "  matha run demo.matha           # 运行源文件"
echo "  matha-cc compile demo.matha -o c  # 编译到 C"
echo ""
