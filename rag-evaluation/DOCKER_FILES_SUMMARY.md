# Docker 部署文件说明

## 📦 已创建的文件列表

### 1. Dockerfile
**位置**: `/rag-evaluation/Dockerfile`

**用途**: Docker 镜像构建文件

**特性**:
- 多阶段构建（frontend builder + runtime）
- Python 源码编译为字节码（.pyc），删除 .py 文件保护源码
- 使用 Nginx + Supervisor 架构
- 内置健康检查
- 前端静态资源优化

**构建产物**:
- 镜像名称: `rag-evaluation:latest`
- 大小: 约 500-600 MB
- 包含: Nginx, Python 3.10, 编译后的后端, 构建后的前端

---

### 2. docker-compose.yml
**位置**: `/rag-evaluation/docker-compose.yml`

**用途**: Docker Compose 服务编排

**配置要点**:
- 端口映射: 5003:80
- 数据持久化: data, logs, tmp 目录挂载
- 连接 RAGFlow 网络: `ragflow_ragflow`
- 自动重启策略: `unless-stopped`
- 健康检查集成

**需要修改的地方**:
```yaml
# 如果 RAGFlow 使用不同网络
networks:
  rag-network:
    external: true
    name: your_network_name  # 修改这里
```

---

### 3. .env.docker
**位置**: `/rag-evaluation/.env.docker`

**用途**: Docker 容器环境变量配置

**必须配置项**:
```bash
RAGFLOW_BASE_URL=http://ragflow:9380        # RAGFlow 地址
RAGFLOW_API_KEY=ragflow-xxx                 # RAGFlow API 密钥
SILICONFLOW_API_KEY=sk-xxx                  # LLM API 密钥（至少一个）
```

**可选配置项**:
- OpenAI、DeepSeek、智谱 AI 的配置
- 评测参数（超时、并发数等）
- 日志级别和存储路径

**⚠️ 安全提示**: 
- 生产环境务必修改 `SECRET_KEY`
- 不要将此文件提交到版本控制系统

---

### 4. .dockerignore
**位置**: `/rag-evaluation/.dockerignore`

**用途**: 排除不需要打包进镜像的文件

**排除内容**:
- Git 相关文件
- 文档文件（*.md）
- 开发环境配置
- Node modules
- 前端源码（仅打包构建产物）
- 测试文件
- 数据库文件
- 日志和临时文件

**效果**: 减小镜像大小，加快构建速度

---

### 5. build-docker.sh
**位置**: `/rag-evaluation/build-docker.sh`

**用途**: 镜像构建脚本

**使用方法**:
```bash
# 构建 latest 版本
./build-docker.sh

# 构建指定版本
./build-docker.sh v1.0.0
```

**功能**:
- 自动检查前置条件
- 构建 Docker 镜像
- 自动打标签
- 显示镜像信息和使用提示

---

### 6. DEPLOY.md
**位置**: `/rag-evaluation/DEPLOY.md`

**用途**: 详细的部署文档

**内容**:
- 镜像特性说明
- 完整部署步骤
- 环境变量详细说明
- 数据持久化配置
- 网络配置指南
- 性能优化建议
- 安全配置建议
- 故障排查指南
- 版本升级流程

**适用对象**: 技术人员、运维工程师

---

### 7. DOCKER_README.md
**位置**: `/rag-evaluation/DOCKER_README.md`

**用途**: Docker 部署综合说明

**内容**:
- 快速部署指南
- 技术架构图
- 配置说明
- 运维管理命令
- 性能优化
- 安全建议
- 镜像分发方法
- 常用命令速查

**适用对象**: 所有用户

---

### 8. QUICKSTART.md
**位置**: `/rag-evaluation/QUICKSTART.md`

**用途**: 5分钟快速开始指南

**内容**:
- 最简化的部署步骤
- 常见问题快速解答
- 基本验证方法
- 下一步指引

**适用对象**: 新用户、客户

---

## 🎯 使用流程

### 开发者构建镜像

```bash
# 1. 构建镜像
./build-docker.sh v1.0.0

# 2. 导出镜像
docker save rag-evaluation:latest | gzip > rag-evaluation-latest.tar.gz

# 3. 将镜像文件和相关文档交付给客户
tar czf rag-evaluation-deploy.tar.gz \
    rag-evaluation-latest.tar.gz \
    docker-compose.yml \
    .env.docker \
    QUICKSTART.md \
    DEPLOY.md
```

### 客户部署

```bash
# 1. 解压部署包
tar xzf rag-evaluation-deploy.tar.gz
cd rag-evaluation-deploy

# 2. 加载镜像
docker load -i rag-evaluation-latest.tar.gz

# 3. 配置环境变量
vi .env.docker  # 填入 API 密钥等配置

# 4. 启动服务
docker-compose up -d

# 5. 访问系统
# 浏览器打开 http://localhost:5003
```

---

## 🔒 源码保护机制

### 镜像中的文件结构

```
/app/
├── *.pyc                    # Python 字节码（已编译）
├── services/
│   └── *.pyc               # 服务模块字节码
├── models/
│   └── *.pyc               # 模型字节码
├── static/                 # 前端构建产物
│   ├── index.html
│   ├── assets/
│   └── ...
├── tmp/                    # 临时目录
├── logs/                   # 日志目录
└── data/                   # 数据目录
```

### 源码保护方式

1. **Python 后端**:
   - 使用 `python3 -m compileall -b` 编译所有 .py 文件为 .pyc
   - 删除所有 .py 源文件（保留 __init__.py）
   - 仅保留字节码文件

2. **前端**:
   - 使用 `npm run build` 构建生产版本
   - 代码经过压缩和混淆
   - 仅包含构建产物，不包含源码

3. **配置文件**:
   - 通过环境变量传入
   - 不在镜像中硬编码

### 验证源码保护

```bash
# 进入容器
docker exec -it rag-evaluation bash

# 检查是否有 .py 文件（除了 __init__.py）
find /app -name "*.py" -type f | grep -v __init__

# 应该只看到 __init__.py，没有其他 .py 文件
```

---

## 📊 镜像层次结构

```
rag-evaluation:latest
├── Layer 1: Python 3.10 基础镜像
├── Layer 2: 系统依赖（Nginx, Supervisor）
├── Layer 3: Python 依赖包
├── Layer 4: 编译后的后端代码（.pyc）
├── Layer 5: 前端构建产物
└── Layer 6: 配置文件（Nginx, Supervisor）
```

---

## 🌐 网络架构

```
┌─────────────────┐
│   Browser       │
└────────┬────────┘
         │ HTTP
         ↓
┌─────────────────────────┐
│   Host:5003             │
└────────┬────────────────┘
         │
         ↓
┌─────────────────────────┐
│   Docker Container      │
│   ┌─────────────────┐  │
│   │  Nginx:80       │  │
│   └────┬────────────┘  │
│        │                │
│        ↓                │
│   ┌─────────────────┐  │
│   │  Flask:5002     │  │
│   └─────────────────┘  │
└─────────┬───────────────┘
          │
          ↓
   ┌──────────────────┐
   │  RAGFlow:9380    │
   │  (ragflow_ragflow│
   │   network)       │
   └──────────────────┘
```

---

## 📝 配置文件优先级

环境变量加载顺序（后加载的覆盖先加载的）：

1. 系统环境变量
2. `.env.docker` 文件（docker-compose 加载）
3. `docker-compose.yml` 中的 `environment` 配置
4. 容器内默认值

---

## 🔄 更新和维护

### 版本命名规范

```bash
# 主版本.次版本.修订版本
v1.0.0  # 首次发布
v1.0.1  # 修复 bug
v1.1.0  # 新功能
v2.0.0  # 重大更新
```

### 构建新版本

```bash
# 构建新版本
./build-docker.sh v1.1.0

# 测试新版本
docker-compose up -d

# 验证功能
curl http://localhost:5003/health

# 导出新版本
docker save rag-evaluation:v1.1.0 | gzip > rag-evaluation-v1.1.0.tar.gz
```

---

## 📋 交付清单

交付给客户的文件：

```
rag-evaluation-delivery/
├── rag-evaluation-latest.tar.gz   # Docker 镜像文件
├── docker-compose.yml             # Docker Compose 配置
├── .env.docker                    # 环境变量模板
├── QUICKSTART.md                  # 快速开始指南
├── DEPLOY.md                      # 详细部署文档
├── DOCKER_README.md               # Docker 使用说明
└── README.txt                     # 简要说明
```

README.txt 内容：

```
RAG 评估系统 - Docker 部署包
==========================

包含文件：
1. rag-evaluation-latest.tar.gz - Docker 镜像
2. docker-compose.yml - 服务配置
3. .env.docker - 环境变量配置模板
4. QUICKSTART.md - 5分钟快速开始
5. DEPLOY.md - 详细部署文档
6. DOCKER_README.md - Docker 使用说明

快速开始：
1. 阅读 QUICKSTART.md
2. 加载镜像: docker load -i rag-evaluation-latest.tar.gz
3. 配置 .env.docker 文件
4. 启动服务: docker-compose up -d
5. 访问 http://localhost:5003

技术支持：
- 详细文档：DEPLOY.md
- 常见问题：QUICKSTART.md 的"常见问题"部分

系统要求：
- Docker 20.10+
- Docker Compose 2.0+
- 2GB+ 可用内存
- RAGFlow 服务运行中
```

---

## ✅ 验证清单

部署前检查：

- [ ] 所有配置文件已创建
- [ ] .env.docker 中的敏感信息已填写
- [ ] Docker 镜像已成功构建
- [ ] 测试镜像可以正常启动
- [ ] 健康检查通过
- [ ] 前端页面可访问
- [ ] API 接口可调用
- [ ] RAGFlow 连接正常
- [ ] 数据持久化目录已创建
- [ ] 文档齐全且准确

---

**📧 如有疑问，请查阅相关文档或联系技术支持。**
