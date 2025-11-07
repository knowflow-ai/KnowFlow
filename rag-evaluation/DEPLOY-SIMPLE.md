# RAG 评估系统部署指南

## 快速部署

### 1. 修改配置

编辑 `.env.docker`：

```bash
# 修改 RAGFlow 配置
RAGFLOW_BASE_URL=http://ragflow:9380  # 如果在同一 Docker 网络
# 或者
RAGFLOW_BASE_URL=http://192.168.1.100:9380  # 如果在其他服务器

RAGFLOW_API_KEY=ragflow-your-actual-api-key

# 修改 LLM 配置
SILICONFLOW_API_KEY=sk-your-actual-api-key
```

### 2. 构建和启动

```bash
docker-compose build --no-cache
docker-compose up -d
```

### 3. 访问服务

浏览器打开：`http://服务器IP:5003`

## 架构说明

```
浏览器 
  ↓
Nginx (80端口)
  ├─ /api/v1/* → 后端 API (5002端口)
  └─ /api/ragflow/* → 后端代理 → RAGFlow
```

**优势**：
- ✅ 前端只需配置一次，使用相对路径
- ✅ RAGFlow 配置统一在 `.env.docker`
- ✅ 支持 RAGFlow 在任何位置（同网络或远程服务器）
- ✅ 无需暴露 RAGFlow API Key 给前端

## 配置说明

### RAGFLOW_BASE_URL

- **同一 Docker 网络**：`http://ragflow:9380`（推荐）
- **其他服务器**：`http://192.168.1.100:9380`
- **本地开发**：`http://localhost:9380`

后端会自动添加 API Key，前端无需关心。

## 故障排查

### 1. 无法访问 RAGFlow

检查后端日志：
```bash
docker logs rag-evaluation 2>&1 | grep "RAGFlow proxy"
```

### 2. 修改配置后不生效

只需重启容器（无需重新构建）：
```bash
docker-compose restart
```
