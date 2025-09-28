#!/bin/bash

# MinerU 离线镜像构建脚本

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 镜像配置
IMAGE_NAME="knowflow/mineru-api"
IMAGE_TAG="2.5-offline"
PLATFORM="linux/amd64"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== MinerU 离线镜像构建脚本 ===${NC}"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    exit 1
fi

# 构建选项
BUILD_PUSH=false
BUILD_CACHE=true
VLM_MODEL="got_ocr2"  # 默认 VLM 模型

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            BUILD_PUSH=true
            shift
            ;;
        --no-cache)
            BUILD_CACHE=false
            shift
            ;;
        --vlm-model)
            VLM_MODEL="$2"
            shift 2
            ;;
        --help)
            echo "使用方法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --push          构建后推送到镜像仓库"
            echo "  --no-cache      不使用构建缓存"
            echo "  --vlm-model     指定 VLM 模型 (got_ocr2 或 qwen2_vl)"
            echo "  --help          显示帮助信息"
            exit 0
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            exit 1
            ;;
    esac
done

# 确保下载脚本存在
if [ ! -f "download_models.py" ]; then
    echo -e "${RED}错误: download_models.py 不存在${NC}"
    exit 1
fi

# 构建参数
BUILD_ARGS="--platform $PLATFORM"
BUILD_ARGS="$BUILD_ARGS --build-arg MINERU_VLM_MODEL=$VLM_MODEL"

if [ "$BUILD_CACHE" = false ]; then
    BUILD_ARGS="$BUILD_ARGS --no-cache"
fi

if [ "$BUILD_PUSH" = true ]; then
    BUILD_ARGS="$BUILD_ARGS --push"
fi

echo -e "${YELLOW}构建配置:${NC}"
echo "  镜像: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "  平台: $PLATFORM"
echo "  VLM模型: $VLM_MODEL"
echo "  使用缓存: $BUILD_CACHE"
echo "  推送镜像: $BUILD_PUSH"
echo ""

# 开始构建
echo -e "${GREEN}开始构建镜像...${NC}"

docker buildx build \
    $BUILD_ARGS \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -t "${IMAGE_NAME}:latest" \
    -f Dockerfile \
    .

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ 镜像构建成功!${NC}"
    echo ""

    # 显示镜像信息
    echo -e "${YELLOW}镜像信息:${NC}"
    docker images | grep "$IMAGE_NAME"

    echo ""
    echo -e "${YELLOW}启动服务:${NC}"
    echo "  docker compose up -d mineru-api"
    echo ""
    echo -e "${YELLOW}启动 VLM 服务（可选）:${NC}"
    echo "  docker compose --profile vllm up -d"
else
    echo -e "${RED}✗ 镜像构建失败${NC}"
    exit 1
fi