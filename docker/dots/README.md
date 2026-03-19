# DOTS OCR 服务部署说明

DOTS OCR 是基于视觉语言模型的高精度 OCR 服务，提供优秀的图片和文档识别能力。

## 系统要求

- Docker 和 Docker Compose
- NVIDIA GPU（推荐）
- nvidia-docker（GPU 支持）
- 至少 16GB GPU 显存（推荐）

## 前置准备

### 下载 DOTS 模型

在部署前，需要下载 DOTS OCR 模型：

```bash
# 1. 安装 modelscope CLI（如果还没安装）
pip install modelscope

# 2. 下载模型
modelscope download --model rednote-hilab/dots.ocr --local_dir ./weights/DotsOCR

# 或者手动下载
# 访问: https://www.modelscope.cn/models/rednote-hilab/dots.ocr
# 下载所有文件到 ./weights/DotsOCR/ 目录
```

**目录结构**:
```
dots/
├── docker-compose.yml
├── .env
├── README.md
└── weights/
    └── DotsOCR/          # 👈 模型文件存放位置
        ├── config.json
        ├── modeling_dots_ocr_vllm.py
        ├── preprocessor_config.json
        ├── model-xxxxx.safetensors
        └── ...
```

## 快速启动

```bash
# 1. 确保模型已下载到 weights/DotsOCR/
ls weights/DotsOCR/

# 2. 启动 DOTS OCR 服务
docker compose up -d

# 3. 查看日志
docker compose logs -f

# 4. 测试服务（等待模型加载完成，约 1-2 分钟）
curl http://localhost:8000/v1/models
```

## 配置说明

编辑 `.env` 文件进行配置：

### 基础配置

```bash
# Docker 镜像
DOTS_IMAGE=rednotehilab/dots.ocr:vllm-openai-v0.9.1

# 服务端口
DOTS_PORT=8000

# 模型目录（相对路径或绝对路径）
DOTS_MODEL_DIR=./weights/DotsOCR
```

### GPU 配置

```bash
# 单 GPU
DOTS_GPU_DEVICE_IDS=0

# 多 GPU（张量并行）
DOTS_GPU_DEVICE_IDS=0,1
DOTS_TENSOR_PARALLEL_SIZE=2  # 与 GPU 数量一致
```

### 性能配置

```bash
# GPU 内存利用率（0.0-1.0）
# 如果显存不足，可以降低此值
DOTS_GPU_MEMORY_UTILIZATION=0.8

# 模型名称
DOTS_MODEL_NAME=dotsocr-model
```

## 多服务器部署

### 场景 1: DOTS 独立部署

DOTS 部署在独立服务器（例如：192.168.1.101），在 KnowFlow 主服务中配置：

```yaml
# 在 KnowFlow 主服务的 docker/knowflow-server/settings.yaml 中：
dots:
  vllm:
    url: "http://192.168.1.101:8000"  # 👈 修改为 DOTS 服务器 IP
```

### 场景 2: 同服务器部署

DOTS 和 KnowFlow 在同一服务器：

```yaml
# 在 docker/knowflow-server/settings.yaml 中：
dots:
  vllm:
    url: "http://localhost:8000"
```

注意：如果同服务器还运行 MinerU，需要修改端口避免冲突：
```bash
# DOTS .env 文件
DOTS_PORT=8001
```

### 场景 3: Docker 网络部署

DOTS 和 KnowFlow 在同一 Docker 网络中：

```yaml
dots:
  vllm:
    url: "http://knowflow-dots-ocr:8000"
```

## 常用命令

```bash
# 启动服务
docker compose up -d

# 查看日志（跟踪启动过程）
docker compose logs -f

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 查看服务状态
docker compose ps

# 进入容器
docker compose exec dots-ocr-server bash

# 查看 GPU 使用
nvidia-smi
```

## API 测试

### 检查模型列表

```bash
curl http://localhost:8000/v1/models
```

### OCR 识别测试

```bash
# 使用 OpenAI 兼容 API
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "dotsocr-model",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "识别图片中的文字"},
          {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
        ]
      }
    ]
  }'
```

## 性能优化

### 多 GPU 加速

如果有多张 GPU，可以启用张量并行：

```bash
# .env 文件
DOTS_GPU_DEVICE_IDS=0,1,2,3
DOTS_TENSOR_PARALLEL_SIZE=4  # 与 GPU 数量一致
```

### 内存优化

如果 GPU 显存不足：

```bash
# 降低 GPU 内存利用率
DOTS_GPU_MEMORY_UTILIZATION=0.6  # 从 0.8 降到 0.6

# 或使用更少的 GPU
DOTS_GPU_DEVICE_IDS=0
DOTS_TENSOR_PARALLEL_SIZE=1
```

## 故障排查

### 1. 模型加载失败

**错误**: `FileNotFoundError: weights/DotsOCR not found`

**解决方案**:
```bash
# 检查模型目录
ls -la weights/DotsOCR/

# 如果没有模型，重新下载
modelscope download --model rednote-hilab/dots.ocr --local_dir ./weights/DotsOCR

# 检查 .env 配置
cat .env | grep DOTS_MODEL_DIR
```

### 2. GPU 不可用

**错误**: `No GPU available`

**解决方案**:
```bash
# 检查 GPU
nvidia-smi

# 检查 nvidia-docker
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# 确认 GPU 配置
cat .env | grep DOTS_GPU_DEVICE_IDS
```

### 3. 显存不足

**错误**: `CUDA out of memory`

**解决方案**:
```bash
# 方案 1: 降低内存利用率
DOTS_GPU_MEMORY_UTILIZATION=0.6

# 方案 2: 使用更多 GPU 分担负载
DOTS_GPU_DEVICE_IDS=0,1
DOTS_TENSOR_PARALLEL_SIZE=2

# 方案 3: 关闭其他占用 GPU 的程序
nvidia-smi  # 查看哪些进程在使用 GPU
```

### 4. 端口冲突

**错误**: `port 8000 already in use`

**解决方案**:
```bash
# 修改 .env 文件
DOTS_PORT=8001

# 重启服务
docker compose down && docker compose up -d

# 更新 KnowFlow 配置中的端口
# docker/knowflow-server/settings.yaml:
# dots.vllm.url: "http://localhost:8001"
```

### 5. 模型加载缓慢

**现象**: 启动后长时间显示 "Loading model..."

**说明**: DOTS 模型较大（约 10GB+），首次加载需要 1-3 分钟，这是正常现象。

**优化**:
- 使用 SSD 存储模型
- 预热模型（第一次请求会慢）

### 6. 服务无法访问

**检查清单**:
```bash
# 1. 检查服务状态
docker compose ps

# 2. 检查日志
docker compose logs dots-ocr-server | tail -100

# 3. 检查端口
netstat -tlnp | grep 8000

# 4. 测试本地访问
curl http://localhost:8000/v1/models

# 5. 检查防火墙
sudo ufw status
sudo ufw allow 8000/tcp
```

## 版本更新

```bash
# 1. 停止服务
docker compose down

# 2. 更新镜像版本
# 编辑 .env
DOTS_IMAGE=rednotehilab/dots.ocr:vllm-openai-v0.9.2  # 新版本

# 3. 拉取新镜像
docker compose pull

# 4. 启动服务
docker compose up -d
```

## 资源监控

### 实时监控

```bash
# GPU 使用情况
watch -n 1 nvidia-smi

# 容器资源
docker stats knowflow-dots-ocr

# 查看日志
docker compose logs -f --tail=50
```

### 性能指标

正常运行时的资源使用参考：

- **GPU 显存**: 10-14GB（单卡）
- **GPU 利用率**: 推理时 30-80%
- **启动时间**: 1-3 分钟

## 高级配置

### 自定义 vLLM 参数

如需修改更多 vLLM 参数，编辑 `docker-compose.yml` 的 command 部分：

```yaml
command:
  - -c
  - |
    exec vllm serve /workspace/weights/DotsOCR \
        --tensor-parallel-size ${DOTS_TENSOR_PARALLEL_SIZE:-1} \
        --gpu-memory-utilization ${DOTS_GPU_MEMORY_UTILIZATION:-0.8} \
        --max-model-len 8192 \                    # 👈 最大序列长度
        --max-num-seqs 256 \                      # 👈 最大并发序列数
        --chat-template-content-format string \
        --served-model-name ${DOTS_MODEL_NAME:-dotsocr-model} \
        --trust-remote-code \
        --host 0.0.0.0 \
        --port 8000
```

## 常见问题

**Q: DOTS 和 MinerU 有什么区别？**

A:
- **MinerU**: 专注于 PDF 文档解析，支持表格、公式提取
- **DOTS**: 通用 OCR 服务，支持图片和文档，视觉理解能力更强

**Q: 可以同时使用 DOTS 和 MinerU 吗？**

A: 可以！它们各有优势，可以根据文档类型选择使用。

**Q: DOTS 需要多少显存？**

A: 建议至少 16GB，单卡部署推荐 24GB 以获得最佳性能。

**Q: 支持 CPU 部署吗？**

A: 不推荐。DOTS 模型较大，CPU 推理速度非常慢。

## 更多帮助

- DOTS OCR 模型: https://www.modelscope.cn/models/rednote-hilab/dots.ocr
- vLLM 文档: https://docs.vllm.ai/
- KnowFlow 配置: 查看 `../knowflow-server/README.md`
- 主服务部署: 查看 `../README.md`
