# RAG 评估系统部署说明

## 快速部署

### 1. 修改配置文件

编辑 `.env.docker`，修改以下配置：

```bash
# 修改为服务器的实际 IP 地址（前端浏览器访问用）
RAGFLOW_BASE_URL=http://192.168.1.100:9380

# 修改为实际的 RAGFlow API Key
RAGFLOW_API_KEY=ragflow-your-actual-api-key

# 修改为实际的 LLM API Key
SILICONFLOW_API_KEY=sk-your-actual-api-key
```

### 2. 构建并启动

```bash
# 构建镜像并启动服务
docker-compose up -d --build
```

### 3. 访问服务

- 前端地址：`http://服务器IP:5003`
- 健康检查：`http://服务器IP:5003/health`

## 配置说明

### 前端环境变量

前端在 **Docker 构建时** 会从 `.env.docker` 读取以下配置：

- `RAGFLOW_BASE_URL` → 转换为 `VITE_RAGFLOW_API_URL`
- `RAGFLOW_API_KEY` → 转换为 `VITE_RAGFLOW_API_KEY`

**重要**：修改这些配置后需要重新构建镜像！

```bash
docker-compose up -d --build
```

### 后端环境变量

后端在 **运行时** 从 `.env.docker` 读取配置：

- `RAGFLOW_BASE_URL` - RAGFlow 服务地址（容器内部可用 `http://ragflow:9380`）
- `RAGFLOW_API_KEY` - RAGFlow API Key
- `SILICONFLOW_API_KEY` - 硅基流动 API Key（用于评估）

## 架构说明

```
浏览器 → Nginx (80) → 后端 API (5002)
       ↓
       → RAGFlow API (服务器IP:9380)
```

- **前端静态文件**：由 Nginx 提供
- **后端 API**：`/api/*` 由 Nginx 反向代理到后端
- **RAGFlow API**：前端直接访问（需配置服务器 IP）

## 常见问题

### 1. 前端无法访问 RAGFlow API

**错误**：`Network Error` 或 `Failed to fetch`

**原因**：`.env.docker` 中的 `RAGFLOW_BASE_URL` 配置错误

**解决**：
1. 确认 RAGFlow 服务可访问：`curl http://服务器IP:9380/api/v1/health`
2. 修改 `.env.docker` 中的 `RAGFLOW_BASE_URL` 为正确的 IP
3. 重新构建：`docker-compose up -d --build`

### 2. 修改配置后不生效

**原因**：前端配置是在构建时写入的，需要重新构建镜像

**解决**：
```bash
docker-compose down
docker-compose up -d --build
```
