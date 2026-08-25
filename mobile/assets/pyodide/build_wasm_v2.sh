#!/bin/bash
# Matha WebAssembly 完整打包脚本 v2.0
# 支持完整编译、优化、测试和部署

set -e

# ========== 配置 ==========
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WASM_DIR="$PROJECT_ROOT/mobile/assets/pyodide"
EMSDK_DIR="$HOME/.emsdk"
PYTHON_WASM_DIR="$WASM_DIR/python-wasm"
MATHA_WASM_DIR="$WASM_DIR/matha-wasm"
DIST_DIR="$WASM_DIR/dist"

# 版本信息
MATHA_VERSION="4.4.18"
PYODIDE_VERSION="0.24.1"
PYTHON_VERSION=$(python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 || echo "3.11")

# Matha 模块列表
MATHA_MODULES=(
    "calculus_symbolic"
    "linear_algebra"
    "probability_stats"
    "graph"
    "computer_science"
    "repl"
    "llm"
    "perf_profiler"
    "doc_generator"
)

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ========== 日志函数 ==========
log_info() {
    echo -e "${GREEN}[Matha WASM v${MATHA_VERSION}]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[Matha WASM]${NC} $1"
}

log_error() {
    echo -e "${RED}[Matha WASM]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[Matha WASM]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_fail() {
    echo -e "${RED}[✗]${NC} $1"
}

# ========== 检查命令 ==========
check_command() {
    if ! command -v "$1" &> /dev/null; then
        return 1
    fi
    return 0
}

# ========== 环境检查 ==========
check_environment() {
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_step "  环境检查"
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local errors=0
    
    # Python
    if check_command python3; then
        PYTHON_VERSION=$(python3 --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
        log_success "Python: $PYTHON_VERSION"
    else
        log_fail "Python 未安装，请安装 Python 3.8+"
        ((errors++))
    fi
    
    # Git
    if check_command git; then
        log_success "Git: $(git --version)"
    else
        log_fail "Git 未安装"
        ((errors++))
    fi
    
    # Emscripten
    if [ -f "$EMSDK_DIR/emsdk_env.sh" ]; then
        source "$EMSDK_DIR/emsdk_env.sh" 2>/dev/null || true
        if check_command emcc; then
            log_success "Emscripten: $(emcc --version | head -1)"
        else
            log_warn "Emscripten 已安装但不可用"
        fi
    else
        log_warn "Emscripten 未安装"
    fi
    
    # Pyodide
    if check_command pyodide; then
        log_success "Pyodide: $(pyodide --version 2>/dev/null || echo 'installed')"
    else
        log_warn "Pyodide CLI 未安装"
    fi
    
    # Node.js
    if check_command node; then
        log_success "Node.js: $(node --version)"
    else
        log_warn "Node.js 未安装"
    fi
    
    if [ $errors -gt 0 ]; then
        log_error "环境检查失败，请安装缺失的依赖"
        return 1
    fi
    
    log_success "环境检查完成"
    return 0
}

# ========== 安装 Emscripten ==========
install_emsdk() {
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_step "  安装 Emscripten"
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ -f "$EMSDK_DIR/emsdk_env.sh" ]; then
        log_success "Emscripten 已安装: $EMSDK_DIR"
        source "$EMSDK_DIR/emsdk_env.sh"
        return 0
    fi
    
    log_info "克隆 EMSDK..."
    git clone https://github.com/emscripten-core/emsdk.git "$EMSDK_DIR"
    
    log_info "安装 Emscripten..."
    cd "$EMSDK_DIR"
    ./emsdk install latest
    
    log_info "激活 Emscripten..."
    ./emsdk activate latest
    
    source "$EMSDK_DIR/emsdk_env.sh"
    
    log_success "Emscripten 安装完成: $(emcc --version)"
}

# ========== 创建目录结构 ==========
setup_directories() {
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_step "  创建目录结构"
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    mkdir -p "$WASM_DIR"
    mkdir -p "$WASM_DIR/packages"
    mkdir -p "$WASM_DIR/third_party"
    mkdir -p "$WASM_DIR/dist"
    mkdir -p "$PYTHON_WASM_DIR"
    mkdir -p "$MATHA_WASM_DIR"
    
    log_success "目录创建完成"
    log_info "  WASM_DIR: $WASM_DIR"
    log_info "  DIST_DIR: $DIST_DIR"
}

# ========== 打包 Matha Python 模块 ==========
package_matha_modules() {
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_step "  打包 Matha Python 模块"
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    cd "$MATHA_WASM_DIR"
    
    # 创建包结构
    rm -rf matha
    mkdir -p matha/stdlib
    mkdir -p matha/domains
    mkdir -p matha/tools
    mkdir -p matha/intent
    
    local packaged=0
    local skipped=0
    
    # 复制核心模块
    for module in "${MATHA_MODULES[@]}"; do
        # 检查 stdlib
        SRC_FILE="$PROJECT_ROOT/src/stdlib/${module}.py"
        if [ -f "$SRC_FILE" ]; then
            cp "$SRC_FILE" "matha/stdlib/${module}.py"
            log_success "已打包: $module (stdlib)"
            ((packaged++))
            continue
        fi
        
        # 检查 domains
        SRC_FILE="$PROJECT_ROOT/src/domains/${module}.py"
        if [ -f "$SRC_FILE" ]; then
            cp "$SRC_FILE" "matha/domains/${module}.py"
            log_success "已打包: $module (domains)"
            ((packaged++))
            continue
        fi
        
        # 检查 tools
        SRC_FILE="$PROJECT_ROOT/src/tools/${module}.py"
        if [ -f "$SRC_FILE" ]; then
            cp "$SRC_FILE" "matha/tools/${module}.py"
            log_success "已打包: $module (tools)"
            ((packaged++))
            continue
        fi
        
        # 检查 intent
        SRC_FILE="$PROJECT_ROOT/src/intent/${module}.py"
        if [ -f "$SRC_FILE" ]; then
            cp "$SRC_FILE" "matha/intent/${module}.py"
            log_success "已打包: $module (intent)"
            ((packaged++))
            continue
        fi
        
        log_warn "未找到模块: $module"
        ((skipped++))
    done
    
    # 创建 __init__.py 文件
    cat > matha/__init__.py << EOF
"""Matha 数学计算库 - WebAssembly 版本"""
__version__ = "${MATHA_VERSION}"
__pyodide_version__ = "${PYODIDE_VERSION}"

from . import stdlib
from . import domains
from . import tools
from . import intent
EOF

    cat > matha/stdlib/__init__.py << 'EOF'
"""Matha 标准库"""
from . import calculus_symbolic
from . import linear_algebra
from . import probability_stats
from . import graph
EOF

    cat > matha/domains/__init__.py << 'EOF'
"""Matha 领域模块"""
from . import graph as graph_domain
EOF

    cat > matha/tools/__init__.py << 'EOF'
"""Matha 工具模块"""
from . import doc_generator
from . import perf_profiler
EOF

    cat > matha/intent/__init__.py << 'EOF'
"""Matha 意图识别模块"""
from . import llm_parser
EOF

    # 创建打包清单
    cat > package.json << EOF
{
  "name": "matha-wasm",
  "version": "${MATHA_VERSION}",
  "description": "Matha 数学计算库 WebAssembly 版本",
  "main": "matha/__init__.py",
  "pyodide": {
    "packageType": "stdlib",
    "version": "${PYODIDE_VERSION}",
    "pythonVersion": "${PYTHON_VERSION}",
    "modules": [$(printf '"%s",' "${MATHA_MODULES[@]}" | sed 's/,$//')]
  },
  "dependencies": {
    "numpy": ">=1.24.0",
    "scipy": ">=1.10.0"
  }
}
EOF

    log_success "Matha 模块打包完成: $packaged 个模块, $skipped 个跳过"
}

# ========== 构建 WebAssembly ==========
build_wasm() {
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_step "  构建 WebAssembly"
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # 确保 Emscripten 可用
    if [ ! -f "$EMSDK_DIR/emsdk_env.sh" ]; then
        install_emsdk
    fi
    source "$EMSDK_DIR/emsdk_env.sh"
    
    cd "$MATHA_WASM_DIR"
    
    # 检查 pyodide-pack
    if ! check_command pyodide-pack; then
        log_info "安装 pyodide-pack..."
        pip3 install pyodide-pack
    fi
    
    # 使用 pyodide-pack 打包
    log_info "开始打包..."
    pyodide-pack package/ matha-wasm.tar
    
    # 移动到输出目录
    if [ -f "matha-wasm.tar" ]; then
        mv "matha-wasm.tar" "$WASM_DIR/packages/matha-wasm.tar"
        log_success "WASM 包已生成: matha-wasm.tar"
        
        # 显示文件大小
        local size=$(du -h "$WASM_DIR/packages/matha-wasm.tar" | cut -f1)
        log_info "文件大小: $size"
    else
        log_fail "WASM 包生成失败"
        return 1
    fi
    
    # 优化 WASM 文件（可选）
    if check_command wasm-opt; then
        log_info "优化 WASM 文件..."
        wasm-opt -O3 "$WASM_DIR/packages/matha-wasm.tar" -o "$WASM_DIR/packages/matha-wasm.optimized.tar" 2>/dev/null || true
        if [ -f "$WASM_DIR/packages/matha-wasm.optimized.tar" ]; then
            mv "$WASM_DIR/packages/matha-wasm.optimized.tar" "$WASM_DIR/packages/matha-wasm.tar"
            log_success "WASM 优化完成"
        fi
    fi
    
    log_success "WebAssembly 构建完成"
}

# ========== 生成构建配置 ==========
generate_build_config() {
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_step "  生成构建配置"
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # 生成 build_config.json
    cat > "$WASM_DIR/build_config.json" << EOF
{
  "version": "${MATHA_VERSION}",
  "pyodideVersion": "${PYODIDE_VERSION}",
  "pythonVersion": "${PYTHON_VERSION}",
  "modules": [$(printf '"%s",' "${MATHA_MODULES[@]}" | sed 's/,$//')],
  "outputDir": "${WASM_DIR}",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "environment": {
    "emsdk": "${EMSDK_DIR}",
    "node": "$(node --version 2>/dev/null || echo 'not installed')",
    "pip": "$(pip3 --version 2>/dev/null || echo 'not installed')"
  }
}
EOF
    
    log_success "构建配置已生成"
}

# ========== 验证构建结果 ==========
validate_build() {
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_step "  验证构建结果"
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local errors=0
    
    # 检查必要文件
    local required_files=(
        "$WASM_DIR/packages/matha-wasm.tar"
        "$WASM_DIR/build_config.json"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            local size=$(du -h "$file" | cut -f1)
            log_success "✓ $file ($size)"
        else
            log_fail "✗ 缺少: $file"
            ((errors++))
        fi
    done
    
    # 检查目录结构
    local required_dirs=(
        "$WASM_DIR/packages"
        "$WASM_DIR/third_party"
        "$WASM_DIR/dist"
    )
    
    for dir in "${required_dirs[@]}"; do
        if [ -d "$dir" ]; then
            log_success "✓ $dir/"
        else
            log_warn "⚠ 目录不存在: $dir"
        fi
    done
    
    # 检查模块文件
    local module_count=$(find "$MATHA_WASM_DIR/matha" -name "*.py" 2>/dev/null | wc -l)
    log_info "打包模块数: $module_count"
    
    if [ $errors -eq 0 ]; then
        log_success "验证通过"
        return 0
    else
        log_fail "验证失败，有 $errors 个错误"
        return 1
    fi
}

# ========== 生成部署包 ==========
generate_deploy_package() {
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_step "  生成部署包"
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local deploy_dir="$WASM_DIR/dist"
    mkdir -p "$deploy_dir"
    
    # 复制构建产物
    cp -r "$WASM_DIR/packages/"* "$deploy_dir/" 2>/dev/null || true
    cp "$WASM_DIR/build_config.json" "$deploy_dir/" 2>/dev/null || true
    
    # 生成部署说明
    cat > "$deploy_dir/README.md" << EOF
# Matha WebAssembly 部署包

## 版本信息
- Matha 版本: ${MATHA_VERSION}
- Pyodide 版本: ${PYODIDE_VERSION}
- Python 版本: ${PYTHON_VERSION}
- 构建时间: $(date -u +'%Y-%m-%d %H:%M:%S UTC')

## 包含文件
\`\`\`
matha-wasm.tar          # WebAssembly 包
build_config.json       # 构建配置
\`\`\`

## 使用方法

### 在 Flutter 中使用
\`\`\`dart
final pyodide = PyodideController();
await pyodide.initialize(
  packages: {'matha-wasm': '${MATHA_VERSION}'},
);
\`\`\`

### 直接加载
\`\`\`javascript
const pyodide = await loadPyodide();
await pyodide.loadPackage('matha-wasm');
\`\`\`

## 依赖
- Flutter SDK >= 3.0.0
- Python >= 3.8
- Emscripten (用于编译)
EOF
    
    log_success "部署包已生成: $deploy_dir/"
}

# ========== 清理构建文件 ==========
clean_build() {
    log_info "清理构建文件..."
    
    rm -rf "$PYTHON_WASM_DIR"
    rm -rf "$MATHA_WASM_DIR"
    rm -rf "$WASM_DIR/packages"
    rm -rf "$WASM_DIR/dist"
    rm -f "$WASM_DIR/build_config.json"
    
    log_success "清理完成"
}

# ========== 显示帮助 ==========
show_help() {
    echo "Matha WebAssembly 完整打包工具 v${MATHA_VERSION}"
    echo ""
    echo "用法:"
    echo "  ./build_wasm.sh [选项]"
    echo ""
    echo "选项:"
    echo "  --full        完整构建（环境检查 + 安装 + 编译 + 打包）"
    echo "  --package     仅打包（需要已安装环境）"
    echo "  --build       仅构建 WASM"
    echo "  --validate    验证构建结果"
    echo "  --deploy      生成部署包"
    echo "  --clean       清理构建文件"
    echo "  --help        显示此帮助"
    echo ""
    echo "示例:"
    echo "  ./build_wasm.sh --full    # 完整构建"
    echo "  ./build_wasm.sh --package # 仅打包"
    echo "  ./build_wasm.sh --validate # 验证结果"
}

# ========== 主函数 ==========
main() {
    local mode="${1:---full}"
    
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_step "  Matha WebAssembly 打包工具 v${MATHA_VERSION}"
    log_step "  Pyodide: ${PYODIDE_VERSION} | Python: ${PYTHON_VERSION}"
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_step ""
    
    case "$mode" in
        --full)
            check_environment || exit 1
            install_emsdk
            setup_directories
            package_matha_modules
            build_wasm
            generate_build_config
            validate_build
            generate_deploy_package
            ;;
        --package)
            setup_directories
            package_matha_modules
            build_wasm
            generate_build_config
            validate_build
            ;;
        --build)
            setup_directories
            build_wasm
            ;;
        --validate)
            validate_build
            ;;
        --deploy)
            generate_deploy_package
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
    
    log_step ""
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_success "  打包完成!"
    log_step "  输出目录: $WASM_DIR"
    log_step "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# 执行
main "$@"
