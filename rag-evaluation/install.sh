#!/bin/bash

# RAG 评估系统自动安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "RAG Evaluation System 自动安装"
echo "==========================================${NC}"

# 项目根目录
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 检测 Python 版本
check_python_version() {
    echo -e "${YELLOW}检测 Python 版本...${NC}"

    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        echo -e "${BLUE}当前 Python 版本: $PYTHON_VERSION${NC}"

        # 检查是否是兼容版本
        if [[ "$PYTHON_VERSION" == "3.13" ]]; then
            echo -e "${RED}⚠️  检测到 Python 3.13，存在兼容性问题${NC}"
            echo -e "${YELLOW}强烈建议使用 Python 3.10 以获得最佳兼容性${NC}"

            # 检查是否有 pyenv
            if command -v pyenv &> /dev/null; then
                echo -e "${BLUE}检测到 pyenv，是否安装 Python 3.10? (y/n)${NC}"
                read -r response
                if [[ "$response" =~ ^[Yy]$ ]]; then
                    echo -e "${YELLOW}安装 Python 3.10...${NC}"
                    pyenv install 3.10.14 --skip-existing
                    pyenv local 3.10.14
                    PYTHON_VERSION="3.10"
                    echo -e "${GREEN}已切换到 Python 3.10${NC}"
                fi
            else
                echo -e "${RED}✗ Python 3.13 兼容性较差，建议使用 Python 3.10${NC}"
                echo -e "${YELLOW}请安装 Python 3.10 或使用 pyenv 管理版本${NC}"
                echo -e "${BLUE}安装 pyenv: brew install pyenv${NC}"
                exit 1
            fi
        elif [[ "$PYTHON_VERSION" == "3.10" ]]; then
            echo -e "${GREEN}✓ Python 3.10 - 推荐版本，兼容性最佳${NC}"
        elif [[ "$PYTHON_VERSION" =~ ^3\.(8|9|11|12)$ ]]; then
            echo -e "${GREEN}✓ Python 版本兼容${NC}"
        else
            echo -e "${RED}✗ Python 版本不兼容，建议使用 Python 3.10${NC}"
            exit 1
        fi
    else
        echo -e "${RED}✗ 未找到 Python3${NC}"
        exit 1
    fi
    echo ""
}

# 检查 Node.js
check_node() {
    echo -e "${YELLOW}检测 Node.js...${NC}"

    if command -v node &> /dev/null; then
        NODE_VERSION=$(node -v | sed 's/v//')
        echo -e "${GREEN}✓ Node.js 版本: $NODE_VERSION${NC}"
    else
        echo -e "${RED}✗ 未找到 Node.js，请先安装${NC}"
        echo -e "${YELLOW}推荐使用: brew install node${NC}"
        exit 1
    fi
    echo ""
}

# 安装后端依赖
install_backend() {
    echo -e "${YELLOW}安装后端依赖...${NC}"
    cd "$BACKEND_DIR"

    # 创建虚拟环境
    if [ ! -d "venv" ]; then
        echo -e "${BLUE}创建 Python 虚拟环境...${NC}"
        python3 -m venv venv
    fi

    # 激活虚拟环境
    source venv/bin/activate
    echo -e "${BLUE}虚拟环境已激活${NC}"

    # 升级 pip
    pip install --upgrade pip

    # 安装依赖
    echo -e "${YELLOW}安装 Python 依赖包...${NC}"

    # 使用最小依赖列表
    if [ -f "requirements-minimal.txt" ]; then
        echo -e "${BLUE}使用最小依赖列表...${NC}"
        pip install -r requirements-minimal.txt
    else
        echo -e "${BLUE}使用完整依赖列表...${NC}"
        pip install -r requirements.txt
    fi

    echo -e "${GREEN}✓ 后端依赖安装完成${NC}"
    echo ""
}

# 安装前端依赖
install_frontend() {
    echo -e "${YELLOW}安装前端依赖...${NC}"
    cd "$FRONTEND_DIR"

    # 使用合适的包管理器
    if command -v yarn &> /dev/null; then
        echo -e "${BLUE}使用 yarn 安装前端依赖...${NC}"
        yarn install
    elif command -v npm &> /dev/null; then
        echo -e "${BLUE}使用 npm 安装前端依赖...${NC}"
        npm install
    else
        echo -e "${RED}✗ 未找到 npm 或 yarn${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ 前端依赖安装完成${NC}"
    echo ""
}

# 创建配置文件
setup_config() {
    echo -e "${YELLOW}创建配置文件...${NC}"

    # 后端配置
    if [ ! -f "$BACKEND_DIR/.env" ]; then
        cp "$PROJECT_ROOT/.env.example" "$BACKEND_DIR/.env"
        echo -e "${GREEN}✓ 已创建后端配置文件: $BACKEND_DIR/.env${NC}"
    fi

    # 前端配置
    if [ ! -f "$FRONTEND_DIR/.env" ]; then
        cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
        echo -e "${GREEN}✓ 已创建前端配置文件: $FRONTEND_DIR/.env${NC}"
    fi

    # 创建必要目录
    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$BACKEND_DIR/tmp/datasets"
    mkdir -p "$BACKEND_DIR/tmp/evaluation/reports"

    echo -e "${GREEN}✓ 配置文件创建完成${NC}"
    echo ""
}

# 验证安装
verify_installation() {
    echo -e "${YELLOW}验证安装...${NC}"

    # 检查后端
    cd "$BACKEND_DIR"
    source venv/bin/activate

    # 测试导入
    python -c "
import flask
import pandas
import requests
import pydantic
print('✓ 所有核心模块导入成功')
" 2>/dev/null || {
        echo -e "${RED}✗ 模块导入测试失败${NC}"
        exit 1
    }

    # 检查前端
    cd "$FRONTEND_DIR"
    if [ -f "package.json" ] && [ -d "node_modules" ]; then
        echo -e "${GREEN}✓ 前端依赖验证成功${NC}"
    else
        echo -e "${RED}✗ 前端依赖验证失败${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ 安装验证完成${NC}"
    echo ""
}

# 主安装流程
main() {
    check_python_version
    check_node
    install_backend
    install_frontend
    setup_config
    verify_installation

    echo -e "${GREEN}=========================================="
    echo "🎉 安装完成！"
    echo "==========================================${NC}"
    echo ""
    echo -e "${BLUE}下一步:${NC}"
    echo "1. 编辑配置文件: $BACKEND_DIR/.env"
    echo "2. 启动系统: ./start.sh dev"
    echo ""
    echo -e "${BLUE}访问地址:${NC}"
    echo "  前端: http://localhost:3001"
    echo "  后端: http://localhost:5002"
    echo ""
    echo -e "${YELLOW}如需帮助，请查看: cat INSTALL.md${NC}"
}

# 运行安装
main