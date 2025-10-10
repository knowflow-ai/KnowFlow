<div align="center">
  <img src="knowflow/assets/logo.png" alt="KnowFlow 企业知识库" width="30%">
</div>

# KnowFlow - 企业级智能知识库解决方案

[![Star History Chart](https://api.star-history.com/svg?repos=weizxfree/KnowFlow&type=Date)](https://star-history.com/#weizxfree/KnowFlow&Date)

🌐 **官方网站**: [https://www.knowflowchat.cn/](https://www.knowflowchat.cn/)

📺 **B站视频**: [https://www.bilibili.com/video/BV1Vfg8zDEUf/](https://www.bilibili.com/video/BV1Vfg8zDEUf/)

---

## 🚀 什么是 KnowFlow

**KnowFlow** 是一个基于 RAGFlow 的企业级开源知识库解决方案，专注于为企业提供真正落地的最后一公里服务。我们持续兼容 RAGFlow 官方版本（当前适配 RAGFlow v0.20.1），同时将社区最佳实践整合进来，为企业知识管理提供更加完善的解决方案。

### 🎯 产品定位

- **RAGFlow 企业落地的最后一公里**：解决从开源到生产的关键差距
- **插件化增强平台**：通过独立服务方式扩展 RAGFlow 功能
- **企业级知识管理系统**：提供完整的用户权限、团队协作、数据安全保障

### 🏗️ 系统架构

KnowFlow 采用分布式微服务架构，通过独立的服务组件为 RAGFlow 提供增强功能：

```mermaid
graph TB
    subgraph "用户端"
        User[👤 用户]
        Browser[🌐 浏览器]
        User --> Browser
    end

    subgraph "RAGFlow 生态系统"
        direction TB
        subgraph "RAGFlow 核心服务"
            RF_Frontend[RAGFlow 前端<br/>端口: 80/443]
            RF_Backend[RAGFlow 后端<br/>端口: 9380]
            RF_DB[(RAGFlow 数据库<br/>MySQL)]
            RF_ES[(Elasticsearch<br/>端口: 9200)]
            RF_Minio[(MinIO 存储<br/>端口: 9000)]
            RF_Redis[(Redis 缓存<br/>端口: 6379)]
        end
        
        subgraph "KnowFlow 扩展服务"
            direction TB
            KF_Backend[KnowFlow 后端<br/>端口: 5000<br/>• 用户管理<br/>• 团队协作<br/>• MinerU集成<br/>• API Token管理]
            KF_Gotenberg[Gotenberg 文档转换<br/>端口: 3000<br/>• PPT/Word/Excel转PDF<br/>• 文档格式标准化]
            
            subgraph "MinerU 解析引擎"
                MinerU_API[MinerU API 服务<br/>端口: 8888<br/>• OCR 文字识别<br/>• 图像提取<br/>• 文档结构分析]
                MinerU_VLM[VLM 视觉模型<br/>端口: 30000<br/>• 图像理解<br/>• 多模态分析]
            end
        end
    end

    %% 用户访问流程
    Browser --> RF_Frontend
    
    %% RAGFlow 内部服务通信
    RF_Frontend --> RF_Backend
    RF_Backend --> RF_DB
    RF_Backend --> RF_ES
    RF_Backend --> RF_Minio
    RF_Backend --> RF_Redis
    
    %% RAGFlow 与 KnowFlow 集成
    RF_Frontend -.->|API 调用| KF_Backend
    RF_Backend -.->|共享数据库| RF_DB
    
    %% KnowFlow 内部服务通信
    KF_Backend --> KF_Gotenberg
    KF_Backend --> MinerU_API
    MinerU_API --> MinerU_VLM
    
    %% KnowFlow 与 RAGFlow 数据层集成
    KF_Backend --> RF_DB
    KF_Backend --> RF_ES
    KF_Backend --> RF_Minio
    KF_Backend --> RF_Redis
```

**架构特点：**
- **🔌 独立服务**：KnowFlow 作为独立微服务运行，不修改 RAGFlow 核心代码
- **🔗 API 集成**：通过 RESTful API 与 RAGFlow 前端无缝集成
- **💾 共享数据层**：复用 RAGFlow 的数据库、存储等基础设施
- **⚡ 高性能解析**：集成 MinerU 2.x 引擎，支持 GPU 加速
- **📄 格式转换**：内置 Gotenberg 服务，支持多种文档格式转换

### 💡 核心功能

<div align="center">

| 📚 **智能文档解析** | 🧠 **增强检索问答** | 👥 **企业级管理** | 🔌 **开放集成** |
|-------------------|-------------------|------------------|----------------|
| • MinerU2.x OCR引擎<br>• 图文混排输出<br>• 多种分块策略<br>• 20+文档格式支持 | • 精准语义检索<br>• 上下文感知问答<br>• 多模态内容理解<br>• 实时知识更新 | • RBAC权限管理<br>• 团队协作空间<br>• 纯离线部署<br>• 企业微信集成<br>• LDAP/SSO支持 | • 插件化架构<br>• API开放接口<br>• 自定义扩展<br>• 第三方系统集成 |

</div>


### 🌟 核心优势

<div align="center">

| 🌟 | **KnowFlow 优势** |
|----|-------------------|
| 🔌 | **插件化架构**：无缝兼容 RAGFlow 任意版本，所有增强均可热插拔，升级无忧 |
| 🏗️ | **微服务设计**：通过独立服务方式增强 RAGFlow，不修改核心代码 |
| 🧩 | **分块策略丰富**：支持多种分块算法，检索更精准，适配多场景文档 |
| 🏢 | **企业级特性**：MinerU2.x OCR 引擎、RBAC权限管理、纯离线部署、企业微信、LDAP/SSO |
| 📈 | **最佳实践集成**：持续吸收社区优质方案，助力企业高效落地 |
| 🔧 | **简化部署**：一键安装脚本，Docker Compose 开箱即用 |

</div>


---

## 🚀 快速开始

### 方式一：Docker Compose 部署（推荐）

#### 前置要求
- Docker 20.10+
- Docker Compose 2.0+
- 至少 8GB 内存
- 可选：NVIDIA GPU + nvidia-container-toolkit（GPU加速）

#### 1. 克隆项目代码

```bash
git clone https://github.com/weizxfree/KnowFlow.git
cd KnowFlow/docker
```

#### 2. 配置 KnowFlow Server

配置文件位于：`docker/knowflow-server/settings.yaml`

```bash
# 从模板创建配置文件
cp knowflow-server/settings.yaml.example knowflow-server/settings.yaml

# 编辑配置文件，配置 MinerU/DOTS 服务地址
vim knowflow-server/settings.yaml
```

**配置示例**：

```yaml
# MinerU 服务配置
mineru:
  default_backend: "pipeline"
  fastapi:
    url: "http://localhost:8000"  # 👈 修改为 MinerU 服务地址
    timeout: 60000

# DOTS 服务配置（可选）
dots:
  vllm:
    url: "http://localhost:8000"  # 👈 修改为 DOTS 服务地址
    model_name: "dotsocr-model"
    timeout: 60000
```

**部署场景配置**：
- **同服务器部署**: `http://localhost:8000`
- **远程服务器部署**: `http://192.168.1.101:8000`
- **Docker 网络部署**: `http://knowflow-mineru-api:8000`

详细配置说明：[docker/knowflow-server/README.md](docker/knowflow-server/README.md)

#### 3. 部署 OCR 解析服务（可选）

KnowFlow 支持 MinerU 和 DOTS 两种 OCR 服务，可根据需求选择部署。

##### 选项 A：部署 MinerU 服务

```bash
# 进入 MinerU 目录
cd mineru/

# 从模板创建配置
cp .env.example .env

# 启动 MinerU API 服务
docker compose up -d

# 查看服务状态
docker compose ps
docker compose logs -f
```

**服务端口**：
- MinerU API: 8000
- MinerU VLM (可选): 30000

详细说明：[docker/mineru/README.md](docker/mineru/README.md)

##### 选项 B：部署 DOTS 服务

```bash
# 进入 DOTS 目录
cd dots/

# 下载 DOTS 模型
pip install modelscope
modelscope download --model rednote-hilab/dots.ocr --local_dir ./weights/DotsOCR

# 从模板创建配置
cp .env.example .env

# 启动 DOTS 服务
docker compose up -d

# 查看服务状态
docker compose ps
docker compose logs -f
```

**服务端口**：
- DOTS OCR: 8000

详细说明：[docker/dots/README.md](docker/dots/README.md)

> 💡 **提示**：MinerU 和 DOTS 可以同时部署，但需要修改端口避免冲突。建议 MinerU 使用 8000，DOTS 使用 8001。

#### 4. 启动 KnowFlow 主服务

返回 docker 目录，启动主服务：

```bash
# 返回 docker 目录
cd ..

# 配置环境变量（如果未配置）
cp .env.example .env

# 选择部署模式
# 有 GPU：
docker compose -f docker-compose-gpu.yml up -d

# 无 GPU：
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f
```

#### 5. 访问系统

- 🌐 **前端地址**: `http://服务器IP` 或 `http://localhost`
- 🔌 **API 地址**: `http://服务器IP:9380`

#### 6. 默认管理员账户

```
邮箱：admin@gmail.com
密码：admin
```

> 💡 **安全提示**：首次登录后请立即修改默认密码！


### 方式二：源码部署


#### 前置要求
- Python 3.9+
- Node.js 16+ 
- pnpm
- MinerU 服务（参考上述步骤）

#### KnowFlow 后端部署

1. **安装 Python 依赖**
```bash
cd knowflow/server
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **启动文件转换服务（可选）**
```bash
# 支持 PDF 以外文件格式需要启动此服务
docker run -d -p 3000:3000 gotenberg/gotenberg:8
```

3. **执行 install 脚本，初始化环境变量**

```bash
cd knowflow/
./scripts/install.sh --local
```

4. **启动 knowflow 后端服务**
```bash
python3 app.py
```

#### RAGFlow 后端部署

1. **修改 docker/entrypoint.sh 文件**
```bash
# 注释掉 nginx 行
# /usr/sbin/nginx
```

2. **激活 Python 虚拟环境**
```bash
source .venv/bin/activate
export PYTHONPATH=$(pwd)
```

3. **配置 HuggingFace 镜像（可选）**
```bash
# 如果无法访问 HuggingFace，设置镜像站点
export HF_ENDPOINT=https://hf-mirror.com
```

4. **检查配置文件**
确保 `conf/service_conf.yaml` 中所有主机和端口配置正确。

5. **启动后端服务**

方案一：

```bash
# 设置内存分配器和启动任务执行器
JEMALLOC_PATH=$(pkg-config --variable=libdir jemalloc)/libjemalloc.so
LD_PRELOAD=$JEMALLOC_PATH python rag/svr/task_executor.py 1

# 启动 API 服务器
python api/ragflow_server.py
```

方案二：

```bash
./local_entrypoint.sh
```


#### RAGFlow 前端部署

1. **安装 Node.js 依赖**
```bash
cd web
pnpm install
```

2. **启动开发服务器**
```bash
pnpm dev
```

浏览器访问启动后的地址，即可进入系统。

---

## 📋 功能详解

### 🎨 全新 UI 界面

基于 RAGFlow v0.20.1 二次开发，提供更加现代化的用户界面：

<div align="center">
  <img src="knowflow/assets/ui_1.png" alt="KnowFlow 主界面">
</div>

<div align="center">
  <img src="knowflow/assets/ui_2.png" alt="KnowFlow 知识库界面">
</div>

<div align="center">
  <img src="knowflow/assets/ui_3.png" alt="KnowFlow 知识库界面">
</div>

### 👥 用户后台管理系统

管理员可以进行统一的管理：

<div align="center">
  <img src="knowflow/assets/user-setting.png" alt="用户后台管理系统">
</div>


**核心特性：**
- **RBAC权限管理**：基于角色的访问控制，精细化权限分配
- **纯离线部署**：支持完全离线环境部署，满足高安全性要求
- 移除前端用户注册通道，管理员统一管理用户
- 用户管理、团队管理、模型配置管理
- 新用户自动加入创建时间最早用户的团队
- 继承团队模型配置，降低配置复杂度

### 📄 图文混排输出

**支持格式：** PPT、PNG、Word、DOC、Excel 等 20+ 种常见文件格式

**分块策略：**
1. **文档结构分块**：基于文档原生结构进行智能分块
2. **按标题分块**：根据标题层级自动划分内容块
3. **RAGFlow 原分块**：保持与官方完全一致的分块规则
4. **父子分块**：父块较大用于补充上下文，子块用于向量检索
5. **DOTS 解析**：先进的文档智能解析引擎，支持复杂版式和多模态内容

<div align="center">
  <img src="knowflow/assets/mulcontent.png" alt="图文混排示例">
</div>

### 💼 企业微信集成

支持企业微信应用，可将企业微信作为聊天机器人入口：

<div align="center">
  <img src="knowflow/assets/wecom.jpg" style="height: 400px;" alt="企业微信应用">
</div>

详细配置方式参照 `server/services/knowflow/README.md`

---

## 🔧 编译 Docker（开发者）


### 编译 KnowFlow-Server 镜像

```bash
# 后端镜像
docker buildx build --platform linux/amd64 --target backend -t zxwei/knowflow-server:v0.3.0 --push .

# 前端镜像
docker buildx build --platform linux/amd64 --target frontend -t zxwei/knowflow-web:v0.3.0 --push .
```

### 编译 KnowFlow 全镜像

```bash
# 安装 uv
sudo snap install astral-uv --classic

# 安装 libicu
sudo apt-get update
sudo apt-get install -y python3.12-dev build-essential pkg-config libicu-dev

uv run download_deps.py
docker build -f Dockerfile.deps -t infiniflow/ragflow_deps .
docker build --build-arg LIGHTEN=1 -f Dockerfile -t infiniflow/ragflow:nightly-slim .


docker tag infiniflow/ragflow:nightly-slim zxwei/knowflow:v2.0.2
docker push zxwei/knowflow:v2.0.2

vim docker/.env 
RAGFLOW_IMAGE=infiniflow/ragflow:nightly-slim

```

---

## 📋 TODO 清单

- [x] 支持更多文档格式的 MinerU 解析
- [x] 增强 MarkDown 文件的分块规则
- [x] 优化 Excel 文件分块
- [x] MinerU 2.0 接入
- [x] RAGFlow 前端 UI 源码开源
- [x] API Token 自动生成机制
- [x] MinerU 支持自动问题，自动关键词，Raptor，知识图谱 
- [ ] 文档审批工作流

---

## ❓ 常见问题

### 1. 如何启用 GPU 加速？

**安装 nvidia-container-toolkit**
```bash
# 添加源
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 安装组件
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 重启 Docker
sudo systemctl restart docker

```

---


## 📄 许可证

**KnowFlow** 采用 [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE) 开源许可证。

### ✅ 您可以自由地：
- **使用**：个人学习、研究、开发和部署
- **修改**：根据需要修改源代码  
- **分发**：分享给他人使用
- **贡献**：提交 PR 和 Issue，参与开源协作

### ⚠️ 重要限制条件：
- **源码开放**：如果您修改了 KnowFlow 并通过网络提供服务，必须向用户提供修改后的完整源代码
- **相同许可**：基于 KnowFlow 的衍生作品必须同样采用 AGPL-3.0 许可证
- **版权保留**：保留原始版权声明和许可证信息

### 🏢 商业使用说明
AGPL-3.0 允许商业使用，但有重要约束：
- 如果您将修改版本作为网络服务提供，必须开源所有修改
- 如果这不符合您的商业需求，请联系获取商业许可

### 📞 商业许可咨询
- 💬 微信：skycode007（备注"商业授权咨询"）

> **注意**：AGPL-3.0 是一个严格的 copyleft 许可证，特别适用于网络服务。使用前请仔细阅读 [完整许可证条款](LICENSE)。


---

## 🤝 社区与支持

### 💬 交流群

如有需求或问题建议，可加入交流群讨论。

加微信 `skycode007`，备注"加群"即可。

### 📢 更新信息

项目持续更新中，更新日志会在微信公众号 **[KnowFlow 企业知识库]** 发布，欢迎关注。

### 🙏 鸣谢

本项目基于以下开源项目开发：

- [ragflow](https://github.com/infiniflow/ragflow) - 核心 RAG 框架

---

<div align="center">
  <p>⭐ 如果这个项目对您有帮助，请不要忘记点个 Star！</p>
  <p>🚀 让我们一起构建更好的企业知识库解决方案！</p>
</div>