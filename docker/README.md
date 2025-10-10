# KnowFlow Docker 部署指南

<details open>
<summary></b>📗 Table of Contents</b></summary>

- 🚀 [快速开始](#-快速开始)
- 📦 [部署架构](#-部署架构)
- 🐳 [Docker Compose](#-docker-compose)
- 🐬 [Docker environment variables](#-docker-environment-variables)
- 🐋 [Service configuration](#-service-configuration)
- 🔧 [KnowFlow 配置](#-knowflow-配置)
- 🖥️ [部署场景](#-部署场景)
- 📋 [Setup Examples](#-setup-examples)
- 🛠️ [故障排查](#-故障排查)

</details>

---

## 🚀 快速开始

### 方式一：自动部署脚本（推荐，零配置）

完整的交互式部署流程，自动配置所有服务：

```bash
# 运行自动部署脚本
./scripts/deploy.sh
```

**部署流程**：
1. ✅ 选择要安装的 OCR 服务（MinerU/DOTS）
2. ✅ 选择部署模式（CPU/GPU）
3. ✅ 自动配置服务地址和端口
4. ✅ 自动更新 settings.yaml
5. ✅ 自动启动所有服务
6. ✅ 显示访问地址和登录信息

**访问服务**：
- 🌐 前端: http://localhost
- 🔌 API: http://localhost:9380
- 👤 默认账号: admin@gmail.com / admin

详细说明请查看：[scripts/README.md](scripts/README.md)

### 方式二：快速启动（适用于已配置环境）

```bash
# 启动主服务
./scripts/quick-start.sh

# 启动所有服务（包括 MinerU 和 DOTS）
./scripts/quick-start.sh --all

# 停止服务
./scripts/quick-start.sh --stop

# 查看状态
./scripts/quick-start.sh --status
```

### 方式三：手动启动

```bash
# 1. 配置环境
cp .env.example .env
cp knowflow-server/settings.yaml.example knowflow-server/settings.yaml

# 2. 编辑配置（可选）
vim .env
vim knowflow-server/settings.yaml

# 3. 启动服务
docker compose up -d

# 4. 查看日志
docker compose logs -f

# 5. 检查服务状态
docker compose ps
```

---

## 📦 部署架构

KnowFlow 采用模块化部署架构，支持灵活的分布式部署：

```
KnowFlow 部署架构
├── 主服务 (docker-compose.yml)
│   ├── RAGFlow 前端 (端口 80/443)
│   ├── RAGFlow API (端口 9380)
│   ├── KnowFlow Server (端口 5000)
│   ├── MySQL (端口 5455)
│   ├── Elasticsearch (端口 1200)
│   ├── MinIO (端口 9000, 9001)
│   └── Redis (端口 6379)
│
├── MinerU 服务 (mineru/docker-compose.yml) - 可独立部署
│   ├── MinerU API (端口 8000)
│   └── MinerU VLM (端口 30000, 可选)
│
└── DOTS 服务 (dots/docker-compose.yml) - 可独立部署
    └── DOTS OCR Server (端口 8000)
```

**核心特性**:
- ✅ **独立部署**: MinerU 和 DOTS 可部署在不同服务器
- ✅ **灵活配置**: 通过 `knowflow-server/settings.yaml` 配置服务地址
- ✅ **GPU 支持**: MinerU/DOTS 支持多 GPU 并行
- ✅ **一键启动**: 提供自动化部署脚本

---

## 🔧 KnowFlow 配置

### KnowFlow Server 业务配置

配置文件位置: `knowflow-server/settings.yaml`

**重要**: 此文件控制 KnowFlow 的业务逻辑，包括 MinerU/DOTS 服务地址配置。

```yaml
# 应用配置
app:
  dev_mode: false

# MinerU 服务配置
mineru:
  default_backend: "pipeline"  # pipeline 或 vlm-http-client
  fastapi:
    url: "http://localhost:8000"  # 👈 修改为 MinerU 服务地址
    timeout: 60000
  vlm:
    http_client:
      server_url: "http://localhost:30000"  # VLM 服务地址（可选）

# DOTS 服务配置
dots:
  vllm:
    url: "http://localhost:8000"  # 👈 修改为 DOTS 服务地址
    model_name: "dotsocr-model"
    timeout: 60000
```

**配置步骤**:

1. 从模板创建配置文件:
   ```bash
   cp knowflow-server/settings.yaml.example knowflow-server/settings.yaml
   ```

2. 根据部署场景修改服务地址:
   - **同服务器部署**: `http://localhost:8000`
   - **远程部署**: `http://192.168.1.101:8000`
   - **Docker 网络**: `http://knowflow-mineru-api:8000`

3. 详细配置说明请参考: [knowflow-server/README.md](knowflow-server/README.md)

---

## 🖥️ 部署场景

### 场景 1: 单服务器部署 (All-in-One)

所有服务部署在同一台服务器上。

**适用场景**: 开发环境、小规模生产环境

**部署步骤**:

```bash
# 1. 启动主服务
./scripts/quick-start.sh

# 2. 启动 MinerU（注意端口冲突）
cd mineru/
cp .env.example .env
# 修改端口避免冲突: MINERU_API_PORT=8888
docker compose up -d

# 3. 启动 DOTS（注意端口冲突）
cd ../dots/
cp .env.example .env
# 下载模型
pip install modelscope
modelscope download --model rednote-hilab/dots.ocr --local_dir ./weights/DotsOCR
# 修改端口: DOTS_PORT=8001
docker compose up -d

# 4. 配置 KnowFlow Server
# 编辑 knowflow-server/settings.yaml:
# mineru.fastapi.url: "http://localhost:8888"
# dots.vllm.url: "http://localhost:8001"

# 5. 重启主服务
cd ..
docker compose restart knowflow-server
```

### 场景 2: 分布式部署（推荐）

将 GPU 密集型服务部署在独立服务器上。

**适用场景**: 生产环境、GPU 资源独立管理

**服务器分配示例**:
- **服务器 A** (192.168.1.100): KnowFlow 主服务
- **服务器 B** (192.168.1.101): MinerU 服务
- **服务器 C** (192.168.1.102): DOTS 服务

**部署步骤**:

```bash
# 服务器 A - 主服务
cd /path/to/knowflow/docker
cp .env.example .env
cp knowflow-server/settings.yaml.example knowflow-server/settings.yaml

# 编辑 knowflow-server/settings.yaml:
# mineru.fastapi.url: "http://192.168.1.101:8000"
# dots.vllm.url: "http://192.168.1.102:8000"

./scripts/quick-start.sh

# 服务器 B - MinerU
cd /path/to/knowflow/docker/mineru
cp .env.example .env
docker compose up -d

# 服务器 C - DOTS
cd /path/to/knowflow/docker/dots
cp .env.example .env
# 下载模型
modelscope download --model rednote-hilab/dots.ocr --local_dir ./weights/DotsOCR
docker compose up -d
```

### 场景 3: Docker 网络部署

所有服务在同一 Docker Compose 网络中通信。

**适用场景**: 容器化环境、Kubernetes

**配置示例**:

```yaml
# knowflow-server/settings.yaml
mineru:
  fastapi:
    url: "http://knowflow-mineru-api:8000"
dots:
  vllm:
    url: "http://knowflow-dots-ocr:8000"
```

---

## 🛠️ 故障排查

### 1. KnowFlow Server 无法连接 MinerU/DOTS

**症状**: 日志显示连接超时或拒绝连接

**检查清单**:

```bash
# 1. 检查 MinerU/DOTS 服务是否运行
cd mineru && docker compose ps
cd ../dots && docker compose ps

# 2. 测试网络连通性
curl http://localhost:8000/health  # MinerU
curl http://localhost:8000/v1/models  # DOTS

# 3. 检查 settings.yaml 配置
cat knowflow-server/settings.yaml | grep -A 5 "mineru:"
cat knowflow-server/settings.yaml | grep -A 5 "dots:"

# 4. 查看 KnowFlow Server 日志
docker compose logs knowflow-server | tail -50

# 5. 检查防火墙规则
sudo ufw status
sudo ufw allow 8000/tcp
```

### 2. 端口冲突

**症状**: `port already in use`

**解决方案**:

```bash
# 修改冲突的端口
# MinerU: 编辑 mineru/.env
MINERU_API_PORT=8888

# DOTS: 编辑 dots/.env
DOTS_PORT=8001

# 重启服务
docker compose down && docker compose up -d
```

### 3. GPU 不可用

**症状**: `No GPU available` 或 `CUDA out of memory`

**解决方案**:

```bash
# 检查 GPU 状态
nvidia-smi

# 检查 nvidia-docker
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# 降低 GPU 内存利用率（编辑 .env）
MINERU_GPU_MEMORY_UTILIZATION=0.6
DOTS_GPU_MEMORY_UTILIZATION=0.6
```

### 4. DOTS 模型加载失败

**症状**: `FileNotFoundError: weights/DotsOCR not found`

**解决方案**:

```bash
cd dots/

# 下载模型
pip install modelscope
modelscope download --model rednote-hilab/dots.ocr --local_dir ./weights/DotsOCR

# 检查模型文件
ls -la weights/DotsOCR/

# 重启服务
docker compose restart
```

### 5. 数据库连接失败

**症状**: `Can't connect to MySQL server`

**解决方案**:

```bash
# 检查 MySQL 服务
docker compose ps mysql

# 查看 MySQL 日志
docker compose logs mysql | tail -50

# 检查 .env 中的密码配置
cat .env | grep MYSQL_PASSWORD

# 重启 MySQL
docker compose restart mysql
```

---

## 🐳 Docker Compose

- **docker-compose.yml**  
  Sets up environment for RAGFlow and its dependencies.
- **docker-compose-base.yml**  
  Sets up environment for RAGFlow's dependencies: Elasticsearch/[Infinity](https://github.com/infiniflow/infinity), MySQL, MinIO, and Redis.

> [!CAUTION]
> We do not actively maintain **docker-compose-CN-oc9.yml**, **docker-compose-gpu-CN-oc9.yml**, or **docker-compose-gpu.yml**, so use them at your own risk. However, you are welcome to file a pull request to improve any of them.

## 🐬 Docker environment variables

The [.env](./.env) file contains important environment variables for Docker.

### Elasticsearch

- `STACK_VERSION`  
  The version of Elasticsearch. Defaults to `8.11.3`
- `ES_PORT`  
  The port used to expose the Elasticsearch service to the host machine, allowing **external** access to the service running inside the Docker container.  Defaults to `1200`.
- `ELASTIC_PASSWORD`  
  The password for Elasticsearch.

### Kibana

- `KIBANA_PORT`  
  The port used to expose the Kibana service to the host machine, allowing **external** access to the service running inside the Docker container. Defaults to `6601`.
- `KIBANA_USER`  
  The username for Kibana. Defaults to `rag_flow`.
- `KIBANA_PASSWORD`  
  The password for Kibana. Defaults to `infini_rag_flow`.

### Resource management

- `MEM_LIMIT`  
  The maximum amount of the memory, in bytes, that *a specific* Docker container can use while running. Defaults to `8073741824`.

### MySQL

- `MYSQL_PASSWORD`  
  The password for MySQL.
- `MYSQL_PORT`  
  The port used to expose the MySQL service to the host machine, allowing **external** access to the MySQL database running inside the Docker container. Defaults to `5455`.

### MinIO

- `MINIO_CONSOLE_PORT`  
  The port used to expose the MinIO console interface to the host machine, allowing **external** access to the web-based console running inside the Docker container. Defaults to `9001`
- `MINIO_PORT`  
  The port used to expose the MinIO API service to the host machine, allowing **external** access to the MinIO object storage service running inside the Docker container. Defaults to `9000`.
- `MINIO_USER`  
  The username for MinIO.
- `MINIO_PASSWORD`  
  The password for MinIO.

### Redis

- `REDIS_PORT`  
  The port used to expose the Redis service to the host machine, allowing **external** access to the Redis service running inside the Docker container. Defaults to `6379`.
- `REDIS_PASSWORD`  
  The password for Redis.

### RAGFlow

- `SVR_HTTP_PORT`  
  The port used to expose RAGFlow's HTTP API service to the host machine, allowing **external** access to the service running inside the Docker container. Defaults to `9380`.
- `RAGFLOW-IMAGE`  
  The Docker image edition. Available editions:  
  
  - `infiniflow/ragflow:v0.20.5-slim` (default): The RAGFlow Docker image without embedding models.  
  - `infiniflow/ragflow:v0.20.5`: The RAGFlow Docker image with embedding models including:
    - Built-in embedding models:
      - `BAAI/bge-large-zh-v1.5` 
      - `maidalun1020/bce-embedding-base_v1`

  
> [!TIP]  
> If you cannot download the RAGFlow Docker image, try the following mirrors.  
> 
> - For the `nightly-slim` edition:  
>   - `RAGFLOW_IMAGE=swr.cn-north-4.myhuaweicloud.com/infiniflow/ragflow:nightly-slim` or,
>   - `RAGFLOW_IMAGE=registry.cn-hangzhou.aliyuncs.com/infiniflow/ragflow:nightly-slim`.
> - For the `nightly` edition:  
>   - `RAGFLOW_IMAGE=swr.cn-north-4.myhuaweicloud.com/infiniflow/ragflow:nightly` or,
>   - `RAGFLOW_IMAGE=registry.cn-hangzhou.aliyuncs.com/infiniflow/ragflow:nightly`.

### Timezone

- `TIMEZONE`  
  The local time zone. Defaults to `'Asia/Shanghai'`.

### Hugging Face mirror site

- `HF_ENDPOINT`  
  The mirror site for huggingface.co. It is disabled by default. You can uncomment this line if you have limited access to the primary Hugging Face domain.

### MacOS

- `MACOS`  
  Optimizations for macOS. It is disabled by default. You can uncomment this line if your OS is macOS.

### Maximum file size

- `MAX_CONTENT_LENGTH`  
  The maximum file size for each uploaded file, in bytes. You can uncomment this line if you wish to change the 128M file size limit. After making the change, ensure you update `client_max_body_size` in nginx/nginx.conf correspondingly.

### Doc bulk size

- `DOC_BULK_SIZE`  
  The number of document chunks processed in a single batch during document parsing. Defaults to `4`.

### Embedding batch size

- `EMBEDDING_BATCH_SIZE`  
  The number of text chunks processed in a single batch during embedding vectorization. Defaults to `16`.

## 🐋 Service configuration

[service_conf.yaml](./service_conf.yaml) specifies the system-level configuration for RAGFlow and is used by its API server and task executor. In a dockerized setup, this file is automatically created based on the [service_conf.yaml.template](./service_conf.yaml.template) file (replacing all environment variables by their values).

- `ragflow`
  - `host`: The API server's IP address inside the Docker container. Defaults to `0.0.0.0`.
  - `port`: The API server's serving port inside the Docker container. Defaults to `9380`.

- `mysql`
  - `name`: The MySQL database name. Defaults to `rag_flow`.
  - `user`: The username for MySQL.
  - `password`: The password for MySQL.
  - `port`: The MySQL serving port inside the Docker container. Defaults to `3306`.
  - `max_connections`: The maximum number of concurrent connections to the MySQL database. Defaults to `100`.
  - `stale_timeout`: Timeout in seconds.

- `minio`
  - `user`: The username for MinIO.
  - `password`: The password for MinIO.
  - `host`: The MinIO serving IP *and* port inside the Docker container. Defaults to `minio:9000`.

- `oss`
  - `access_key`: The access key ID used to authenticate requests to the OSS service.
  - `secret_key`: The secret access key used to authenticate requests to the OSS service.
  - `endpoint_url`: The URL of the OSS service endpoint.
  - `region`: The OSS region where the bucket is located.
  - `bucket`: The name of the OSS bucket where files will be stored. When you want to store all files in a specified bucket, you need this configuration item.
  - `prefix_path`: Optional. A prefix path to prepend to file names in the OSS bucket, which can help organize files within the bucket.

- `s3`:
  - `access_key`: The access key ID used to authenticate requests to the S3 service.
  - `secret_key`: The secret access key used to authenticate requests to the S3 service.
  - `endpoint_url`: The URL of the S3-compatible service endpoint. This is necessary when using an S3-compatible protocol instead of the default AWS S3 endpoint.
  - `bucket`: The name of the S3 bucket where files will be stored. When you want to store all files in a specified bucket, you need this configuration item.
  - `region`: The AWS region where the S3 bucket is located. This is important for directing requests to the correct data center.
  - `signature_version`: Optional. The version of the signature to use for authenticating requests. Common versions include `v4`.
  - `addressing_style`: Optional. The style of addressing to use for the S3 endpoint. This can be `path` or `virtual`.
  - `prefix_path`: Optional. A prefix path to prepend to file names in the S3 bucket, which can help organize files within the bucket.

- `oauth`
  The OAuth configuration for signing up or signing in to RAGFlow using a third-party account.
  - `<channel>`: Custom channel ID.
    - `type`: Authentication type, options include `oauth2`, `oidc`, `github`. Default is `oauth2`, when `issuer` parameter is provided, defaults to `oidc`.
    - `icon`: Icon ID, options include `github`, `sso`, default is `sso`.
    - `display_name`: Channel name, defaults to the Title Case format of the channel ID.
    - `client_id`: Required, unique identifier assigned to the client application.
    - `client_secret`: Required, secret key for the client application, used for communication with the authentication server.
    - `authorization_url`: Base URL for obtaining user authorization.
    - `token_url`: URL for exchanging authorization code and obtaining access token.
    - `userinfo_url`: URL for obtaining user information (username, email, etc.).
    - `issuer`: Base URL of the identity provider. OIDC clients can dynamically obtain the identity provider's metadata (`authorization_url`, `token_url`, `userinfo_url`) through `issuer`.
    - `scope`: Requested permission scope, a space-separated string. For example, `openid profile email`.
    - `redirect_uri`: Required, URI to which the authorization server redirects during the authentication flow to return results. Must match the callback URI registered with the authentication server. Format: `https://your-app.com/v1/user/oauth/callback/<channel>`. For local configuration, you can directly use `http://127.0.0.1:80/v1/user/oauth/callback/<channel>`.

- `user_default_llm`  
  The default LLM to use for a new RAGFlow user. It is disabled by default. To enable this feature, uncomment the corresponding lines in **service_conf.yaml.template**.  
  - `factory`: The LLM supplier. Available options:
    - `"OpenAI"`
    - `"DeepSeek"`
    - `"Moonshot"`
    - `"Tongyi-Qianwen"`
    - `"VolcEngine"`
    - `"ZHIPU-AI"`
  - `api_key`: The API key for the specified LLM. You will need to apply for your model API key online.

> [!TIP]  
> If you do not set the default LLM here, configure the default LLM on the **Settings** page in the RAGFlow UI.


## 📋 Setup Examples

### 🔒 HTTPS Setup

#### Prerequisites

- A registered domain name pointing to your server
- Port 80 and 443 open on your server
- Docker and Docker Compose installed

#### Getting and configuring certificates (Let's Encrypt)

If you want your instance to be available under `https`, follow these steps:

1. **Install Certbot and obtain certificates**
   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install certbot
   
   # CentOS/RHEL
   sudo yum install certbot
   
   # Obtain certificates (replace with your actual domain)
   sudo certbot certonly --standalone -d your-ragflow-domain.com
   ```

2. **Locate your certificates**  
   Once generated, your certificates will be located at:
   - Certificate: `/etc/letsencrypt/live/your-ragflow-domain.com/fullchain.pem`
   - Private key: `/etc/letsencrypt/live/your-ragflow-domain.com/privkey.pem`

3. **Update docker-compose.yml**  
   Add the certificate volumes to the `ragflow` service in your `docker-compose.yml`:
   ```yaml
   services:
     ragflow:
       # ...existing configuration...
       volumes:
         # SSL certificates
         - /etc/letsencrypt/live/your-ragflow-domain.com/fullchain.pem:/etc/nginx/ssl/fullchain.pem:ro
         - /etc/letsencrypt/live/your-ragflow-domain.com/privkey.pem:/etc/nginx/ssl/privkey.pem:ro
         # Switch to HTTPS nginx configuration
         - ./nginx/ragflow.https.conf:/etc/nginx/conf.d/ragflow.conf
         # ...other existing volumes...
  
   ```

4. **Update nginx configuration**  
   Edit `nginx/ragflow.https.conf` and replace `my_ragflow_domain.com` with your actual domain name.

5. **Restart the services**
   ```bash
   docker-compose down
   docker-compose up -d
   ```


> [!IMPORTANT]
> - Ensure your domain's DNS A record points to your server's IP address
> - Stop any services running on ports 80/443 before obtaining certificates with `--standalone`

> [!TIP]
> For development or testing, you can use self-signed certificates, but browsers will show security warnings.

#### Alternative: Using existing certificates

If you already have SSL certificates from another provider:

1. Place your certificates in a directory accessible to Docker
2. Update the volume paths in `docker-compose.yml` to point to your certificate files
3. Ensure the certificate file contains the full certificate chain
4. Follow steps 4-5 from the Let's Encrypt guide above