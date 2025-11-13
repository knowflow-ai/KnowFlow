# PaddleOCR 独立部署指南

[PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) 是一个强大的 OCR 工具，支持文档解析、版面分析和文字识别。本目录提供了 PaddleOCR 的 Docker 独立部署方案。

## 📋 目录结构

```
paddleocr/
├── docker-compose.yml      # Docker Compose 配置文件
├── Dockerfile             # PaddleOCR API 镜像构建文件
├── pipeline_config.yaml   # PaddleOCR 流水线配置
├── .env.example          # 环境变量示例文件
└── README.md             # 本文档
```

## 🚀 快速开始

### 前置要求

- Docker >= 20.10
- Docker Compose >= 2.0
- NVIDIA GPU（支持 CUDA 12.6）
- NVIDIA Docker Runtime

### 1. 复制环境变量文件

```bash
cd /Users/zxwei/zhishi/KnowFlow/docker/paddleocr
cp .env.example .env
```

### 2. 修改配置（可选）

编辑 `.env` 文件：

```bash
# 修改服务端口（默认 8888）
PADDLEOCR_API_PORT=8888

# 修改 GPU 设备 ID（默认使用 GPU 0）
GPU_DEVICE_ID=0
```

### 3. 启动服务

```bash
# 使用预构建镜像启动（推荐）
docker-compose up -d

# 或者本地构建镜像后启动
docker-compose up -d --build
```

### 4. 验证服务

```bash
# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f paddleocr-api

# 健康检查
curl http://localhost:8888/health
```

## 📦 服务架构

本部署包含两个核心服务：

### 1. paddleocr-api
- **端口**: 8888 (可配置)
- **功能**: PaddleOCR-VL API 服务，提供文档解析接口
- **GPU**: 需要 NVIDIA GPU
- **依赖**: paddleocr-vllm 服务

### 2. paddleocr-vllm
- **端口**: 内部端口 8080 (不对外暴露)
- **功能**: GenAI vLLM 推理后端，支持 PaddleOCR-VL 模型
- **GPU**: 需要 NVIDIA GPU

## 🔧 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `PADDLEOCR_API_PORT` | 8888 | API 服务对外端口 |
| `GPU_DEVICE_ID` | 0 | 使用的 GPU 设备 ID |
| `CUDA_VISIBLE_DEVICES` | 0 | CUDA 可见设备 |
| `BUILD_FOR_OFFLINE` | false | 是否在构建时下载模型 |

### Pipeline 配置

编辑 `pipeline_config.yaml` 可以自定义：

- **batch_size**: 批处理大小
- **use_layout_detection**: 是否启用版面检测
- **use_chart_recognition**: 是否启用图表识别
- **threshold**: 各类别检测阈值

## 📝 API 使用示例

### 基础 OCR

```bash
curl -X POST http://localhost:8888/ocr \
  -F "file=@document.pdf" \
  -F "return_format=json"
```

### 带版面分析的文档解析

```python
import requests

url = "http://localhost:8888/parse"
files = {'file': open('document.pdf', 'rb')}
params = {
    'use_layout': True,
    'format': 'markdown'
}

response = requests.post(url, files=files, params=params)
print(response.json())
```

## 🛠️ 常用命令

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 只查看 API 服务日志
docker-compose logs -f paddleocr-api

# 只查看 vLLM 服务日志
docker-compose logs -f paddleocr-vllm
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启单个服务
docker-compose restart paddleocr-api
```

### 停止服务

```bash
# 停止服务（保留数据）
docker-compose stop

# 停止并删除容器（保留数据卷）
docker-compose down

# 完全清理（包括数据卷）
docker-compose down -v
```

### 更新服务

```bash
# 拉取最新镜像
docker-compose pull

# 重新构建并启动
docker-compose up -d --build
```

## 📊 性能优化

### GPU 内存优化

如果遇到 GPU 内存不足，可以调整 `pipeline_config.yaml`：

```yaml
batch_size: 32  # 减小批处理大小

SubModules:
  VLRecognition:
    batch_size: 1024  # 减小 VL 识别批处理大小
```

### 多 GPU 支持

修改 `.env` 文件：

```bash
# 使用多个 GPU
CUDA_VISIBLE_DEVICES=0,1
GPU_DEVICE_ID=0,1
```

修改 `docker-compose.yml`：

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          device_ids: ["0", "1"]  # 指定多个 GPU
          capabilities: [gpu]
```

## 🔍 故障排查

### 服务无法启动

1. **检查 GPU 驱动**
   ```bash
   nvidia-smi
   ```

2. **检查 Docker GPU 支持**
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi
   ```

3. **查看详细错误日志**
   ```bash
   docker-compose logs paddleocr-api
   ```

### 模型下载失败

首次启动时，服务会自动下载模型（约 2-3GB），可能需要较长时间。如果下载失败：

1. **检查网络连接**
2. **使用离线模式构建**：
   ```bash
   # 修改 .env
   BUILD_FOR_OFFLINE=true

   # 重新构建镜像
   docker-compose build --build-arg BUILD_FOR_OFFLINE=true
   ```

### 端口冲突

如果默认端口 8888 被占用：

```bash
# 修改 .env
PADDLEOCR_API_PORT=8889

# 重启服务
docker-compose up -d
```

## 📚 集成到 KnowFlow

在 KnowFlow 主配置文件中配置 PaddleOCR 服务：

```yaml
# knowflow/server/services/config/settings.yaml
paddleocr:
  enabled: true
  api_url: http://localhost:8888
  timeout: 300
```

## 🔗 相关链接

- [PaddleOCR 官方文档](https://github.com/PaddlePaddle/PaddleOCR)
- [PaddleX 文档](https://github.com/PaddlePaddle/PaddleX)
- [PaddleOCR-VL 模型](https://github.com/PaddlePaddle/PaddleOCR/blob/main/doc/ppocr/blog/VL.md)

## 📄 许可证

本部署配置遵循 KnowFlow 项目许可证。PaddleOCR 本身遵循 Apache 2.0 许可证。

## 🤝 贡献

如有问题或建议，请在 KnowFlow 项目中提 Issue。
