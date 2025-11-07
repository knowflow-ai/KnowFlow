# RAG 评估系统 - Docker 部署说明

## 📦 镜像说明

本 Docker 镜像是 RAG 评估系统的生产就绪版本，具有以下特点：

### ✨ 核心特性

1. **前后端一体化**: 单个容器包含完整的 Web 界面和后端 API
2. **源码保护**: 镜像中仅包含编译后的 Python 字节码（.pyc），不包含源代码
3. **轻量化部署**: 使用 Nginx 提供静态文件服务，Supervisor 管理进程
4. **开箱即用**: 配置环境变量即可启动，无需额外安装依赖

### 🏗️ 技术架构

```
┌─────────────────────────────────────┐
│         Docker Container            │
│  ┌──────────────────────────────┐  │
│  │  Nginx (Port 80)             │  │
│  │  ├─ Static Files (/app/static)│  │
│  │  └─ Reverse Proxy (/api)     │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │  Flask Backend (Port 5002)   │  │
│  │  ├─ Evaluation API           │  │
│  │  ├─ Dataset Management       │  │
│  │  └─ Report Generation        │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │  Supervisor                  │  │
│  │  └─ Process Management       │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

## 🚀 快速部署

### 第一步：构建镜像

```bash
# 进入项目目录
cd /path/to/rag-evaluation

# 执行构建脚本
./build-docker.sh

# 或手动构建
docker build -t rag-evaluation:latest .
```

### 第二步：配置环境变量

编辑 `.env.docker` 文件：

```bash
# 必须配置的项目
RAGFLOW_BASE_URL=http://ragflow:9380        # RAGFlow 服务地址
RAGFLOW_API_KEY=ragflow-your-api-key       # RAGFlow API 密钥

# 至少配置一个 LLM API
SILICONFLOW_API_KEY=sk-xxxx                # 硅基流动（推荐）
# 或
OPENAI_API_KEY=sk-xxxx                     # OpenAI
# 或
DEEPSEEK_API_KEY=sk-xxxx                   # DeepSeek
```

### 第三步：启动服务

```bash
# 使用 docker-compose 启动
docker-compose up -d

# 查看启动日志
docker-compose logs -f

# 检查服务状态
docker-compose ps
```

### 第四步：访问系统

打开浏览器访问：`http://localhost:5003`

## 📁 目录结构

```
rag-evaluation/
├── Dockerfile              # Docker 镜像构建文件
├── docker-compose.yml      # Docker Compose 配置
├── .env.docker            # Docker 环境变量配置
├── .dockerignore          # Docker 构建忽略文件
├── build-docker.sh        # 镜像构建脚本
├── DEPLOY.md              # 详细部署文档
├── backend/               # 后端源码（不包含在镜像中）
├── frontend/              # 前端源码（仅构建产物包含在镜像中）
├── data/                  # 数据持久化目录（挂载）
├── logs/                  # 日志目录（挂载）
└── tmp/                   # 临时文件目录（挂载）
```

## 🔧 配置说明

### 环境变量

| 变量名 | 说明 | 必填 | 默认值 |
|--------|------|------|--------|
| `RAGFLOW_BASE_URL` | RAGFlow 服务地址 | ✅ | - |
| `RAGFLOW_API_KEY` | RAGFlow API 密钥 | ✅ | - |
| `SILICONFLOW_API_KEY` | 硅基流动 API 密钥 | ⚠️ | - |
| `OPENAI_API_KEY` | OpenAI API 密钥 | ⚠️ | - |
| `DEFAULT_LLM_MODEL` | 默认模型 | ❌ | Qwen/Qwen2.5-32B-Instruct |
| `EVALUATION_MAX_WORKERS` | 最大并发数 | ❌ | 2 |

⚠️ 至少需要配置一个 LLM API 密钥

### 数据持久化

容器默认挂载以下目录到宿主机：

```yaml
volumes:
  - ./data:/app/data      # 数据库文件
  - ./logs:/app/logs      # 系统日志
  - ./tmp:/app/tmp        # 临时文件（数据集、报告等）
```

## 🔍 运维管理

### 查看日志

```bash
# 查看容器日志
docker-compose logs

# 实时查看日志
docker-compose logs -f

# 查看后端应用日志
tail -f ./logs/evaluation.log

# 查看 Nginx 日志
docker exec rag-evaluation tail -f /var/log/nginx/access.log
```

### 健康检查

```bash
# 通过 API 检查
curl http://localhost:5003/health

# 检查容器健康状态
docker inspect --format='{{.State.Health.Status}}' rag-evaluation
```

### 重启服务

```bash
# 重启容器
docker-compose restart

# 重启特定服务
docker exec rag-evaluation supervisorctl restart backend
docker exec rag-evaluation supervisorctl restart nginx
```

### 进入容器调试

```bash
# 进入容器 shell
docker exec -it rag-evaluation /bin/bash

# 查看进程状态
docker exec rag-evaluation supervisorctl status

# 查看配置
docker exec rag-evaluation cat /etc/nginx/sites-available/default
```

## 🌐 网络配置

### 与 RAGFlow 集成

系统默认连接到 RAGFlow 的 Docker 网络 `ragflow_ragflow`。

如果你的 RAGFlow 使用不同的网络名称，需要修改 `docker-compose.yml`：

```yaml
networks:
  rag-network:
    external: true
    name: your_ragflow_network_name  # 修改为实际网络名
```

### 查看 RAGFlow 网络

```bash
# 列出所有网络
docker network ls

# 查看 RAGFlow 容器连接的网络
docker inspect ragflow | grep NetworkMode
```

### 单独部署（不使用 RAGFlow 网络）

如果单独部署，修改配置：

```yaml
# docker-compose.yml
networks:
  rag-network:
    driver: bridge  # 创建独立网络
```

```bash
# .env.docker
RAGFLOW_BASE_URL=http://your-ragflow-host:9380  # 使用外部地址
```

## 📊 性能优化

### 资源限制

在 `docker-compose.yml` 中添加资源限制：

```yaml
services:
  rag-evaluation:
    deploy:
      resources:
        limits:
          cpus: '2'        # CPU 核心数
          memory: 4G       # 内存限制
        reservations:
          cpus: '1'
          memory: 2G
```

### 并发配置

调整环境变量：

```bash
EVALUATION_MAX_WORKERS=4      # 增加并发评测数量
EVALUATION_TIMEOUT=600        # 延长超时时间（秒）
```

## 🔒 安全建议

1. **修改默认密钥**: 生产环境务必修改 `SECRET_KEY`
2. **限制 CORS**: 将 `CORS_ORIGINS` 改为具体域名，不使用 `*`
3. **使用 HTTPS**: 通过反向代理（如 Nginx、Traefik）提供 HTTPS
4. **网络隔离**: 仅暴露必要的端口
5. **定期备份**: 备份 `./data` 目录
6. **定期更新**: 及时更新镜像

## 🐛 故障排查

### 问题 1: 容器启动失败

```bash
# 查看详细日志
docker-compose logs

# 检查配置文件
docker-compose config
```

### 问题 2: 无法访问前端

```bash
# 检查 Nginx 状态
docker exec rag-evaluation supervisorctl status nginx

# 查看 Nginx 日志
docker exec rag-evaluation nginx -t
```

### 问题 3: API 调用失败

```bash
# 检查后端服务
docker exec rag-evaluation supervisorctl status backend

# 测试后端健康
curl http://localhost:5003/health

# 查看后端日志
tail -f ./logs/evaluation.log
```

### 问题 4: RAGFlow 连接失败

```bash
# 测试网络连通性
docker exec rag-evaluation ping ragflow

# 检查 RAGFlow 服务
curl http://localhost:9380/api/v1/health
```

## 📦 镜像分发

### 导出镜像

```bash
# 导出镜像为 tar 文件
docker save rag-evaluation:latest -o rag-evaluation-latest.tar

# 压缩镜像
gzip rag-evaluation-latest.tar
```

### 导入镜像

```bash
# 在客户端加载镜像
docker load -i rag-evaluation-latest.tar.gz

# 验证镜像
docker images | grep rag-evaluation
```

### 推送到私有仓库

```bash
# 标记镜像
docker tag rag-evaluation:latest your-registry.com/rag-evaluation:latest

# 推送镜像
docker push your-registry.com/rag-evaluation:latest
```

## 🔄 版本升级

```bash
# 1. 拉取最新代码（如果有源码访问权限）
git pull

# 2. 重新构建镜像
./build-docker.sh v1.1.0

# 3. 停止旧容器
docker-compose down

# 4. 启动新容器
docker-compose up -d

# 5. 验证升级
curl http://localhost:5003/health
```

## 📞 技术支持

### 常用命令速查

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 查看状态
docker-compose ps

# 进入容器
docker exec -it rag-evaluation bash

# 健康检查
curl http://localhost:5003/health
```

### 日志位置

- 应用日志: `./logs/evaluation.log`
- Nginx 日志: 容器内 `/var/log/nginx/`
- Supervisor 日志: 容器内 `/var/log/supervisor/`

### 配置文件位置

- Nginx 配置: 容器内 `/etc/nginx/sites-available/default`
- Supervisor 配置: 容器内 `/etc/supervisor/conf.d/rag-evaluation.conf`
- 应用配置: 通过环境变量 `.env.docker`

## 📝 更新日志

### v1.0.0 (2024-11)
- ✨ 首次发布
- 🎯 前后端一体化容器
- 🔒 源码保护机制
- 📊 完整的评测功能
- 🚀 开箱即用的部署方案
