#!/bin/bash
# Matha Flutter SDK 安装脚本
# 自动检测系统并安装 Flutter SDK

set -e

# ========== 颜色定义 ==========
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ========== 版本配置 ==========
FLUTTER_VERSION="3.24.0"
FLUTTER_CHANNEL="stable"
INSTALL_DIR="${HOME}/flutter"
CACHE_DIR="${HOME}/.cache/flutter"

# ========== 日志函数 ==========
log_info() {
    echo -e "${BLUE}[Flutter Install]${NC} $1"
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

# ========== 检测系统 ==========
detect_os() {
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    case $os in
        linux*)
            echo "linux"
            ;;
        darwin*)
            echo "macos"
            ;;
        msys*|cygwin*|mingw*)
            echo "windows"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# ========== 检查依赖 ==========
check_dependencies() {
    log_info "检查系统依赖..."
    
    local missing=()
    
    # Git
    if ! command -v git &> /dev/null; then
        missing+=("git")
    fi
    
    # Python (可选，用于 flutter doctor)
    if ! command -v python3 &> /dev/null; then
        log_warn "Python 未安装（可选依赖）"
    fi
    
    # curl/wget
    if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
        missing+=("curl or wget")
    fi
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "缺少依赖: ${missing[*]}"
        log_info "请先安装缺失的依赖"
        return 1
    fi
    
    log_success "依赖检查通过"
    return 0
}

# ========== 安装 Git ==========
install_git() {
    log_info "检查 Git..."
    if ! command -v git &> /dev/null; then
        log_info "正在安装 Git..."
        local os=$(detect_os)
        case $os in
            linux)
                sudo apt-get update
                sudo apt-get install -y git
                ;;
            macos)
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                brew install git
                ;;
            windows)
                log_warn "请在 Windows 上手动安装 Git: https://git-scm.com/download/win"
                return 1
                ;;
        esac
    fi
    log_success "Git 已安装: $(git --version)"
}

# ========== 下载 Flutter ==========
download_flutter() {
    log_info "下载 Flutter SDK ${FLUTTER_VERSION}..."
    
    mkdir -p "${CACHE_DIR}"
    cd "${CACHE_DIR}"
    
    local archive_name="flutter_${FLUTTER_VERSION}-${FLUTTER_CHANNEL}-linux-x64.tar.xz"
    local download_url="https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_${FLUTTER_VERSION}-${FLUTTER_CHANNEL}-linux-x64.tar.xz"
    
    # 检查是否已下载
    if [ -f "${CACHE_DIR}/${archive_name}" ]; then
        log_info "已找到缓存文件: ${archive_name}"
    else
        log_info "正在下载 Flutter SDK..."
        log_info "下载地址: ${download_url}"
        
        if command -v curl &> /dev/null; then
            curl -L "${download_url}" -o "${archive_name}"
        else
            wget -O "${archive_name}" "${download_url}"
        fi
        
        log_success "下载完成"
    fi
    
    # 解压
    log_info "正在解压..."
    tar xf "${archive_name}" -C "${INSTALL_DIR}/.."
    
    log_success "Flutter SDK 已解压到: ${INSTALL_DIR}"
}

# ========== 配置环境变量 ==========
setup_environment() {
    log_info "配置环境变量..."
    
    local shell_rc=""
    local os=$(detect_os)
    
    case $os in
        linux)
            shell_rc="${HOME}/.bashrc"
            if [ -f "${HOME}/.zshrc" ]; then
                shell_rc="${HOME}/.zshrc"
            fi
            ;;
        macos)
            shell_rc="${HOME}/.zshrc"
            if [ ! -f "${shell_rc}" ]; then
                shell_rc="${HOME}/.bashrc"
            fi
            ;;
        windows)
            log_info "Windows 环境，请手动添加环境变量"
            log_info "  Flutter 路径: ${INSTALL_DIR}/bin"
            log_info "  添加到 PATH"
            return 0
            ;;
    esac
    
    # 添加 Flutter 到 PATH
    if ! grep -q "export PATH=\"\$PATH:${INSTALL_DIR}/bin\"" "${shell_rc}" 2>/dev/null; then
        echo "" >> "${shell_rc}"
        echo "# Flutter SDK" >> "${shell_rc}"
        echo "export PATH=\"\$PATH:${INSTALL_DIR}/bin\"" >> "${shell_rc}"
        log_success "已添加 Flutter 到 ${shell_rc}"
    fi
    
    # 启用 Flutter analytics（可选）
    # flutter config --enable-analytics
    
    log_info "请运行以下命令使环境变量生效:"
    log_info "  source ${shell_rc}"
}

# ========== 运行 Flutter doctor ==========
run_flutter_doctor() {
    log_info "运行 Flutter Doctor..."
    
    export PATH="${INSTALL_DIR}/bin:$PATH"
    
    flutter doctor
    
    log_info ""
    log_info "如需安装缺失的依赖，请运行:"
    log_info "  flutter precache"
    log_info "  flutter doctor --android-licenses"
}

# ========== 显示帮助 ==========
show_help() {
    echo "Matha Flutter SDK 安装脚本"
    echo ""
    echo "用法:"
    echo "  ./install_flutter.sh [选项]"
    echo ""
    echo "选项:"
    echo "  --channel   安装指定频道 (stable/dev/canary)"
    echo "  --version   安装指定版本"
    echo "  --help      显示此帮助"
    echo ""
    echo "示例:"
    echo "  ./install_flutter.sh"
    echo "  ./install_flutter.sh --channel stable"
    echo "  ./install_flutter.sh --version 3.24.0"
}

# ========== 主函数 ==========
main() {
    local channel="stable"
    local version="$FLUTTER_VERSION"
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --channel)
                channel="$2"
                shift 2
                ;;
            --version)
                version="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  Matha Flutter SDK 安装脚本${NC}"
    echo -e "${CYAN}  版本: ${version} | 频道: ${channel}${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    
    # 1. 检查依赖
    check_dependencies || exit 1
    
    # 2. 安装 Git（如果需要）
    install_git
    
    # 3. 下载 Flutter
    download_flutter
    
    # 4. 配置环境变量
    setup_environment
    
    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_success "  Flutter SDK 安装完成!"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    log_info "  安装路径: ${INSTALL_DIR}"
    log_info "  版本: ${version}"
    log_info "  频道: ${channel}"
    echo ""
    log_info "  下一步:"
    log_info "    1. 运行: source ${HOME}/.bashrc  (或 .zshrc)"
    log_info "    2. 运行: flutter doctor"
    log_info "    3. 运行: flutter precache"
    echo ""
}

# 执行
main "$@"
