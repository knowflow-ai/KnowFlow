#!/bin/bash
# RAG 评估系统部署问题排查脚本

echo "========================================="
echo "RAG 评估系统部署诊断"
echo "========================================="
echo ""

echo "1️⃣  检查 .env.docker 配置"
echo "========================================="
if [ -f .env.docker ]; then
    echo "✅ .env.docker 文件存在"
    echo ""
    echo "📝 RAGFlow 配置:"
    grep "^RAGFLOW" .env.docker || echo "❌ 未找到 RAGFLOW 配置"
else
    echo "❌ .env.docker 文件不存在！"
fi
echo ""

echo "2️⃣  检查 Docker 镜像构建参数"
echo "========================================="
echo "查看 docker-compose.yml 构建配置:"
grep -A 5 "build:" docker-compose.yml
echo ""

echo "3️⃣  检查容器内的前端构建产物"
echo "========================================="
if docker ps | grep -q "rag-evaluation"; then
    echo "✅ 容器正在运行"
    echo ""
    echo "📄 检查前端 JS 文件中的 API 配置:"
    docker exec rag-evaluation sh -c "grep -o 'localhost:9380' /app/static/assets/*.js | head -3" 2>/dev/null && \
        echo "❌ 发现 localhost:9380 - 配置未生效！" || \
        echo "✅ 未发现 localhost:9380"
    echo ""
    
    echo "📄 检查前端实际使用的 API URL:"
    docker exec rag-evaluation sh -c "grep -o 'RAGFLOW_API_URL.*http[^\"]*' /app/static/assets/*.js | head -3" 2>/dev/null || \
        echo "⚠️  无法检测到 RAGFLOW_API_URL"
else
    echo "❌ 容器未运行！请先启动容器"
fi
echo ""

echo "4️⃣  检查构建参数是否传递"
echo "========================================="
echo "建议手动重新构建并查看日志:"
echo ""
echo "  docker-compose build --no-cache 2>&1 | grep -E 'VITE_|RAGFLOW'"
echo ""

echo "5️⃣  推荐的修复步骤"
echo "========================================="
echo "1. 确认 .env.docker 配置正确"
echo "   RAGFLOW_BASE_URL=http://YOUR_SERVER_IP:9380"
echo ""
echo "2. 完全重新构建镜像（不使用缓存）"
echo "   docker-compose down"
echo "   docker-compose build --no-cache"
echo "   docker-compose up -d"
echo ""
echo "3. 验证前端配置"
echo "   docker exec rag-evaluation grep -r 'localhost:9380' /app/static/"
echo "   如果还有 localhost，说明构建参数未生效"
echo ""
echo "========================================="
