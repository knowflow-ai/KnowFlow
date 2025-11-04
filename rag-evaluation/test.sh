#!/bin/bash

# RAG 评估系统测试脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 项目根目录
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo -e "${BLUE}=========================================="
echo "RAG Evaluation System 测试脚本"
echo "==========================================${NC}"

# 测试后端
test_backend() {
    echo -e "${YELLOW}测试后端服务...${NC}"

    # 检查后端是否运行
    if curl -s http://localhost:5002/health > /dev/null; then
        echo -e "${GREEN}✓ 后端服务运行正常${NC}"

        # 测试健康检查
        response=$(curl -s http://localhost:5002/health)
        echo -e "${BLUE}健康检查响应:${NC}"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"

        # 测试评测 API
        echo -e "\n${YELLOW}测试评测指标 API...${NC}"
        if curl -s http://localhost:5002/api/v1/evaluation/metrics > /dev/null; then
            echo -e "${GREEN}✓ 评测 API 正常${NC}"
        else
            echo -e "${RED}✗ 评测 API 异常${NC}"
        fi
    else
        echo -e "${RED}✗ 后端服务未运行${NC}"
    fi
    echo ""
}

# 测试前端
test_frontend() {
    echo -e "${YELLOW}测试前端服务...${NC}"

    # 检查前端是否运行
    if curl -s http://localhost:3001 > /dev/null; then
        echo -e "${GREEN}✓ 前端服务运行正常${NC}"
        echo -e "${BLUE}前端地址: http://localhost:3001${NC}"
    else
        echo -e "${RED}✗ 前端服务未运行${NC}"
    fi
    echo ""
}

# 测试 RAGFlow 连接
test_ragflow() {
    echo -e "${YELLOW}测试 RAGFlow 连接...${NC}"

    # 从环境变量获取 RAGFlow 配置
    if [ -f "$BACKEND_DIR/.env" ]; then
        source "$BACKEND_DIR/.env"

        if [ -n "$RAGFLOW_API_KEY" ]; then
            # 测试 RAGFlow API
            if curl -s -H "Authorization: Bearer $RAGFLOW_API_KEY" \
                   "$RAGFLOW_BASE_URL/api/v1/chats" > /dev/null; then
                echo -e "${GREEN}✓ RAGFlow 连接正常${NC}"
            else
                echo -e "${RED}✗ RAGFlow 连接失败${NC}"
            fi
        else
            echo -e "${YELLOW}⚠ 未配置 RAGFLOW_API_KEY${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ 后端环境文件不存在${NC}"
    fi
    echo ""
}

# 运行所有测试
run_all_tests() {
    echo -e "${BLUE}开始运行系统测试...${NC}\n"

    test_backend
    test_frontend
    test_ragflow

    echo -e "${GREEN}=========================================="
    echo "测试完成!"
    echo "==========================================${NC}"
}

# 检查参数
case "${1:-}" in
    "backend")
        test_backend
        ;;
    "frontend")
        test_frontend
        ;;
    "ragflow")
        test_ragflow
        ;;
    *)
        run_all_tests
        ;;
esac