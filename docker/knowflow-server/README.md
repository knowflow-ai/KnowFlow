# KnowFlow Server 配置说明

## 配置文件

- `settings.yaml` - KnowFlow Server 的核心业务配置文件
- `settings.yaml.example` - 配置模板文件
- `CONFIG_LOADING.md` - 配置加载机制详细说明

## 重要说明

**本地开发和 Docker 部署统一使用此配置文件**：

- ✅ **本地开发**: 自动从 `docker/knowflow-server/settings.yaml` 加载配置
- ✅ **Docker 部署**: 通过 volume 挂载此文件到容器内
- ✅ **统一管理**: 修改一处配置，本地和容器环境同步生效

配置文件加载优先级：
1. 环境变量 `KNOWFLOW_SETTINGS_PATH`（最高优先级）
2. `docker/knowflow-server/settings.yaml`（推荐，本地开发自动使用）
3. `knowflow/server/services/config/settings.yaml`（向后兼容，已废弃）

详细的配置加载机制说明请查看：[CONFIG_LOADING.md](./CONFIG_LOADING.md)

## 快速配置

### 1. 初次部署

如果这是第一次部署，从模板创建配置文件：

```bash
cp settings.yaml.example settings.yaml
```

### 2. 配置 MinerU 服务地址

编辑 `settings.yaml`，找到 `mineru.fastapi.url` 并修改：

```yaml
mineru:
  fastapi:
    url: "http://your-mineru-server:8000"  # 👈 修改为实际地址
```

**部署场景示例：**

| 场景 | URL 配置 | 说明 |
|------|---------|------|
| MinerU 部署在同一服务器 | `http://localhost:8000` | 通过宿主机网络访问 |
| MinerU 部署在独立服务器 | `http://192.168.1.100:8000` | 替换为实际 IP 地址 |
| MinerU 在同一 Docker 网络 | `http://knowflow-mineru-api:8000` | 通过容器名访问 |

### 3. 配置 DOTS 服务地址

编辑 `settings.yaml`，找到 `dots.vllm.url` 并修改：

```yaml
dots:
  vllm:
    url: "http://your-dots-server:8000"  # 👈 修改为实际地址
```

部署场景同 MinerU。

### 4. （可选）启用 VLM 高级 OCR

如果需要使用 MinerU 的 VLM 后端进行高级 OCR：

1. 修改后端类型：
```yaml
mineru:
  default_backend: "vlm-http-client"  # 切换到 VLM 后端
```

2. 配置 VLM 服务地址：
```yaml
mineru:
  vlm:
    http_client:
      server_url: "http://your-vlm-server:30000"  # 配置 VLM 服务地址
```

### 5. 重启服务使配置生效

```bash
cd /path/to/docker
docker compose restart knowflow-backend
```

## 配置参数说明

### app 配置

- **dev_mode**: 开发模式开关
  - `true`: 启用详细日志，输出调试信息
  - `false`: 生产模式（推荐）

### mineru 配置

- **default_backend**: MinerU 后端类型
  - `pipeline`: 标准解析后端（默认，推荐）
  - `vlm-http-client`: 视觉语言模型后端（需要 VLM 服务）

- **fastapi.url**: MinerU API 服务地址 **（必填）**
- **fastapi.timeout**: HTTP 请求超时时间（秒），默认 60000

- **pipeline.parse_method**: 解析方法
  - `auto`: 自动选择（推荐）
  - `txt`: 文本提取
  - `ocr`: OCR 识别

- **pipeline.lang**: 文档语言
  - `ch`: 中文
  - `en`: 英文

- **pipeline.formula_enable**: 是否启用公式解析（true/false）
- **pipeline.table_enable**: 是否启用表格解析（true/false）

### dots 配置

- **vllm.url**: DOTS OCR 服务地址 **（必填）**
- **vllm.model_name**: 模型名称（与 DOTS 部署配置一致）
- **vllm.timeout**: 请求超时时间（秒）
- **vllm.temperature**: 生成温度（0.0-1.0）
- **vllm.top_p**: Top-P 采样参数
- **vllm.max_completion_tokens**: 最大生成 token 数

## 部署场景示例

### 场景 1: 单服务器部署（所有服务在一台机器）

```yaml
mineru:
  fastapi:
    url: "http://localhost:8000"

dots:
  vllm:
    url: "http://localhost:8001"  # DOTS 使用不同端口
```

### 场景 2: 多服务器部署

```yaml
# KnowFlow 主服务在 服务器A (192.168.1.10)
# MinerU 在 服务器B (192.168.1.20)
# DOTS 在 服务器C (192.168.1.30)

mineru:
  fastapi:
    url: "http://192.168.1.20:8000"

dots:
  vllm:
    url: "http://192.168.1.30:8000"
```

### 场景 3: Docker 同网络部署

如果 MinerU/DOTS 容器在同一个 Docker 网络中：

```yaml
mineru:
  fastapi:
    url: "http://knowflow-mineru-api:8000"

dots:
  vllm:
    url: "http://knowflow-dots-ocr:8000"
```

## 故障排查

### 1. 连接 MinerU/DOTS 失败

**错误信息**: `Cannot connect to MinerU/DOTS server`

**解决方案**:
1. 检查 `settings.yaml` 中的 URL 配置是否正确
2. 确认 MinerU/DOTS 服务是否已启动：
   ```bash
   # 检查 MinerU
   curl http://your-server:8000/health

   # 检查 DOTS
   curl http://your-server:8000/v1/models
   ```
3. 检查网络连通性（防火墙、端口是否开放）
4. 如果使用 Docker 网络，确认容器在同一网络中

### 2. 配置修改未生效

**解决方案**:
1. 确认已修改 `docker/knowflow-server/settings.yaml`（而非源码中的文件）
2. 重启 knowflow-backend 服务：
   ```bash
   docker compose restart knowflow-backend
   ```
3. 查看日志确认配置加载：
   ```bash
   docker compose logs knowflow-backend | grep "加载的配置"
   ```

### 3. 开发模式日志过多

**解决方案**:
1. 编辑 `settings.yaml`，设置 `app.dev_mode: false`
2. 重启服务：
   ```bash
   docker compose restart knowflow-backend
   ```

### 4. MinerU/DOTS 服务地址配置错误

**常见错误**:
- ❌ `http://localhost:8000` - 在 Docker 容器内，localhost 指向容器自身
- ✅ `http://host.docker.internal:8000` - Docker Desktop 访问宿主机
- ✅ `http://192.168.1.100:8000` - 使用实际 IP 地址
- ✅ `http://knowflow-mineru-api:8000` - 使用 Docker 容器名（需在同一网络）

### 5. 查看详细日志

如果遇到问题，开启开发模式查看详细日志：

```yaml
app:
  dev_mode: true
```

重启服务后查看日志：
```bash
docker compose logs -f knowflow-backend
```

## 高级配置

### 性能优化

对于大文件处理，可以调整超时时间：

```yaml
mineru:
  fastapi:
    timeout: 120000  # 增加到 120 秒

dots:
  vllm:
    timeout: 120000
```

### VLM 高级配置

使用 VLM 后端可获得更好的图表识别效果，但需要更多资源：

```yaml
mineru:
  default_backend: "vlm-http-client"
  vlm:
    http_client:
      server_url: "http://your-vlm-server:30000"
```

注意：VLM 服务需要独立部署，参考 `mineru/README.md` 中的 VLM 部署说明。

## 更多帮助

- MinerU 服务部署：查看 `../mineru/README.md`
- DOTS 服务部署：查看 `../dots/README.md`
- 主服务部署：查看 `../README.md`
