# RAG 评估系统 - 快速开始指南

## 🎯 5分钟快速部署

### 前置要求

- ✅ Docker 已安装（版本 20.10 或更高）
- ✅ Docker Compose 已安装（版本 2.0 或更高）
- ✅ RAGFlow 服务正在运行
- ✅ 至少一个 LLM API 密钥（硅基流动/OpenAI/DeepSeek）

### 步骤 1: 加载 Docker 镜像

如果收到的是镜像文件（.tar.gz），先加载镜像：

```bash
# 解压并加载镜像
docker load -i rag-evaluation-latest.tar.gz

# 验证镜像已加载
docker images | grep rag-evaluation
```

### 步骤 2: 准备配置文件

创建 `.env.docker` 文件：

```bash
cat > .env.docker << 'EOF'
# RAGFlow 配置（必填）
RAGFLOW_BASE_URL=http://ragflow:9380
RAGFLOW_API_KEY=ragflow-你的API密钥

# LLM 配置（至少填一个）
SILICONFLOW_API_KEY=sk-你的硅基流动密钥
# OPENAI_API_KEY=sk-你的OpenAI密钥
# DEEPSEEK_API_KEY=sk-你的DeepSeek密钥

# 默认配置（可选）
DEFAULT_LLM_PROVIDER=siliconflow
DEFAULT_LLM_MODEL=Qwen/Qwen2.5-32B-Instruct
SECRET_KEY=请修改为随机字符串
EOF
```

### 步骤 3: 创建 docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  rag-evaluation:
    image: rag-evaluation:latest
    container_name: rag-evaluation
    restart: unless-stopped
    
    ports:
      - "5003:80"
    
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./tmp:/app/tmp
    
    env_file:
      - .env.docker
    
    environment:
      - TZ=Asia/Shanghai
    
    networks:
      - rag-network

networks:
  rag-network:
    external: true
    name: ragflow_ragflow
EOF
```

### 步骤 4: 启动服务

```bash
# 创建必要的目录
mkdir -p data logs tmp

# 启动容器
docker-compose up -d

# 查看启动日志
docker-compose logs -f
```

### 步骤 5: 访问系统

等待 30-40 秒后，打开浏览器访问：

```
http://localhost:5003
```

或通过健康检查确认服务就绪：

```bash
curl http://localhost:5003/health
```

## ✅ 验证部署

### 检查服务状态

```bash
# 查看容器状态
docker-compose ps

# 应该看到类似输出：
# NAME              STATUS         PORTS
# rag-evaluation    Up (healthy)   0.0.0.0:5003->80/tcp
```

### 测试 API

```bash
# 测试健康检查
curl http://localhost:5003/health

# 测试数据集列表
curl http://localhost:5003/api/v1/evaluation/datasets
```

### 访问 Web 界面

打开浏览器，访问 `http://localhost:5003`，你应该看到：

- 📊 数据集管理
- 🎯 评测任务
- 📈 评测报告
- ⚙️ 配置管理

## 🔧 常见问题

### Q1: 容器无法启动？

```bash
# 检查日志
docker-compose logs

# 可能原因：
# 1. 端口 5003 被占用 -> 修改 docker-compose.yml 中的端口
# 2. RAGFlow 网络不存在 -> 检查 RAGFlow 是否运行
# 3. 环境变量配置错误 -> 检查 .env.docker 文件
```

### Q2: 无法连接到 RAGFlow？

```bash
# 测试网络连通性
docker exec rag-evaluation ping ragflow

# 如果 ping 失败，检查网络配置
docker network ls | grep ragflow

# 如果 RAGFlow 使用不同的网络名，修改 docker-compose.yml
```

### Q3: 前端页面无法访问？

```bash
# 检查 Nginx 状态
docker exec rag-evaluation supervisorctl status

# 检查端口是否正确映射
docker port rag-evaluation

# 查看详细日志
docker-compose logs -f
```

### Q4: API 调用失败？

```bash
# 测试后端健康
curl http://localhost:5003/health

# 查看后端日志
docker exec rag-evaluation tail -f /app/logs/evaluation.log

# 检查环境变量配置
docker exec rag-evaluation env | grep API_KEY
```

## 📁 目录说明

部署完成后，会自动创建以下目录：

```
.
├── .env.docker              # 环境变量配置（重要！）
├── docker-compose.yml       # Docker Compose 配置
├── data/                    # 数据库文件（持久化）
├── logs/                    # 系统日志
└── tmp/                     # 临时文件
    ├── datasets/           # 上传的数据集
    └── evaluation/         # 评测结果
        └── reports/        # 评测报告
```

## 🎓 下一步

现在你已经成功部署了 RAG 评估系统，可以：

1. **创建数据集**: 上传评测数据或使用 AI 生成
2. **创建评测任务**: 选择数据集和对话助手
3. **查看报告**: 分析评测结果和性能指标
4. **配置指标**: 自定义评测指标

详细使用说明请参考系统内的文档。

## 🔄 停止和重启

```bash
# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 完全删除（包括数据）
docker-compose down -v
```

## 📞 获取帮助

如遇到问题，请：

1. 查看日志: `docker-compose logs -f`
2. 检查健康状态: `docker-compose ps`
3. 查看详细文档: `DEPLOY.md` 和 `DOCKER_README.md`

---

**🎉 恭喜！你已成功部署 RAG 评估系统！**
