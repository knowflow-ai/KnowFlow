#!/bin/bash

set -e

echo "========================================"
echo " RAG 评估系统 - Docker 镜像构建脚本"
echo "========================================"

VERSION=${1:-"latest"}
IMAGE_NAME="rag-evaluation"
FULL_IMAGE_NAME="${IMAGE_NAME}:${VERSION}"

echo ""
echo "📦 构建镜像: ${FULL_IMAGE_NAME}"
echo ""

if [ ! -f "Dockerfile" ]; then
    echo "❌ 错误: Dockerfile 不存在"
    exit 1
fi

if [ ! -d "frontend" ] || [ ! -d "backend" ]; then
    echo "❌ 错误: frontend 或 backend 目录不存在"
    exit 1
fi

echo "🔨 开始构建 Docker 镜像..."
docker build -t ${FULL_IMAGE_NAME} .

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 镜像构建成功: ${FULL_IMAGE_NAME}"
    echo ""
    echo "📋 镜像信息:"
    docker images ${IMAGE_NAME}
    echo ""
    echo "💡 使用说明:"
    echo "   1. 修改 .env.docker 文件，填入你的 API 密钥"
    echo "   2. 启动容器: docker-compose up -d"
    echo "   3. 访问系统: http://localhost:5003"
    echo "   4. 查看日志: docker-compose logs -f"
    echo ""
else
    echo ""
    echo "❌ 镜像构建失败"
    exit 1
fi

if [ "${VERSION}" != "latest" ]; then
    echo "🏷️  添加 latest 标签..."
    docker tag ${FULL_IMAGE_NAME} ${IMAGE_NAME}:latest
    echo "✅ 已添加标签: ${IMAGE_NAME}:latest"
fi

echo ""
echo "🎉 构建完成！"
