#!/bin/bash

# 快速切换到 Python 3.10 的脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "Python 3.10 环境设置"
echo "==========================================${NC}"

# 检查当前 Python 版本
CURRENT_VERSION=$(python3 --version 2>/dev/null | awk '{print $2}' | cut -d. -f1,2)
echo -e "${YELLOW}当前 Python 版本: $CURRENT_VERSION${NC}"

if [[ "$CURRENT_VERSION" == "3.10" ]]; then
    echo -e "${GREEN}✓ 已经是 Python 3.10，无需切换${NC}"
    exit 0
fi

# 检查 pyenv 是否安装
if ! command -v pyenv &> /dev/null; then
    echo -e "${YELLOW}安装 pyenv...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install pyenv
        else
            echo -e "${RED}请先安装 Homebrew: https://brew.sh/${NC}"
            exit 1
        fi
    else
        # Linux
        curl https://pyenv.run | bash
    fi

    # 配置 pyenv
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
    echo 'eval "$(pyenv init -)"' >> ~/.zshrc

    echo -e "${BLUE}请重新加载 shell 或运行: source ~/.zshrc${NC}"
    echo -e "${YELLOW}然后重新运行此脚本${NC}"
    exit 0
fi

# 安装 Python 3.10
echo -e "${YELLOW}安装 Python 3.10...${NC}"
pyenv install 3.10.14 --skip-existing

# 设置本地 Python 版本
echo -e "${YELLOW}设置本地 Python 版本为 3.10...${NC}"
pyenv local 3.10.14

# 验证安装
NEW_VERSION=$(python3 --version 2>/dev/null | awk '{print $2}' | cut -d. -f1,2)
echo -e "${GREEN}✓ 成功切换到 Python $NEW_VERSION${NC}"

# 重新创建虚拟环境
BACKEND_DIR="/Users/zxwei/zhishi/knowflow/rag-evaluation/backend"
echo -e "${YELLOW}重新创建虚拟环境...${NC}"
cd "$BACKEND_DIR"

# 删除旧的虚拟环境
if [ -d "venv" ]; then
    rm -rf venv
    echo -e "${BLUE}删除旧的虚拟环境${NC}"
fi

# 创建新的虚拟环境
python3 -m venv venv
echo -e "${GREEN}✓ 创建新的虚拟环境${NC}"

echo -e "${BLUE}现在可以运行: ./install.sh 来安装依赖${NC}"