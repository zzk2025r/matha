#!/bin/bash
# Matha WebAssembly 打包脚本
# 一键完成环境配置和 WASM 打包

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WASM_DIR="$PROJECT_ROOT/mobile/assets/pyodide"
EMSDK_DIR="$HOME/.emsdk"
PYTHON_WASM_DIR="$WASM_DIR/python-wasm"
MATHA_WASM_DIR="$WASM_DIR/matha-wasm"

# Matha 模块列表
MATHA_MODULES=(
    "calculus_symbolic"
    "linear_algebra"
    "probability_stats"
    "graph"
    "computer_science"
)

# 日志函数
log_info() {
    echo -e "${GREEN}[Matha WASM]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[Matha WASM]${NC} $1"
}

log_error() {
    echo -e "${RED}[Matha WASM]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "未找到命令: $1"
        return 1
    fi
    return 0
}

# 检查 Python 版本
check_python() {
    log_info "检查 Python 版本..."
    if ! check_command python3; then
        log_error "未找到 python3，请安装 Python 3.8+"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
    log_info "Python 版本: $PYTHON_VERSION"
    
    if (( $(echo "$PYTHON_VERSION < 3.8" | bc -l) )); then
        log_error "Python 版本需要 >= 3.8"
        exit 1
    fi
}

# 安装/更新 Emscripten
install_emsdk() {
    log_info "检查 Emscripten 环境..."
    
    if [ ! -d "$EMSDK_DIR" ]; then
        log_info "克隆 EMSDK..."
        git clone https://github.com/emscripten-core/emsdk.git "$EMSDK_DIR"
    fi
    
    cd "$EMSDK_DIR"
    
    if [ ! -f ".emscripten" ]; then
        log_info "安装 Emscripten..."
        ./emsdk install latest
    fi
    
    log_info "激活 Emscripten..."
    ./emsdk activate latest
    
    # 设置环境变量
    source "$EMSDK_DIR/emsdk_env.sh"
    
    log_info "Emscripten 版本: $(emcc --version)"
}

# 创建目录结构
setup_directories() {
    log_info "创建目录结构..."
    
    mkdir -p "$WASM_DIR"
    mkdir -p "$PYTHON_WASM_DIR"
    mkdir -p "$MATHA_WASM_DIR"
    mkdir -p "$WASM_DIR/packages"
    mkdir -p "$WASM_DIR/third_party"
    
    log_info "目录创建完成"
}

# 编译 Python for WebAssembly
compile_python_wasm() {
    log_info "编译 Python for WebAssembly..."
    
    cd "$PYTHON_WASM_DIR"
    
    # 下载 Python 源码
    if [ ! -d "Python-$PYTHON_VERSION" ]; then
        log_info "下载 Python $PYTHON_VERSION 源码..."
        curl -O "https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz"
        tar -xzf "Python-$PYTHON_VERSION.tgz"
    fi
    
    # 配置和编译
    cd "Python-$PYTHON_VERSION"
    
    if [ ! -f "Makefile" ]; then
        log_info "配置 Python WebAssembly 构建..."
        emconfigure ./configure \
            --host=wasm32 \
            --build=x86_64-linux-gnu \
            --enable-framework \
            --disable-shared \
            --enable-optimizations
    fi
    
    log_info "编译 Python (这可能需要几分钟)..."
    emmake make -j$(nproc)
    
    log_info "Python WebAssembly 编译完成"
}

# 打包 Matha 模块
package_matha_modules() {
    log_info "打包 Matha 核心模块..."
    
    cd "$MATHA_WASM_DIR"
    
    # 创建 Matha 包结构
    mkdir -p matha/stdlib
    mkdir -p matha/domains
    
    # 复制模块文件
    for module in "${MATHA_MODULES[@]}"; do
        log_info "打包模块: $module"
        
        # 从项目源文件复制
        SRC_FILE="$PROJECT_ROOT/src/stdlib/${module}.py"
        if [ -f "$SRC_FILE" ]; then
            cp "$SRC_FILE" "matha/stdlib/${module}.py"
            log_info "✓ 已复制 $module"
        else
            log_warn "✗ 未找到 $module"
        fi
    done
    
    # 创建 __init__.py
    cat > matha/__init__.py << 'EOF'
"""Matha 数学计算库 - WebAssembly 版本"""
__version__ = "4.4.16"
EOF

    cat > matha/stdlib/__init__.py << 'EOF'
"""Matha 标准库"""
from . import calculus_symbolic
from . import linear_algebra
from . import probability_stats
from . import graph
EOF

    # 创建打包清单
    cat > package.json << 'EOF'
{
  "name": "matha-wasm",
  "version": "4.4.16",
  "description": "Matha 数学计算库 WebAssembly 版本",
  "main": "matha/__init__.py",
  "pyodide": {
    "packageType": "stdlib",
    "version": "0.24.1"
  }
}
EOF
    
    log_info "Matha 模块打包完成"
}

# 使用 Pyodide 打包
build_with_pyodide() {
    log_info "使用 Pyodide 打包..."
    
    cd "$MATHA_WASM_DIR"
    
    # 检查是否已安装 pyodide-pack
    if ! command -v pyodide-pack &> /dev/null; then
        log_info "安装 pyodide-pack..."
        pip3 install pyodide-pack
    fi
    
    # 打包
    log_info "开始打包..."
    pyodide-pack package/ matha-wasm.tar
    
    # 重命名为正确的格式
    if [ -f "matha-wasm.tar" ]; then
        mv "matha-wasm.tar" "$WASM_DIR/packages/matha-wasm.tar"
        log_info "✓ 打包完成: matha-wasm.tar"
    fi
    
    log_info "Pyodide 打包完成"
}

# 生成构建配置
generate_build_config() {
    log_info "生成构建配置..."
    
    cat > "$WASM_DIR/build_config.json" << EOF
{
  "version": "4.4.16",
  "pyodideVersion": "0.24.1",
  "pythonVersion": "$PYTHON_VERSION",
  "modules": $(printf '%s\n' "${MATHA_MODULES[@]}" | jq -R . | jq -s .),
  "outputDir": "$WASM_DIR",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
}
EOF
    
    log_info "构建配置已生成"
}

# 验证打包结果
validate_build() {
    log_info "验证构建结果..."
    
    local errors=0
    
    # 检查必要文件
    local files=(
        "$WASM_DIR/packages/matha-wasm.tar"
        "$WASM_DIR/build_config.json"
    )
    
    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            log_info "✓ $file"
        else
            log_error "✗ 缺少: $file"
            ((errors++))
        fi
    done
    
    # 检查目录
    local dirs=(
        "$WASM_DIR/packages"
        "$WASM_DIR/third_party"
    )
    
    for dir in "${dirs[@]}"; do
        if [ -d "$dir" ]; then
            log_info "✓ $dir"
        else
            log_warn "⚠ 目录不存在: $dir"
        fi
    done
    
    if [ $errors -eq 0 ]; then
        log_info "✓ 验证通过"
        return 0
    else
        log_error "✗ 验证失败，有 $errors 个错误"
        return 1
    fi
}

# 显示帮助
show_help() {
    echo "Matha WebAssembly 打包工具"
    echo ""
    echo "用法:"
    echo "  ./build_wasm.sh [选项]"
    echo ""
    echo "选项:"
    echo "  --full        完整构建（安装环境 + 编译 + 打包）"
    echo "  --package     仅打包（需要已安装环境）"
    echo "  --validate    验证构建结果"
    echo "  --clean       清理构建文件"
    echo "  --help        显示此帮助"
    echo ""
    echo "示例:"
    echo "  ./build_wasm.sh --full    # 完整构建"
    echo "  ./build_wasm.sh --package # 仅打包"
}

# 清理构建文件
clean_build() {
    log_info "清理构建文件..."
    
    rm -rf "$PYTHON_WASM_DIR"
    rm -rf "$MATHA_WASM_DIR"
    rm -rf "$WASM_DIR/packages"
    rm -f "$WASM_DIR/build_config.json"
    
    log_info "✓ 清理完成"
}

# 主函数
main() {
    local mode="${1:---full}"
    
    log_info "========================================"
    log_info "  Matha WebAssembly 打包工具 v4.4.16"
    log_info "========================================"
    log_info ""
    
    case "$mode" in
        --full)
            check_python
            install_emsdk
            setup_directories
            compile_python_wasm
            package_matha_modules
            build_with_pyodide
            generate_build_config
            validate_build
            ;;
        --package)
            setup_directories
            package_matha_modules
            build_with_pyodide
            generate_build_config
            validate_build
            ;;
        --validate)
            validate_build
            ;;
        --clean)
            clean_build
            ;;
        --help|-h)
            show_help
            ;;
        *)
            log_error "未知选项: $mode"
            show_help
            exit 1
            ;;
    esac
    
    log_info ""
    log_info "========================================"
    log_info "  打包完成!"
    log_info "========================================"
}

# 执行
main "$@"
