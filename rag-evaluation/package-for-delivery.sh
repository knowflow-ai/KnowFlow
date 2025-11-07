#!/bin/bash

set -e

VERSION=${1:-"latest"}
PACKAGE_NAME="rag-evaluation-${VERSION}-deploy"

echo "========================================"
echo " RAG 评估系统 - 客户交付包打包脚本"
echo "========================================"
echo ""
echo "版本: ${VERSION}"
echo "包名: ${PACKAGE_NAME}.tar.gz"
echo ""

if [ ! -f "Dockerfile" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

echo "📦 步骤 1: 构建 Docker 镜像..."
./build-docker.sh ${VERSION}

echo ""
echo "📦 步骤 2: 导出 Docker 镜像..."
镜像_FILE="rag-evaluation-${VERSION}.tar.gz"
docker save rag-evaluation:${VERSION} | gzip > ${镜像_FILE}
echo "✅ 镜像已导出: ${镜像_FILE} ($(du -h ${镜像_FILE} | cut -f1))"

echo ""
echo "📦 步骤 3: 创建临时打包目录..."
TEMP_DIR=$(mktemp -d)
PACKAGE_DIR="${TEMP_DIR}/${PACKAGE_NAME}"
mkdir -p ${PACKAGE_DIR}

echo ""
echo "📦 步骤 4: 复制必要文件..."

cp ${镜像_FILE} ${PACKAGE_DIR}/
echo "  ✓ Docker 镜像"

cp docker-compose.yml ${PACKAGE_DIR}/
echo "  ✓ docker-compose.yml"

cp .env.docker ${PACKAGE_DIR}/env.docker.template
echo "  ✓ .env.docker (已重命名为 env.docker.template)"

cp README-DEPLOYMENT.txt ${PACKAGE_DIR}/README.txt
echo "  ✓ README.txt"

cp QUICKSTART.md ${PACKAGE_DIR}/
echo "  ✓ QUICKSTART.md"

cp DEPLOY.md ${PACKAGE_DIR}/
echo "  ✓ DEPLOY.md"

cp DOCKER_README.md ${PACKAGE_DIR}/
echo "  ✓ DOCKER_README.md"

cp DOCKER_FILES_SUMMARY.md ${PACKAGE_DIR}/
echo "  ✓ DOCKER_FILES_SUMMARY.md"

echo ""
echo "📦 步骤 5: 创建部署脚本..."

cat > ${PACKAGE_DIR}/deploy.sh << 'EOF'
#!/bin/bash

set -e

echo "========================================"
echo " RAG 评估系统 - 快速部署"
echo "========================================"

echo ""
echo "步骤 1: 加载 Docker 镜像..."
镜像_FILE=$(ls rag-evaluation-*.tar.gz | head -1)
if [ -z "$镜像_FILE" ]; then
    echo "❌ 未找到镜像文件"
    exit 1
fi
docker load -i ${镜像_FILE}
echo "✅ 镜像加载完成"

echo ""
echo "步骤 2: 配置环境变量..."
if [ ! -f ".env.docker" ]; then
    if [ -f "env.docker.template" ]; then
        echo "📝 首次部署，创建 .env.docker 配置文件"
        cp env.docker.template .env.docker
        echo ""
        echo "⚠️  请编辑 .env.docker 文件，填入以下必填项："
        echo "   - RAGFLOW_BASE_URL"
        echo "   - RAGFLOW_API_KEY"
        echo "   - SILICONFLOW_API_KEY (或其他 LLM API)"
        echo ""
        read -p "配置完成后按回车继续..."
    else
        echo "❌ 未找到环境变量模板文件"
        exit 1
    fi
fi

echo ""
echo "步骤 3: 创建数据目录..."
mkdir -p data logs tmp
echo "✅ 数据目录创建完成"

echo ""
echo "步骤 4: 启动服务..."
docker-compose up -d
echo "✅ 服务已启动"

echo ""
echo "步骤 5: 等待服务就绪..."
echo "等待 30 秒让服务完全启动..."
sleep 30

echo ""
echo "步骤 6: 健康检查..."
if curl -f http://localhost:5003/health > /dev/null 2>&1; then
    echo "✅ 服务健康检查通过！"
    echo ""
    echo "🎉 部署成功！"
    echo ""
    echo "📋 访问信息："
    echo "   Web 界面: http://localhost:5003"
    echo "   健康检查: http://localhost:5003/health"
    echo ""
    echo "📝 常用命令："
    echo "   查看日志: docker-compose logs -f"
    echo "   停止服务: docker-compose down"
    echo "   重启服务: docker-compose restart"
    echo ""
else
    echo "⚠️  健康检查失败，请检查日志："
    echo "   docker-compose logs"
    exit 1
fi
EOF

chmod +x ${PACKAGE_DIR}/deploy.sh
echo "  ✓ deploy.sh (一键部署脚本)"

echo ""
echo "📦 步骤 6: 打包所有文件..."
cd ${TEMP_DIR}
tar czf ${PACKAGE_NAME}.tar.gz ${PACKAGE_NAME}
mv ${PACKAGE_NAME}.tar.gz ${OLDPWD}/

echo ""
echo "📦 步骤 7: 清理临时文件..."
cd ${OLDPWD}
rm -rf ${TEMP_DIR}
rm -f ${镜像_FILE}

echo ""
echo "✅ 打包完成！"
echo ""
echo "📦 交付包信息："
echo "   文件名: ${PACKAGE_NAME}.tar.gz"
echo "   大小: $(du -h ${PACKAGE_NAME}.tar.gz | cut -f1)"
echo "   位置: $(pwd)/${PACKAGE_NAME}.tar.gz"
echo ""
echo "📋 包含内容："
echo "   - Docker 镜像 (rag-evaluation-${VERSION}.tar.gz)"
echo "   - Docker Compose 配置"
echo "   - 环境变量模板"
echo "   - 部署文档（中英文）"
echo "   - 一键部署脚本 (deploy.sh)"
echo ""
echo "📝 客户使用方法："
echo "   1. 解压: tar xzf ${PACKAGE_NAME}.tar.gz"
echo "   2. 进入: cd ${PACKAGE_NAME}"
echo "   3. 阅读: cat README.txt"
echo "   4. 部署: ./deploy.sh"
echo ""
echo "🎉 打包成功！可以交付给客户了。"
