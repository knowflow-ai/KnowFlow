# KnowFlow 横向扩展方案 - 多实例负载均衡

> **方案类型**: 架构优化 - 横向扩展
> **优先级**: 备选方案
> **复杂度**: 低
> **风险等级**: 低
> **预计改动**: 2 个配置文件，约 20-30 行代码

---

## 📋 方案概述

基于对 RAGFlow PR #7845 (Gunicorn 生产部署) 的深入分析，我们发现 KnowFlow 当前架构已经非常接近生产级多实例部署。本方案通过**最小改动**实现 API 层的横向扩展，避免 Gunicorn 多进程模式的所有已知坑点。

---

## 🎯 核心思想

```
不使用 Gunicorn 多进程 ❌
改用 Nginx 负载均衡 + 多个 Flask 单进程实例 ✅
```

**优势**:
- ✅ 避免 Gunicorn 的数据库连接池耗尽问题
- ✅ 避免 Gevent monkey-patching 与第三方 SDK 冲突
- ✅ 避免跨 worker 的 SECRET_KEY 不一致问题
- ✅ 避免 worker 关闭死锁问题
- ✅ 保持架构简单清晰

---

## 📊 当前架构分析

### 已有组件 ✅

| 组件 | 状态 | 说明 |
|------|------|------|
| **Nginx** | ✅ 已实现 | 反向代理、静态文件服务 |
| **Redis 消息队列** | ✅ 已实现 | Redis Stream，支持持久化和消费者组 |
| **Task Executor** | ✅ 已实现 | 异步任务处理，使用 trio 框架 |
| **读写分离** | ⚠️ 部分实现 | 重 IO 操作（文档解析）已异步化 |

### 当前部署架构

```
┌──────────────────────────────────────────────┐
│         Nginx (80/443)                        │
│         - 静态文件服务                         │
│         - 反向代理到单个 Flask 实例            │
└─────────────────┬────────────────────────────┘
                  │
          ┌───────▼────────┐
          │  Flask (9380)  │  ← 单实例，多线程
          │  ragflow-server│
          └───────┬────────┘
                  │
    ┌─────────────┴──────────────┐
    │                            │
┌───▼────┐                  ┌───▼────────┐
│ MySQL  │                  │ Redis Queue│
│ ES/INF │                  │            │
│ MinIO  │                  └───┬────────┘
└────────┘                      │
                         ┌──────▼─────────┐
                         │ Task Executor  │
                         │ (N 个进程)     │
                         └────────────────┘
```

---

## 🚀 优化后架构

### 目标架构

```
┌──────────────────────────────────────────────┐
│         Nginx (80/443)                        │
│         - 负载均衡 (upstream)                 │
│         - 健康检查                            │
│         - 静态文件服务                         │
└─────────────────┬────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
    ┌───▼────┐         ┌───▼────┐         ┌────────┐
    │ Flask  │         │ Flask  │         │ Flask  │
    │ API-1  │  ...    │ API-2  │  ...    │ API-N  │
    │(9380)  │         │(9380)  │         │(9380)  │
    └───┬────┘         └───┬────┘         └───┬────┘
        │                   │                   │
        └─────────┬─────────┴───────────────────┘
                  │
    ┌─────────────┴──────────────┐
    │                            │
┌───▼────┐                  ┌───▼────────┐
│ MySQL  │                  │ Redis Queue│
│ ES/INF │                  │            │
│ MinIO  │                  └───┬────────┘
└────────┘                      │
                         ┌──────▼─────────┐
                         │ Task Executor  │
                         │ (N 个进程)     │
                         └────────────────┘
```

### 关键特性

- **多 Flask 实例**: 每个实例独立运行，单进程多线程
- **Nginx 负载均衡**: 轮询或最少连接算法
- **无状态 API**: 通过 Redis Session 实现会话共享
- **优雅降级**: 单个实例失败不影响整体服务

---

## 🔧 具体改动方案

### 改动 1: Docker Compose 配置

#### 文件: `docker/docker-compose.yml`

**当前配置** ❌:
```yaml
ragflow-server:
  image: infiniflow/ragflow:${RAGFLOW_VERSION}
  container_name: ragflow-server
  ports:
    - "${SVR_HTTP_PORT:-9380}:9380"
  # ...其他配置
```

**优化后配置** ✅:
```yaml
# 方案 A: 使用 deploy.replicas (推荐，Docker Compose v3.8+)
ragflow-api:
  image: infiniflow/ragflow:${RAGFLOW_VERSION}
  deploy:
    replicas: 3  # 启动 3 个副本
    # 可选：资源限制
    resources:
      limits:
        cpus: '2'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 2G
  environment:
    - START_API_SERVER=1
    - START_TASK_EXECUTOR=0  # API 实例不运行 task executor
  # 不暴露端口到宿主机，只通过 Nginx 访问
  networks:
    - ragflow

# 方案 B: 手动定义多个服务（适用于不同配置）
ragflow-api-1:
  image: infiniflow/ragflow:${RAGFLOW_VERSION}
  container_name: ragflow-api-1
  # ...配置同上

ragflow-api-2:
  image: infiniflow/ragflow:${RAGFLOW_VERSION}
  container_name: ragflow-api-2
  # ...配置同上

ragflow-api-3:
  image: infiniflow/ragflow:${RAGFLOW_VERSION}
  container_name: ragflow-api-3
  # ...配置同上

# 独立的 Task Executor 服务
ragflow-worker:
  image: infiniflow/ragflow:${RAGFLOW_VERSION}
  deploy:
    replicas: 2  # 2 个 worker 实例
  environment:
    - START_API_SERVER=0
    - START_TASK_EXECUTOR=1
    - WORKERS=4  # 每个容器 4 个 executor 进程
  # ...其他配置
```

**启动命令**:
```bash
# 使用 replicas 方式
docker-compose up -d

# 或使用 scale 命令动态调整
docker-compose up -d --scale ragflow-api=5
```

---

### 改动 2: Nginx 负载均衡配置

#### 文件: `docker/nginx/ragflow.conf`

**在文件顶部添加 upstream 块**:

```nginx
# 负载均衡后端池
upstream ragflow_backend {
    # 负载均衡算法选择
    least_conn;  # 最少连接（推荐）
    # ip_hash;   # IP 哈希（会话粘性）
    # round_robin;  # 轮询（默认，可省略）

    # 后端服务器列表
    # 如果使用 deploy.replicas，Docker 内部 DNS 会自动负载均衡
    server ragflow-api:9380 weight=1 max_fails=3 fail_timeout=30s;

    # 如果手动定义多个服务
    # server ragflow-api-1:9380 weight=1 max_fails=3 fail_timeout=30s;
    # server ragflow-api-2:9380 weight=1 max_fails=3 fail_timeout=30s;
    # server ragflow-api-3:9380 weight=1 max_fails=3 fail_timeout=30s;

    # 可选：备用服务器
    # server ragflow-api-backup:9380 backup;

    # 保持长连接
    keepalive 32;
}

# KnowFlow 后端（企业功能）
upstream knowflow_backend {
    least_conn;
    server knowflow-backend:5000 max_fails=3 fail_timeout=30s;
    keepalive 16;
}
```

**修改 location 块**:

```nginx
server {
    listen 80;
    server_name _;

    # 静态文件服务（不变）
    root /ragflow/web/dist;

    # API 路由 - 负载均衡
    location /api/v1/ {
        proxy_pass http://ragflow_backend;

        # 代理配置
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;  # 长时间 API 调用（如大文件上传）

        # 缓冲配置
        proxy_buffering off;
        proxy_request_buffering off;

        # 长连接
        proxy_set_header Connection "";
    }

    # KnowFlow 企业 API - 负载均衡
    location /api/knowflow/v1/ {
        proxy_pass http://knowflow_backend/api/v1/;
        # ...其他代理配置同上
    }

    # 其他 location 配置（不变）
    location /v1/ {
        proxy_pass http://ragflow_backend;
        # ...
    }

    # 静态资源缓存（不变）
    location ~ ^/static/(css|js|media)/ {
        expires 10y;
        add_header Cache-Control "public, immutable";
    }
}
```

---

### 改动 3: 启动脚本优化（可选）

#### 文件: `docker/entrypoint.sh`

**添加环境变量控制**:

```bash
#!/bin/bash

# 环境变量默认值
START_API_SERVER=${START_API_SERVER:-1}
START_TASK_EXECUTOR=${START_TASK_EXECUTOR:-1}

# 启动 Nginx（总是启动）
/usr/sbin/nginx

# 条件启动 API Server
if [ "$START_API_SERVER" = "1" ]; then
    echo "Starting RAGFlow API Server..."
    python api/ragflow_server.py &
    API_PID=$!
fi

# 条件启动 Task Executor
if [ "$START_TASK_EXECUTOR" = "1" ]; then
    echo "Starting Task Executors (WORKERS=$WORKERS)..."
    for (( i=0; i<${WORKERS:-1}; i++ )); do
        python rag/svr/task_executor.py "$i" &
    done
fi

# 后台进度更新线程（可选，只在 API 实例中启动）
if [ "$START_API_SERVER" = "1" ]; then
    # 启动进度更新线程
    # ...
fi

# 等待所有进程
wait
```

**使用场景**:

```yaml
# API 专用容器
ragflow-api:
  environment:
    - START_API_SERVER=1
    - START_TASK_EXECUTOR=0

# Worker 专用容器
ragflow-worker:
  environment:
    - START_API_SERVER=0
    - START_TASK_EXECUTOR=1
    - WORKERS=4
```

---

### 改动 4: Redis Session 共享（可选但推荐）

#### 文件: `api/settings.py`

**问题**: Flask 默认使用基于 Cookie 的 Session，多实例时需要共享。

**解决方案 1: 固定 SECRET_KEY**

```python
# api/settings.py
import os

# ❌ 原来的实现（每个实例不同）
# SECRET_KEY = datetime.now().isoformat()

# ✅ 使用固定的 SECRET_KEY
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# 建议在 docker-compose.yml 中配置
# environment:
#   - SECRET_KEY=${SECRET_KEY}
```

**解决方案 2: Redis Session（更好）**

```python
# api/settings.py
from flask_session import Session
import redis

# Flask Session 配置
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'ragflow:session:'
app.config['SESSION_REDIS'] = redis.from_url(
    f"redis://:{os.environ.get('REDIS_PASSWORD')}@redis:6379/1"
)

Session(app)
```

**依赖安装**:
```bash
pip install flask-session redis
```

---

### 改动 5: 健康检查端点（可选）

#### 文件: `api/ragflow_server.py`

**添加健康检查接口**:

```python
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点，供 Nginx 和监控系统使用"""
    try:
        # 检查数据库连接
        from api.db import db
        db.session.execute('SELECT 1')

        # 检查 Redis 连接
        from rag.utils.redis_conn import REDIS_CONN
        REDIS_CONN.health_check()

        return {
            'status': 'healthy',
            'service': 'ragflow-api',
            'timestamp': datetime.now().isoformat()
        }, 200
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }, 503

@app.route('/readiness', methods=['GET'])
def readiness_check():
    """就绪检查，确认服务可以接收流量"""
    # 检查是否正在启动中
    # 检查依赖服务是否可用
    return {'ready': True}, 200
```

**Nginx 使用健康检查**:

```nginx
upstream ragflow_backend {
    server ragflow-api:9380 max_fails=3 fail_timeout=30s;

    # Nginx Plus 支持主动健康检查（商业版）
    # health_check interval=10s fails=3 passes=2 uri=/health;
}
```

**Docker 健康检查**:

```yaml
ragflow-api:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9380/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

---

## 📈 性能评估

### 并发能力对比

| 方案 | 并发连接数 | QPS (读) | QPS (写) | 复杂度 |
|------|-----------|---------|---------|--------|
| **当前单实例** | ~500 | ~300 | ~50 | 低 |
| **3 实例负载均衡** | ~1500 | ~900 | ~150 | 低 |
| **5 实例负载均衡** | ~2500 | ~1500 | ~250 | 低 |
| **Gunicorn (4 worker)** | ~2000 | ~1200 | ~200 | 高 ⚠️ |

*基于 4 核 CPU，数据库查询 10ms 的理论值*

### 资源消耗

**单 Flask 实例**:
- 内存: ~500MB
- CPU: 1 核 (idle ~5%, peak ~80%)

**3 实例总消耗**:
- 内存: ~1.5GB
- CPU: 3 核

**优势**:
- ✅ 横向扩展线性增长
- ✅ 单实例故障影响 ≤ 33%（自动摘除）
- ✅ 滚动更新零停机

---

## 🔍 与 Gunicorn 方案对比

| 维度 | 本方案 (多 Flask 实例) | Gunicorn (多 worker) |
|------|----------------------|---------------------|
| **架构复杂度** | 🟢 低 | 🔴 高 |
| **数据库连接池** | 🟢 每实例独立，易控制 | 🔴 需精确计算防止耗尽 |
| **SECRET_KEY 问题** | 🟢 无影响 | 🔴 需 Redis Session |
| **Gevent 冲突** | 🟢 无风险 | 🔴 与 SDK 可能冲突 |
| **Worker 死锁** | 🟢 进程独立 | 🔴 可能发生 |
| **部署灵活性** | 🟢 可分离部署 | 🟡 单容器多进程 |
| **监控和调试** | 🟢 每个实例独立日志 | 🟡 多 worker 日志混杂 |
| **性能上限** | 🟡 ~3000 QPS | 🟢 ~5000 QPS |

**结论**: 在 3000 QPS 以下场景，本方案**更优**。

---

## 🛠️ 实施步骤

### 阶段 1: 准备工作

1. **备份当前配置**
   ```bash
   cd /Users/zxwei/zhishi/KnowFlow/docker
   cp docker-compose.yml docker-compose.yml.backup
   cp nginx/ragflow.conf nginx/ragflow.conf.backup
   ```

2. **设置 SECRET_KEY 环境变量**
   ```bash
   # .env 文件
   SECRET_KEY=$(openssl rand -hex 32)
   ```

### 阶段 2: 配置修改

1. **修改 docker-compose.yml**
   - 添加 `ragflow-api` 服务（replicas: 3）
   - 添加 `ragflow-worker` 服务（专门运行 task executor）

2. **修改 nginx/ragflow.conf**
   - 添加 `upstream ragflow_backend`
   - 修改 `proxy_pass` 指向 upstream

3. **修改 api/settings.py**
   - 使用固定 SECRET_KEY 或 Redis Session

### 阶段 3: 测试验证

1. **本地测试**
   ```bash
   # 启动 2 个实例测试
   docker-compose up -d --scale ragflow-api=2

   # 检查负载均衡
   for i in {1..10}; do
       curl -I http://localhost/api/v1/health
   done
   ```

2. **压力测试**
   ```bash
   # 使用 ab (Apache Bench)
   ab -n 1000 -c 100 http://localhost/api/v1/health

   # 使用 wrk
   wrk -t 4 -c 100 -d 30s http://localhost/api/v1/health
   ```

3. **监控观察**
   - 查看每个实例的日志
   - 监控数据库连接数
   - 检查 CPU 和内存使用

### 阶段 4: 生产部署

1. **灰度发布**
   ```bash
   # 先启动 1 个新实例
   docker-compose up -d --scale ragflow-api=1

   # 观察稳定后逐步增加
   docker-compose up -d --scale ragflow-api=2
   docker-compose up -d --scale ragflow-api=3
   ```

2. **监控告警**
   - 配置 Prometheus + Grafana
   - 设置错误率告警
   - 设置响应时间告警

3. **回滚方案**
   ```bash
   # 恢复单实例
   docker-compose up -d --scale ragflow-api=1

   # 或完全回滚配置
   mv docker-compose.yml.backup docker-compose.yml
   docker-compose up -d
   ```

---

## 📋 配置检查清单

### 部署前检查

- [ ] 备份当前配置文件
- [ ] 设置固定 SECRET_KEY 环境变量
- [ ] 修改 docker-compose.yml 添加多实例配置
- [ ] 修改 nginx.conf 添加 upstream 配置
- [ ] （可选）安装 flask-session 依赖
- [ ] （可选）添加健康检查端点

### 部署后验证

- [ ] 所有实例正常启动（`docker-compose ps`）
- [ ] Nginx 负载均衡生效（多次请求分发到不同实例）
- [ ] 数据库连接数正常（`SHOW PROCESSLIST`）
- [ ] 用户登录状态持久（刷新页面不掉线）
- [ ] 文档上传和解析正常
- [ ] 对话功能正常
- [ ] 错误日志无异常

### 性能验证

- [ ] 并发请求测试通过
- [ ] 响应时间在可接受范围
- [ ] CPU 使用率 < 80%
- [ ] 内存使用稳定无泄漏
- [ ] 单实例故障可自动恢复

---

## 🚨 常见问题和解决方案

### Q1: 用户登录后立即掉线

**原因**: 多实例间 Session 不共享

**解决**:
```python
# 方案 1: 固定 SECRET_KEY
SECRET_KEY = os.environ.get('SECRET_KEY')

# 方案 2: Redis Session
app.config['SESSION_TYPE'] = 'redis'
```

### Q2: 数据库连接数过多

**原因**: 每个实例都维护连接池

**解决**:
```python
# api/settings.py
SQLALCHEMY_POOL_SIZE = 5  # 降低单实例连接数
# 总连接数 = 实例数(3) × pool_size(5) = 15 < MySQL(151)
```

### Q3: 负载不均衡

**现象**: 某个实例压力特别大

**解决**:
```nginx
# 使用最少连接算法
upstream ragflow_backend {
    least_conn;  # 自动分配到连接最少的实例
}
```

### Q4: 实例启动慢，请求失败

**原因**: 健康检查未配置，Nginx 立即转发请求

**解决**:
```yaml
# docker-compose.yml
ragflow-api:
  healthcheck:
    start_period: 60s  # 给予 60 秒启动时间
```

### Q5: 滚动更新时出现 502 错误

**原因**: 旧实例停止过快

**解决**:
```yaml
# docker-compose.yml
ragflow-api:
  stop_grace_period: 30s  # 优雅关闭等待时间
```

---

## 📚 参考资料

- [Nginx Upstream 模块文档](http://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [Docker Compose Scale 文档](https://docs.docker.com/compose/compose-file/deploy/)
- [Flask-Session 文档](https://flask-session.readthedocs.io/)
- [RAGFlow PR #7845 分析](https://github.com/infiniflow/ragflow/pull/7845)

---

## 📝 维护记录

| 日期 | 版本 | 修改内容 | 修改人 |
|------|------|---------|--------|
| 2025-01-13 | v1.0 | 初始版本，基于 PR #7845 分析 | - |

---

## 🎯 后续优化方向

1. **自动扩缩容** (Kubernetes HPA)
2. **蓝绿部署**
3. **金丝雀发布**
4. **分布式追踪** (OpenTelemetry)
5. **服务网格** (Istio)

---

**结论**: 本方案是一个**低风险、高收益**的架构优化方案，建议在流量增长时优先考虑。相比 Gunicorn 多进程方案，本方案更简单、更稳定、更易维护。
