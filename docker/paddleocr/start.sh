#!/bin/bash

# PaddleOCR 快速启动脚本
# 用途：简化 PaddleOCR 服务的部署流程

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  PaddleOCR 独立部署启动脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未安装 Docker${NC}"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}错误: 未安装 Docker Compose${NC}"
    echo "请先安装 Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# 检查 NVIDIA GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${YELLOW}警告: 未检测到 NVIDIA GPU 驱动${NC}"
    echo -e "${YELLOW}PaddleOCR 需要 GPU 支持才能运行${NC}"
    read -p "是否继续? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ 检测到 NVIDIA GPU${NC}"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    echo ""
fi

# 创建 .env 文件（如果不存在）
if [ ! -f .env ]; then
    echo -e "${YELLOW}未找到 .env 文件，从 .env.example 创建...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ 已创建 .env 文件${NC}"
    else
        echo -e "${RED}错误: .env.example 文件不存在${NC}"
        exit 1
    fi
fi

# 加载环境变量
source .env

# 显示配置
echo -e "${GREEN}当前配置:${NC}"
echo "  - API 端口: ${PADDLEOCR_API_PORT:-8888}"
echo "  - GPU 设备: ${GPU_DEVICE_ID:-0}"
echo "  - CUDA 设备: ${CUDA_VISIBLE_DEVICES:-0}"
echo ""

# 询问启动模式
echo -e "${YELLOW}请选择启动模式:${NC}"
echo "  1) 快速启动（使用预构建镜像）"
echo "  2) 本地构建后启动（首次部署或更新配置后推荐）"
echo "  3) 离线模式构建（包含预下载模型）"
read -p "请选择 (1/2/3): " -n 1 -r mode
echo ""

case $mode in
    1)
        echo -e "${GREEN}使用预构建镜像启动...${NC}"
        docker-compose up -d
        ;;
    2)
        echo -e "${GREEN}本地构建镜像...${NC}"
        docker-compose build
        echo -e "${GREEN}启动服务...${NC}"
        docker-compose up -d
        ;;
    3)
        echo -e "${GREEN}离线模式构建（将下载约 2-3GB 模型）...${NC}"
        docker-compose build --build-arg BUILD_FOR_OFFLINE=true
        echo -e "${GREEN}启动服务...${NC}"
        docker-compose up -d
        ;;
    *)
        echo -e "${RED}无效选择，退出${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}等待服务启动...${NC}"
echo -e "${GREEN}========================================${NC}"

# 等待服务健康检查
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker-compose ps | grep -q "healthy"; then
        echo -e "${GREEN}✓ 服务已成功启动！${NC}"
        break
    fi
    attempt=$((attempt + 1))
    echo -n "."
    sleep 2
done

echo ""

if [ $attempt -eq $max_attempts ]; then
    echo -e "${YELLOW}警告: 服务启动超时，请检查日志${NC}"
    echo "运行以下命令查看日志:"
    echo "  docker-compose logs -f"
else
    # 测试 API
    echo ""
    echo -e "${GREEN}服务信息:${NC}"
    echo "  - API 地址: http://localhost:${PADDLEOCR_API_PORT:-8888}"
    echo "  - 健康检查: http://localhost:${PADDLEOCR_API_PORT:-8888}/health"
    echo ""
    echo -e "${GREEN}测试 API 连接:${NC}"
    if curl -s http://localhost:${PADDLEOCR_API_PORT:-8888}/health > /dev/null; then
        echo -e "${GREEN}✓ API 服务正常运行${NC}"
    else
        echo -e "${YELLOW}! API 服务可能尚未完全启动，请稍后再试${NC}"
    fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}常用命令:${NC}"
echo -e "${GREEN}========================================${NC}"
echo "  查看日志:     docker-compose logs -f"
echo "  停止服务:     docker-compose stop"
echo "  重启服务:     docker-compose restart"
echo "  删除服务:     docker-compose down"
echo "  查看状态:     docker-compose ps"
echo ""
echo -e "${GREEN}详细文档请参考 README.md${NC}"
echo ""
