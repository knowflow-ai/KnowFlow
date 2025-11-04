#!/bin/bash

# RAG 评估系统启动脚本

set -e

echo "=========================================="
echo "RAG Evaluation System 启动脚本"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo -e "${BLUE}项目根目录: $PROJECT_ROOT${NC}"
echo ""

# 检查环境配置
check_env() {
    echo -e "${YELLOW}检查环境配置...${NC}"

    # 检查后端环境
    if [ ! -f "$BACKEND_DIR/.env" ]; then
        echo -e "${YELLOW}创建后端环境文件...${NC}"
        cp "$PROJECT_ROOT/.env.example" "$BACKEND_DIR/.env"
        echo -e "${RED}请编辑 $BACKEND_DIR/.env 文件，配置必要的环境变量${NC}"
    fi

    # 检查前端环境
    if [ ! -f "$FRONTEND_DIR/.env" ]; then
        echo -e "${YELLOW}创建前端环境文件...${NC}"
        cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
    fi

    echo -e "${GREEN}环境配置检查完成${NC}"
    echo ""
}

# 安装后端依赖
install_backend() {
    echo -e "${YELLOW}安装后端依赖...${NC}"
    cd "$BACKEND_DIR"

    # 检查虚拟环境
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}创建 Python 虚拟环境...${NC}"
        python3 -m venv venv
    fi

    # 激活虚拟环境并安装依赖
    source venv/bin/activate
    pip install --upgrade pip

    # 首先尝试安装最小依赖
    if [ -f "requirements-minimal.txt" ]; then
        echo -e "${BLUE}使用最小依赖列表安装...${NC}"
        pip install -r requirements-minimal.txt
    else
        pip install -r requirements.txt
    fi

    echo -e "${GREEN}后端依赖安装完成${NC}"
    echo ""
}

# 安装前端依赖
install_frontend() {
    echo -e "${YELLOW}安装前端依赖...${NC}"
    cd "$FRONTEND_DIR"

    # 检查 Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}请先安装 Node.js${NC}"
        exit 1
    fi

    # 检查 npm/yarn
    if command -v yarn &> /dev/null; then
        echo -e "${BLUE}使用 yarn 安装依赖...${NC}"
        yarn install
    else
        echo -e "${BLUE}使用 npm 安装依赖...${NC}"
        npm install
    fi

    echo -e "${GREEN}前端依赖安装完成${NC}"
    echo ""
}

# 启动后端服务
start_backend() {
    echo -e "${YELLOW}启动后端服务...${NC}"
    cd "$BACKEND_DIR"

    # 激活虚拟环境
    source venv/bin/activate

    # 启动后端 (后台运行)
    nohup python app_new.py > ../logs/backend.log 2>&1 &
    BACKEND_PID=$!

    echo -e "${GREEN}后端服务已启动 (PID: $BACKEND_PID)${NC}"
    echo -e "${BLUE}后端地址: http://localhost:5002${NC}"
    echo ""

    # 等待后端启动
    echo -e "${YELLOW}等待后端服务启动...${NC}"
    sleep 3
}

# 启动前端服务
start_frontend() {
    echo -e "${YELLOW}启动前端服务...${NC}"
    cd "$FRONTEND_DIR"

    # 启动前端 (后台运行)
    if command -v yarn &> /dev/null; then
        nohup yarn dev > ../logs/frontend.log 2>&1 &
    else
        nohup npm run dev > ../logs/frontend.log 2>&1 &
    fi
    FRONTEND_PID=$!

    echo -e "${GREEN}前端服务已启动 (PID: $FRONTEND_PID)${NC}"
    echo -e "${BLUE}前端地址: http://localhost:3001${NC}"
    echo ""
}

# 创建日志目录
mkdir -p "$PROJECT_ROOT/logs"

# 检查参数
case "${1:-}" in
    "install")
        check_env
        install_backend
        install_frontend
        ;;
    "backend")
        start_backend
        ;;
    "frontend")
        start_frontend
        ;;
    "dev")
        echo -e "${BLUE}启动开发环境...${NC}"
        check_env
        install_backend
        install_frontend
        start_backend
        start_frontend

        echo -e "${GREEN}=========================================="
        echo "RAG Evaluation System 已启动!"
        echo "=========================================="
        echo -e "前端界面: ${BLUE}http://localhost:3001${NC}"
        echo -e "后端 API: ${BLUE}http://localhost:5002${NC}"
        echo -e "健康检查: ${BLUE}http://localhost:5002/health${NC}"
        echo ""
        echo -e "${YELLOW}查看日志:${NC}"
        echo "  后端: tail -f logs/backend.log"
        echo "  前端: tail -f logs/frontend.log"
        echo ""
        echo -e "${YELLOW}停止服务:${NC}"
        echo "  pkill -f 'python app_new.py'"
        echo "  pkill -f 'vite'"
        echo "=========================================="
        ;;
    *)
        echo "用法: $0 {install|backend|frontend|dev}"
        echo ""
        echo "命令说明:"
        echo "  install   - 安装前后端依赖"
        echo "  backend   - 仅启动后端服务"
        echo "  frontend  - 仅启动前端服务"
        echo "  dev       - 安装依赖并启动完整系统"
        exit 1
        ;;
esac