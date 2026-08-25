#!/bin/bash
# Matha 移动端自动化部署脚本
# 一键完成环境配置、打包和部署

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
MOBILE_DIR="$PROJECT_ROOT/mobile"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Matha 移动端自动化部署脚本${NC}"
echo -e "${BLUE}  版本: 4.4.16${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 步骤 1: 检查环境
echo -e "${GREEN}[步骤 1/6]${NC} 检查开发环境..."

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${YELLOW}  ⚠ 未找到: $1${NC}"
        return 1
    fi
    echo -e "${GREEN}  ✓${NC} $1: $(command -v $1)"
    return 0
}

check_command flutter
check_command python3
check_command git

echo ""

# 步骤 2: 安装依赖
echo -e "${GREEN}[步骤 2/6]${NC} 安装项目依赖..."
cd "$MOBILE_DIR"

echo "  安装 Flutter 依赖..."
flutter pub get

echo "  安装 Pyodide 依赖..."
pip3 install pyodide-pack websockets

echo -e "${GREEN}  ✓${NC} 依赖安装完成"
echo ""

# 步骤 3: 构建 WebAssembly
echo -e "${GREEN}[步骤 3/6]${NC} 构建 WebAssembly..."

if [ -f "$MOBILE_DIR/assets/pyodide/build_wasm.sh" ]; then
    cd "$MOBILE_DIR/assets/pyodide"
    bash build_wasm.sh --package
    echo -e "${GREEN}  ✓${NC} WebAssembly 打包完成"
else
    echo -e "${YELLOW}  ⚠ 跳过 WASM 打包（脚本不存在）${NC}"
fi

echo ""

# 步骤 4: 运行测试
echo -e "${GREEN}[步骤 4/6]${NC} 运行测试..."

echo "  运行 Python 测试..."
cd "$PROJECT_ROOT"
python3 -B tests/run_all_tests.py

echo -e "${GREEN}  ✓${NC} 测试完成"
echo ""

# 步骤 5: 构建 Flutter 应用
echo -e "${GREEN}[步骤 5/6]${NC} 构建 Flutter 应用..."
cd "$MOBILE_DIR"

echo "  构建 Web 版本..."
flutter build web --release --web-renderer canvaskit

echo -e "${GREEN}  ✓${NC} Web 版本构建完成: build/web/"
echo ""

# 步骤 6: 生成部署包
echo -e "${GREEN}[步骤 6/6]${NC} 生成部署包..."

DEPLOY_DIR="$PROJECT_ROOT/deploy"
mkdir -p "$DEPLOY_DIR"

# 复制构建产物
cp -r "$MOBILE_DIR/build/web" "$DEPLOY_DIR/"
cp "$MOBILE_DIR/assets/pyodide/build_config.json" "$DEPLOY_DIR/" 2>/dev/null || true

# 生成部署说明
cat > "$DEPLOY_DIR/README.md" << 'EOF'
# Matha 移动端部署包

## 版本信息
- 版本: 4.4.16
- 构建时间: $(date)

## 包含内容
- `web/` - Flutter Web 构建产物
- `build_config.json` - WASM 构建配置

## 部署步骤

### 方式一：静态服务器部署
```bash
# 使用 Python 内置服务器
cd deploy
python3 -m http.server 8080

# 访问 http://localhost:8080
```

### 方式二：Firebase 部署
```bash
firebase deploy --only hosting
```

### 方式三：Netlify 部署
```bash
netlify deploy --prod --dir=web
```

## 环境要求
- Flutter SDK >= 3.0.0
- Python >= 3.8
- Emscripten (用于 WASM 打包)

## 常见问题

### WebSocket 连接失败
- 检查服务器地址是否正确
- 确认服务器支持 WebSocket
- 查看浏览器控制台日志

### Pyodide 加载超时
- 检查网络连接
- 确认 CDN 可访问
- 查看浏览器控制台日志

### WASM 打包失败
- 确保已安装 Emscripten
- 检查 Python 版本兼容性
- 查看构建日志
EOF

echo -e "${GREEN}  ✓${NC} 部署包生成完成: $DEPLOY_DIR/"
echo ""

# 总结
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  ✓ 部署完成!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}  构建产物:${NC} $DEPLOY_DIR/"
echo -e "${GREEN}  Web 版本:${NC} $DEPLOY_DIR/web/"
echo ""
echo -e "${YELLOW}  下一步:${NC}"
echo -e "    1. 启动本地服务器: cd $DEPLOY_DIR && python3 -m http.server 8080"
echo -e "    2. 访问: http://localhost:8080"
echo -e "    3. 测试 WebSocket 连接和 Pyodide 功能"
echo ""
