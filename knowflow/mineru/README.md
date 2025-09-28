# KnowFlow MinerU 2.5 集成

本目录包含 MinerU 2.5 的离线镜像构建和集成配置，支持在离线环境中使用最新的 MinerU OCR 功能。

## 特性

- ✅ 基于 MinerU 2.5 官方镜像
- ✅ 预下载所有模型文件，支持完全离线运行
- ✅ 使用官方 API 接口，无需维护自定义代码
- ✅ 支持 Pipeline 和 VLM 两种后端
- ✅ 与 KnowFlow 无缝集成

## 目录结构

```
knowflow/mineru/
├── Dockerfile           # 多阶段构建，内置模型文件
├── download_models.py   # 模型下载脚本
├── build.sh            # 镜像构建脚本
├── docker-compose.yml  # 独立部署配置
└── README.md          # 本文档
```

## 快速开始

### 1. 构建离线镜像

```bash
cd knowflow/mineru

# 构建包含所有模型的离线镜像（约 20GB）
./build.sh

# 或指定 VLM 模型
./build.sh --vlm-model qwen2_vl

# 构建并推送到镜像仓库
./build.sh --push
```

### 2. 启动服务

#### 方式一：与 KnowFlow 集成部署

```bash
cd docker

# 启动所有服务（包括 MinerU API）
docker compose -f docker-compose.yml -f docker-compose-mineru.yml up -d

# 启动包括 VLM 服务（需要更多 GPU 内存）
docker compose -f docker-compose.yml -f docker-compose-mineru.yml --profile vllm up -d
```

#### 方式二：独立部署

```bash
cd knowflow/mineru

# 仅启动 MinerU API
docker compose up -d mineru-api

# 启动 API 和 VLM 服务
docker compose --profile vllm up -d
```

### 3. 验证服务

```bash
# 检查 API 服务
curl http://localhost:8000/docs

# 检查 VLM 服务（如果启用）
curl http://localhost:30000/health
```

## 配置说明

### 环境变量

```bash
# MinerU API 端口
MINERU_API_PORT=8000

# VLM 服务端口
MINERU_VLLM_PORT=30000

# 时区设置
TIMEZONE=Asia/Shanghai
```

### KnowFlow 集成配置

在 `knowflow/server/services/config/settings.yaml` 中：

```yaml
mineru:
  fastapi:
    # Docker 内部通信地址
    url: "http://knowflow-mineru-api:8000"
    timeout: 30000

  # 默认后端：pipeline（基础）或 vlm-sglang-client（高级）
  default_backend: "pipeline"

  vlm:
    sglang:
      server_url: "http://knowflow-mineru-vllm:30000"
```

## 模型说明

### 基础模型（Pipeline 后端）

- **LayoutReader**: 版面分析模型（350MB）
- **TableMaster**: 表格识别模型（250MB）
- **LayoutLMv3**: 文档理解模型（420MB）
- **OCR 模型**: 中文 OCR 识别（45MB）
- **Formula 模型**: 公式检测（22MB）

### VLM 模型（高级 OCR）

- **GOT-OCR2_0**: 通用 OCR 模型（6GB）
- **Qwen2-VL-7B**: 视觉语言模型（14GB）

## 使用建议

### 资源需求

- **基础版（Pipeline）**:
  - GPU: 4GB VRAM
  - 内存: 8GB
  - 磁盘: 30GB

- **高级版（VLM）**:
  - GPU: 16GB VRAM
  - 内存: 32GB
  - 磁盘: 50GB

### 性能优化

1. **GPU 内存不足时**：
   ```yaml
   # 在 docker-compose 中添加参数
   command:
     - mineru-api
     - --gpu-memory-utilization
     - "0.5"  # 降低 KV 缓存大小
   ```

2. **多 GPU 加速**：
   ```yaml
   command:
     - mineru-vllm-server
     - --data-parallel-size
     - "2"  # 使用 2 个 GPU
   ```

3. **限制转换页数**：
   ```yaml
   command:
     - mineru-api
     - --max-convert-pages
     - "20"  # 限制最大页数
   ```

## 故障排查

### 常见问题

1. **模型下载失败**
   - 检查网络连接
   - 使用代理：`export https_proxy=http://your-proxy:port`
   - 手动下载模型放入对应目录

2. **GPU 不可用**
   - 确保安装 NVIDIA Docker Runtime
   - 检查驱动版本：`nvidia-smi`
   - 验证 CUDA 版本 >= 12.1

3. **内存不足**
   - 减少并发处理数
   - 调整 GPU 内存利用率
   - 使用 Pipeline 后端代替 VLM

### 日志查看

```bash
# 查看 API 日志
docker logs knowflow-mineru-api

# 查看 VLM 日志
docker logs knowflow-mineru-vllm

# 实时跟踪日志
docker logs -f knowflow-mineru-api
```

## 更新维护

### 更新模型

```bash
# 重新下载最新模型
python download_models.py --type all

# 仅更新 VLM 模型
python download_models.py --type vlm
```

### 版本升级

1. 更新基础镜像版本
2. 重新构建：`./build.sh --no-cache`
3. 重启服务：`docker compose down && docker compose up -d`

## 许可证

遵循 MinerU 和 KnowFlow 的开源许可证。