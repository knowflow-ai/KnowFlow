# MinerU 服务部署说明

MinerU 是一个高精度的 PDF OCR 解析服务，用于提取 PDF 文档中的文本、表格、公式等内容。

## 系统要求

- Docker 和 Docker Compose
- NVIDIA GPU（推荐）
- nvidia-docker（GPU 支持）
- 至少 8GB GPU 显存

## 快速启动

### 1. 基础部署（仅 API 服务）

```bash
# 进入 mineru 目录
cd mineru

# 启动 MinerU API 服务
docker compose up -d

# 查看日志
docker compose logs -f mineru-api

# 测试服务
curl http://localhost:8000/health
```

### 2. 完整部署（包含 VLM 高级 OCR）

如果需要使用 VLM 进行高级图表识别：

```bash
# 启动 API + VLM 服务
docker compose --profile vllm up -d

# 查看所有服务状态
docker compose ps
```

## 配置说明

编辑 `.env` 文件进行配置：

### 基础配置

```bash
# Docker 镜像版本
MINERU_IMAGE=zxwei/mineru-api-full:v2.5.4

# API 服务端口（默认 8000）
MINERU_API_PORT=8000

# VLM 服务端口（默认 30000）
MINERU_VLLM_PORT=30000
```

### GPU 配置

```bash
# 单 GPU 配置
MINERU_GPU_DEVICE_IDS=0

# 多 GPU 配置（使用逗号分隔）
MINERU_GPU_DEVICE_IDS=0,1,2
```

### 模型配置

```bash
# 模型来源
MINERU_MODEL_SOURCE=local     # local: 使用预下载的模型
                              # huggingface: 从 HuggingFace 下载

# 模型是否已预下载到镜像中
MINERU_MODELS_PRELOADED=true
```

## 多服务器部署

### 场景 1: MinerU 独立部署

如果 MinerU 部署在独立服务器（例如：192.168.1.100），需要在 KnowFlow 主服务中配置：

```yaml
# 在 KnowFlow 主服务的 docker/knowflow-server/settings.yaml 中：
mineru:
  fastapi:
    url: "http://192.168.1.100:8000"  # 👈 修改为 MinerU 服务器 IP
```

### 场景 2: 同服务器部署

MinerU 和 KnowFlow 在同一服务器：

```yaml
# 在 docker/knowflow-server/settings.yaml 中：
mineru:
  fastapi:
    url: "http://localhost:8000"
```

### 场景 3: Docker 网络部署

如果 MinerU 和 KnowFlow 在同一 Docker 网络中，可以使用容器名：

```yaml
mineru:
  fastapi:
    url: "http://knowflow-mineru-api:8000"
```

## 常用命令

```bash
# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 查看服务状态
docker compose ps

# 进入容器
docker compose exec mineru-api bash

# 查看 GPU 使用情况
nvidia-smi
```

## API 测试

### 健康检查

```bash
curl http://localhost:8000/health
```

### 解析 PDF 文件

```bash
curl -X POST http://localhost:8000/api/parse \
  -F "file=@/path/to/document.pdf" \
  -F "from_page=0" \
  -F "to_page=10"
```

## VLM 高级功能

### 启用 VLM 服务

1. 启动 VLM 服务：
```bash
docker compose --profile vllm up -d
```

2. 在 KnowFlow 配置中启用 VLM：
```yaml
# docker/knowflow-server/settings.yaml
mineru:
  default_backend: "vlm-http-client"  # 切换到 VLM 后端
  vlm:
    http_client:
      server_url: "http://192.168.1.100:30000"  # VLM 服务地址
```

### VLM 优势

- ✅ 更好的图表识别能力
- ✅ 复杂表格提取更准确
- ✅ 手写内容识别
- ⚠️ 需要更多 GPU 资源

## 性能优化

### 多 GPU 加速

如果有多张 GPU，可以配置张量并行：

```bash
# .env 文件
MINERU_GPU_DEVICE_IDS=0,1,2,3
```

### 内存优化

如果 GPU 显存有限，可以调整：

1. 只运行 API 服务（不启动 VLM）
2. 减小批处理大小
3. 使用更小的模型

## 故障排查

### 1. GPU 不可用

**错误**: `RuntimeError: No GPU available`

**解决方案**:
```bash
# 检查 GPU 状态
nvidia-smi

# 检查 nvidia-docker
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# 确认 docker-compose.yml 中 GPU 配置正确
```

### 2. 端口冲突

**错误**: `port 8000 already in use`

**解决方案**:
```bash
# 修改 .env 文件中的端口
MINERU_API_PORT=8001

# 重启服务
docker compose down && docker compose up -d
```

### 3. 模型下载失败

**错误**: `Failed to download model`

**解决方案**:
```bash
# 使用预下载的模型镜像
MINERU_MODEL_SOURCE=local
MINERU_MODELS_PRELOADED=true

# 或设置 HuggingFace 镜像
export HF_ENDPOINT=https://hf-mirror.com
```

### 4. 内存不足

**错误**: `CUDA out of memory`

**解决方案**:
1. 确保 GPU 有足够显存（推荐 8GB+）
2. 关闭其他占用 GPU 的程序
3. 只运行 API 服务，不启动 VLM

### 5. 服务无法访问

**检查清单**:
```bash
# 1. 检查服务是否运行
docker compose ps

# 2. 检查日志
docker compose logs mineru-api | tail -50

# 3. 检查端口
netstat -tlnp | grep 8000

# 4. 测试本地访问
curl http://localhost:8000/health

# 5. 检查防火墙（Linux）
sudo ufw status
sudo ufw allow 8000/tcp
```

## 版本更新

### 更新到新版本

```bash
# 1. 修改 .env 中的镜像版本
MINERU_IMAGE=zxwei/mineru-api-full:v2.5.5  # 新版本

# 2. 拉取新镜像
docker compose pull

# 3. 重启服务
docker compose down && docker compose up -d
```

## 资源监控

### 监控 GPU 使用情况

```bash
# 实时监控
watch -n 1 nvidia-smi

# 查看容器资源使用
docker stats knowflow-mineru-api
```

### 日志管理

```bash
# 查看最近 100 行日志
docker compose logs --tail=100 mineru-api

# 跟踪日志
docker compose logs -f mineru-api

# 清理日志（谨慎操作）
docker compose down
docker volume prune
```

## 更多帮助

- MinerU 官方文档: https://github.com/opendatalab/MinerU
- KnowFlow 配置: 查看 `../knowflow-server/README.md`
- 主服务部署: 查看 `../README.md`
