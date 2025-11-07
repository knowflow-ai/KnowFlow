# RAG 评估系统 - Docker 部署指南

## 📦 镜像特性

- **前后端一体化**: 单个容器包含完整的前端和后端服务
- **源码保护**: 生产镜像中不包含源代码，仅包含编译后的字节码
- **轻量化部署**: 使用 Nginx + Supervisor 管理多服务
- **开箱即用**: 配置好环境变量即可启动

## 🚀 快速开始

### 1. 构建镜像

```bash
# 构建最新版本
./build-docker.sh

# 构建指定版本
./build-docker.sh v1.0.0
```

### 2. 配置环境

编辑 `.env.docker` 文件，填入必要的配置：

```bash
# 必须配置的项
RAGFLOW_BASE_URL=http://ragflow:9380
RAGFLOW_API_KEY=ragflow-xxxxxx

# LLM API 密钥（至少配置一个）
SILICONFLOW_API_KEY=sk-xxxxxx
OPENAI_API_KEY=sk-xxxxxx
DEEPSEEK_API_KEY=sk-xxxxxx
```

### 3. 启动服务

```bash
# 启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 4. 访问系统

打开浏览器访问: `http://localhost:5003`

## 📋 环境变量说明

### RAGFlow 配置

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `RAGFLOW_BASE_URL` | RAGFlow 服务地址 | `http://ragflow:9380` |
| `RAGFLOW_API_KEY` | RAGFlow API 密钥 | `ragflow-xxxxxx` |

### LLM 配置

支持多个 LLM 提供商，至少需要配置一个：

| 提供商 | API_KEY | BASE_URL |
|--------|---------|----------|
| 硅基流动 | `SILICONFLOW_API_KEY` | `https://api.siliconflow.cn/v1` |
| OpenAI | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| DeepSeek | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1` |
| 智谱AI | `ZHIPU_API_KEY` | `https://open.bigmodel.cn/api/paas/v4` |

### 默认模型

```bash
DEFAULT_LLM_PROVIDER=siliconflow
DEFAULT_LLM_MODEL=Qwen/Qwen2.5-32B-Instruct
DEFAULT_EMBEDDING_MODEL=BAAI/bge-m3
```

## 🗂️ 数据持久化

以下目录会挂载到宿主机，确保数据不丢失：

```yaml
volumes:
  - ./data:/app/data          # 数据库文件
  - ./logs:/app/logs          # 日志文件
  - ./tmp:/app/tmp            # 临时文件（数据集、报告等）
```

## 🔍 健康检查

容器内置健康检查，每30秒检测一次服务状态：

```bash
# 手动检查
docker-compose ps
docker exec rag-evaluation curl -f http://localhost/api/v1/evaluation/health
```

## 🔧 故障排查

### 查看容器日志

```bash
# 查看所有日志
docker-compose logs

# 实时查看日志
docker-compose logs -f

# 查看后端日志
docker exec rag-evaluation tail -f /app/logs/evaluation.log
```

### 进入容器调试

```bash
docker exec -it rag-evaluation /bin/bash
```

### 重启服务

```bash
# 重启容器
docker-compose restart

# 重新构建并启动
docker-compose up -d --build
```

## 🌐 网络配置

系统默认连接到 RAGFlow 的网络 `ragflow_ragflow`。

如果 RAGFlow 使用不同的网络名称，请修改 `docker-compose.yml`：

```yaml
networks:
  rag-network:
    external: true
    name: your_ragflow_network_name
```

## 🔐 安全建议

1. **修改默认密钥**: 生产环境务必修改 `SECRET_KEY`
2. **限制 CORS**: 修改 `CORS_ORIGINS` 为具体域名
3. **网络隔离**: 仅暴露必要的端口
4. **定期更新**: 及时更新镜像和依赖

## 📊 性能优化

### 调整并发配置

```bash
EVALUATION_MAX_WORKERS=4  # 增加评测并发数
EVALUATION_TIMEOUT=600    # 延长超时时间
```

### 资源限制

在 `docker-compose.yml` 中添加：

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

## 🎯 生产部署清单

- [ ] 修改 `.env.docker` 中的所有密钥和配置
- [ ] 配置至少一个可用的 LLM API
- [ ] 确认 RAGFlow 网络配置正确
- [ ] 测试数据库和日志目录挂载
- [ ] 执行健康检查确认服务正常
- [ ] 配置反向代理和 HTTPS (可选)
- [ ] 设置日志轮转和监控
- [ ] 备份数据目录

## 📝 版本更新

```bash
# 拉取最新代码
git pull

# 重新构建镜像
./build-docker.sh v1.1.0

# 更新容器
docker-compose up -d
```

## 💡 高级配置

### 自定义 Nginx 配置

如需自定义 Nginx，可以挂载配置文件：

```yaml
volumes:
  - ./nginx.conf:/etc/nginx/sites-available/default
```

### 使用外部数据库

修改环境变量：

```bash
DATABASE_URL=postgresql://user:password@host:5432/rag_eval
```

## 📞 技术支持

如遇问题，请查看：

1. 日志文件: `./logs/evaluation.log`
2. 容器日志: `docker-compose logs`
3. 健康检查: `http://localhost:5003/api/v1/evaluation/health`
