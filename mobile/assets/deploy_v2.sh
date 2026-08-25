#!/bin/bash
# Matha 移动端自动化部署脚本 v2.0
# 一键完成环境配置、打包和部署

set -e

# ========== 配置 ==========
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
MOBILE_DIR="$PROJECT_ROOT/mobile"
WASM_DIR="$MOBILE_DIR/assets/pyodide"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

# 版本信息
MATHA_VERSION="4.4.18"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ========== 日志函数 ==========
log_info() {
    echo -e "${BLUE}[Matha Deploy]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# ========== 检查环境 ==========
check_environment() {
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "  检查开发环境"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local has_flutter=false
    local has_python=false
    local has_git=false
    
    # Flutter
    if command -v flutter &> /dev/null; then
        FLUTTER_VERSION=$(flutter --version | grep -oE 'Flutter [0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log_success "Flutter: $FLUTTER_VERSION"
        has_flutter=true
    else
        log_warn "Flutter 未安装，将跳过 Flutter 构建"
    fi
    
    # Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | grep -oE '[0-9]+\.[0-9]+')
        log_success "Python: $PYTHON_VERSION"
        has_python=true
    else
        log_error "Python 未安装，这是必需依赖"
        exit 1
    fi
    
    # Git
    if command -v git &> /dev/null; then
        log_success "Git: $(git --version)"
        has_git=true
    else
        log_warn "Git 未安装"
    fi
    
    echo ""
}

# ========== 安装依赖 ==========
install_dependencies() {
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "  安装项目依赖"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Flutter 依赖
    if [ "$has_flutter" = true ]; then
        log_info "安装 Flutter 依赖..."
        cd "$MOBILE_DIR"
        flutter pub get
        log_success "Flutter 依赖安装完成"
    fi
    
    # Python 依赖
    log_info "安装 Python 依赖..."
    pip3 install pyodide-pack websockets emsdk
    
    log_success "Python 依赖安装完成"
    echo ""
}

# ========== 构建 WebAssembly ==========
build_webassembly() {
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "  构建 WebAssembly"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ -f "$WASM_DIR/build_wasm_v2.sh" ]; then
        cd "$WASM_DIR"
        bash build_wasm_v2.sh --package
        log_success "WebAssembly 构建完成"
    else
        log_warn "WASM 打包脚本不存在，跳过 WASM 构建"
    fi
    echo ""
}

# ========== 运行测试 ==========
run_tests() {
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "  运行测试"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    cd "$PROJECT_ROOT"
    
    log_info "运行 Python 测试..."
    python3 -B tests/run_all_tests.py
    
    log_success "测试完成"
    echo ""
}

# ========== 构建 Flutter ==========
build_flutter() {
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "  构建 Flutter 应用"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ "$has_flutter" != true ]; then
        log_warn "Flutter 未安装，跳过 Flutter 构建"
        return
    fi
    
    cd "$MOBILE_DIR"
    
    # 构建 Web 版本
    log_info "构建 Web 版本..."
    flutter build web --release --web-renderer canvaskit
    
    log_success "Web 版本构建完成: build/web/"
    echo ""
}

# ========== 生成部署包 ==========
generate_deploy_package() {
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "  生成部署包"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # 创建部署目录
    mkdir -p "$DEPLOY_DIR"
    
    # 复制构建产物
    if [ -d "$MOBILE_DIR/build/web" ]; then
        cp -r "$MOBILE_DIR/build/web" "$DEPLOY_DIR/"
        log_success "Web 构建产物已复制"
    fi
    
    # 复制 WASM 包
    if [ -d "$WASM_DIR/packages" ]; then
        mkdir -p "$DEPLOY_DIR/wasm"
        cp -r "$WASM_DIR/packages/"* "$DEPLOY_DIR/wasm/" 2>/dev/null || true
        log_success "WASM 包已复制"
    fi
    
    # 复制构建配置
    if [ -f "$WASM_DIR/build_config.json" ]; then
        cp "$WASM_DIR/build_config.json" "$DEPLOY_DIR/"
        log_success "构建配置已复制"
    fi
    
    # 生成部署说明
    cat > "$DEPLOY_DIR/README.md" << EOF
# Matha 移动端部署包

## 版本信息
- 版本: ${MATHA_VERSION}
- 构建时间: $(date -u +'%Y-%m-%d %H:%M:%S UTC')
- 平台: $(uname -s)

## 目录结构
\`\`\`
deploy/
├── web/              # Flutter Web 构建产物
├── wasm/             # WebAssembly 包
├── build_config.json # 构建配置
└── README.md         # 本文件
\`\`\`

## 快速启动

### 方式一：本地服务器
\`\`\`bash
cd deploy
python3 -m http.server 8080
# 访问 http://localhost:8080
\`\`\`

### 方式二：Firebase 部署
\`\`\`bash
firebase deploy --only hosting
\`\`\`

### 方式三：Netlify 部署
\`\`\`bash
netlify deploy --prod --dir=web
\`\`\`

## 环境要求
- Flutter SDK >= 3.0.0
- Python >= 3.8
- Emscripten (用于 WASM 打包)

## 故障排查

### WebSocket 连接失败
1. 检查服务器地址是否正确
2. 确认服务器支持 WebSocket
3. 查看浏览器控制台日志

### Pyodide 加载超时
1. 检查网络连接
2. 确认 CDN 可访问
3. 查看浏览器控制台日志

### WASM 打包失败
1. 确保已安装 Emscripten
2. 检查 Python 版本兼容性
3. 查看构建日志
EOF

    log_success "部署包生成完成: $DEPLOY_DIR/"
    echo ""
}

# ========== 显示总结 ==========
show_summary() {
    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_success "  部署完成!"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    log_info "  构建产物: $DEPLOY_DIR/"
    log_info "  Web 版本: $DEPLOY_DIR/web/"
    log_info "  WASM 包:  $DEPLOY_DIR/wasm/"
    echo ""
    log_info "  下一步:"
    log_info "    1. 启动本地服务器: cd $DEPLOY_DIR && python3 -m http.server 8080"
    log_info "    2. 访问: http://localhost:8080"
    log_info "    3. 测试 WebSocket 连接和 Pyodide 功能"
    echo ""
}

# ========== 主函数 ==========
main() {
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "  Matha 移动端自动化部署脚本 v${MATHA_VERSION}"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # 1. 检查环境
    check_environment
    
    # 2. 安装依赖
    install_dependencies
    
    # 3. 构建 WebAssembly
    build_webassembly
    
    # 4. 运行测试
    run_tests
    
    # 5. 构建 Flutter
    build_flutter
    
    # 6. 生成部署包
    generate_deploy_package
    
    # 7. 显示总结
    show_summary
}

# 执行
main
