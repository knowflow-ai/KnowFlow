# Gunicorn 生产部署方案

> **方案类型**: 单容器多进程部署
> **Worker 模式**: sync（同步）
> **目标规模**: 4-8 workers
> **复杂度**: 中
> **风险等级**: 中（已规避 PR #7845 的所有已知坑点）

---

## 📋 方案概述

本方案基于对 [RAGFlow PR #7845](https://github.com/infiniflow/ragflow/pull/7845) 的深入分析，针对社区反馈的**所有已知坑点**设计了完整的规避措施，提供一个**生产可用的 Gunicorn 部署方案**。

### 核心策略

```
✅ 使用 sync worker（避免 gevent monkey-patching 坑）
✅ 精确配置数据库连接池（避免连接耗尽坑）
✅ 固定 SECRET_KEY（避免 JWT 不一致坑）
✅ 优雅关闭配置（避免 worker 死锁坑）
✅ 预加载应用（避免 fork 问题坑）
```

---

## 🐛 PR #7845 已知坑点及规避措施

### 坑点 1: 数据库连接池耗尽 🔴

**问题描述**:
```
pymysql.err.InterfaceError: (0, '')
RecursionError: maximum recursion depth exceeded
```

**根本原因**:
- 每个 worker 独立维护连接池
- 总连接数 = workers × pool_size
- 超过 MySQL 的 max_connections (默认 151)

**规避措施**:

```python
# 1. 计算公式
workers = 4-8  # 中等规模
pool_size = 5  # 每个 worker 的连接池大小
total_connections = workers × pool_size = 8 × 5 = 40

# 确保: total_connections < MySQL max_connections - 20
# 40 < 151 - 20 = 131 ✅ 安全

# 2. 配置文件 (conf/service_conf.yaml)
mysql:
  pool_size: 5           # 降低单进程连接数
  max_overflow: 10       # 最大溢出连接
  pool_pre_ping: true    # 连接前检查有效性
  pool_recycle: 3600     # 1小时回收连接

# 3. MySQL 服务器配置
[mysqld]
max_connections = 200    # 提高 MySQL 最大连接数
wait_timeout = 28800     # 8小时超时
interactive_timeout = 28800
```

**验证方法**:
```sql
-- 监控当前连接数
SHOW STATUS LIKE 'Threads_connected';
SHOW PROCESSLIST;

-- 检查最大连接数
SHOW VARIABLES LIKE 'max_connections';
```

---

### 坑点 2: Gevent Monkey-Patching 冲突 🟡

**问题描述**:
```python
RecursionError: maximum recursion depth exceeded
# 发生在调用 dashscope、OpenAI 等 SDK 时
```

**根本原因**:
- `gevent.monkey.patch_all()` 替换了 SSL 模块
- 某些 SDK 内部使用原生 SSL 实现
- Monkey patch 后调用这些 SDK 导致递归错误

**规避措施**:

```python
# ✅ 方案: 不使用 gevent worker
# gunicorn_conf.py
worker_class = 'sync'  # 使用同步 worker，完全避免问题

# ❌ 禁用 gevent（以下配置不使用）
# worker_class = 'gevent'
# from gevent import monkey
# monkey.patch_all()
```

**性能影响**:
- sync worker QPS: ~200-300 per worker
- 8 workers 总 QPS: ~1600-2400
- **足够应对大多数场景**

---

### 坑点 3: SECRET_KEY 不一致导致 JWT 失效 🔴

**问题描述**:
```
用户登录后立即被登出
不同 worker 验证 token 失败
```

**根本原因**:
```python
# 原代码问题
SECRET_KEY = datetime.now().isoformat()
# 每个 worker 启动时间不同，SECRET_KEY 不同！
```

**规避措施**:

```python
# 方案 1: 环境变量固定 SECRET_KEY（推荐）
# api/settings.py
import os

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required in production!")

# 方案 2: 配置文件
SECRET_KEY = os.environ.get('SECRET_KEY',
    read_from_config('security.secret_key'))

# 方案 3: Redis Session（最佳）
from flask_session import Session

app.config.update(
    SESSION_TYPE='redis',
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_KEY_PREFIX='ragflow:session:',
    SESSION_REDIS=redis.from_url(REDIS_URL)
)
Session(app)
```

**生成安全的 SECRET_KEY**:
```bash
# 生成随机密钥
python -c "import secrets; print(secrets.token_hex(32))"

# 或使用 openssl
openssl rand -hex 32
```

**Docker Compose 配置**:
```yaml
ragflow-server:
  environment:
    - SECRET_KEY=${SECRET_KEY}  # 从 .env 读取

# .env 文件
SECRET_KEY=your-64-character-hex-string-here
```

---

### 坑点 4: Worker 关闭死锁 🟡

**问题描述**:
```bash
docker-compose stop  # 卡住不动
需要 kill -9 强制终止
```

**根本原因**:
- Worker 正在处理长连接请求（SSE、WebSocket）
- 优雅关闭超时配置不当
- 数据库连接未正确释放

**规避措施**:

```python
# gunicorn_conf.py

# 1. 设置合理的超时
timeout = 30              # 请求超时 30 秒
graceful_timeout = 30     # 优雅关闭超时 30 秒
keepalive = 2             # Keep-Alive 超时 2 秒

# 2. Worker 退出时清理资源
def worker_exit(server, worker):
    """Worker 退出时的清理钩子"""
    from api.db import db
    from rag.utils.redis_conn import REDIS_CONN

    try:
        # 关闭数据库连接
        db.session.remove()
        db.engine.dispose()

        # 关闭 Redis 连接
        REDIS_CONN.close()

        worker.log.info(f"Worker {worker.pid} cleaned up successfully")
    except Exception as e:
        worker.log.error(f"Error during worker cleanup: {e}")

# 3. 捕获关闭信号
def on_exit(server):
    """主进程退出时的清理"""
    server.log.info("Gunicorn master exiting, cleaning up...")

# 4. Worker 异常时重启
max_requests = 1000       # 处理 1000 请求后重启（防止内存泄漏）
max_requests_jitter = 50  # 随机抖动，避免同时重启
```

**Docker 优雅关闭配置**:
```yaml
ragflow-server:
  stop_grace_period: 60s  # 给予 60 秒优雅关闭时间

  # 健康检查
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9380/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

---

### 坑点 5: macOS Fork 兼容性问题 🟢

**问题描述**:
```
objc_initializeAfterForkError
Worker failed to boot. Perhaps out of memory?
```

**根本原因**:
- macOS 的 Core Foundation 框架不支持多进程 fork
- 仅在 macOS 开发环境出现

**规避措施**:

```python
# gunicorn_conf.py

import platform

# 开发环境检测
if platform.system() == 'Darwin':  # macOS
    # 本地开发使用单 worker
    workers = 1
    worker_class = 'sync'
    print("WARNING: Running on macOS, using 1 worker for development")
else:
    # 生产环境（Linux）使用多 worker
    workers = 4

# 或强制使用 preload（推荐）
preload_app = True  # 预加载应用，减少 fork 问题
```

**开发建议**:
```bash
# macOS 本地开发：使用 Docker（Linux 环境）
docker-compose up -d

# 或使用单 worker 模式
gunicorn -w 1 -k sync api.wsgi:app
```

---

## 🔧 完整配置方案

### 1. Gunicorn 配置文件

**文件**: `conf/gunicorn_conf.py`

```python
# -*- coding: utf-8 -*-
"""
Gunicorn 生产环境配置
基于 RAGFlow PR #7845 优化，规避所有已知坑点
"""

import multiprocessing
import os
import platform

# ========================================
# 基础配置
# ========================================

# 绑定地址
bind = f"{os.getenv('HOST_IP', '0.0.0.0')}:{os.getenv('HOST_PORT', '9380')}"

# 反向代理配置
forwarded_allow_ips = '*'
proxy_protocol = False
proxy_allow_ips = '*'

# ========================================
# Worker 配置（关键）
# ========================================

# Worker 数量计算
def calculate_workers():
    """
    根据 CPU 核心数和环境计算 worker 数量

    规则：
    - macOS: 1 worker（避免 fork 问题）
    - Linux: 2 * CPU + 1 或环境变量指定
    - 最大: 8 workers（避免数据库连接池耗尽）
    """
    if platform.system() == 'Darwin':
        return 1  # macOS 开发环境

    # 从环境变量读取
    workers_env = os.getenv('GUNICORN_WORKERS')
    if workers_env:
        return int(workers_env)

    # 默认计算：2 * CPU + 1，但不超过 8
    cpu_count = multiprocessing.cpu_count()
    calculated = 2 * cpu_count + 1
    return min(calculated, 8)

workers = calculate_workers()

# ✅ 使用 sync worker（避免 gevent 坑）
worker_class = 'sync'

# Worker 连接数（每个 worker 的最大并发连接）
worker_connections = 1000

# ========================================
# 超时配置（避免死锁）
# ========================================

# 请求超时（秒）
# 如果请求处理超过此时间，worker 会被杀死并重启
timeout = 120  # 2 分钟（考虑文档上传等长时间操作）

# 优雅关闭超时（秒）
# 停止信号发出后，等待 worker 完成当前请求的最大时间
graceful_timeout = 30

# Keep-Alive 超时（秒）
keepalive = 5

# ========================================
# 性能优化配置
# ========================================

# 预加载应用（重要！）
# 优点：
# 1. 减少内存占用（代码共享）
# 2. 避免 fork 时的资源竞争
# 3. 加快 worker 启动速度
preload_app = True

# Worker 重启策略（防止内存泄漏）
max_requests = 1000        # 每个 worker 处理 1000 请求后重启
max_requests_jitter = 100  # 随机抖动，避免同时重启

# ========================================
# 日志配置
# ========================================

# 访问日志
accesslog = os.getenv('GUNICORN_ACCESS_LOG', '-')  # '-' 表示 stdout
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 错误日志
errorlog = os.getenv('GUNICORN_ERROR_LOG', '-')
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')

# ========================================
# 进程命名
# ========================================

proc_name = 'ragflow-gunicorn'

# ========================================
# 钩子函数（关键！）
# ========================================

def on_starting(server):
    """
    服务器启动时执行
    """
    server.log.info(f"Gunicorn starting with {workers} workers")
    server.log.info(f"Worker class: {worker_class}")
    server.log.info(f"Preload app: {preload_app}")

    # 检查关键环境变量
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        server.log.warning("WARNING: SECRET_KEY not set! This will cause issues in production!")


def post_fork(server, worker):
    """
    Worker 进程 fork 后执行

    用途：
    1. 重新初始化数据库连接（避免连接共享）
    2. 重新初始化 Redis 连接
    3. 设置进程特定的配置
    """
    server.log.info(f"Worker {worker.pid} spawned")

    # 重新初始化数据库连接
    try:
        from api.db import db
        db.engine.dispose()  # 关闭父进程的连接
        server.log.info(f"Worker {worker.pid}: Database connections reinitialized")
    except Exception as e:
        server.log.error(f"Worker {worker.pid}: Failed to reinitialize database: {e}")


def pre_fork(server, worker):
    """
    Worker 进程 fork 前执行
    """
    pass


def pre_exec(server):
    """
    在重新执行前执行
    """
    server.log.info("Forked child, re-executing.")


def when_ready(server):
    """
    服务器准备好接收请求时执行
    """
    server.log.info("Server is ready. Spawning workers")


def worker_int(worker):
    """
    Worker 收到 SIGINT 信号时执行
    """
    worker.log.info(f"Worker {worker.pid} received SIGINT (Ctrl+C)")


def worker_abort(worker):
    """
    Worker 收到 SIGABRT 信号时执行（通常是超时）
    """
    worker.log.error(f"Worker {worker.pid} aborted (timeout or crash)")


def worker_exit(server, worker):
    """
    Worker 退出时执行（关键！）

    用途：
    1. 清理数据库连接
    2. 清理 Redis 连接
    3. 释放其他资源
    """
    try:
        from api.db import db
        from rag.utils.redis_conn import REDIS_CONN

        # 关闭数据库连接池
        db.session.remove()
        db.engine.dispose()

        # 关闭 Redis 连接
        if hasattr(REDIS_CONN, 'close'):
            REDIS_CONN.close()

        worker.log.info(f"Worker {worker.pid} cleaned up successfully")
    except Exception as e:
        worker.log.error(f"Worker {worker.pid} cleanup error: {e}")


def on_exit(server):
    """
    主进程退出时执行
    """
    server.log.info("Gunicorn master process exiting")


def child_exit(server, worker):
    """
    子进程退出时执行
    """
    server.log.info(f"Worker {worker.pid} exited")


def nworkers_changed(server, new_value, old_value):
    """
    Worker 数量变化时执行
    """
    server.log.info(f"Worker count changed from {old_value} to {new_value}")


# ========================================
# 安全配置
# ========================================

# 限制请求行大小（防止攻击）
limit_request_line = 4096

# 限制请求头数量
limit_request_fields = 100

# 限制请求头大小
limit_request_field_size = 8190

# ========================================
# SSL 配置（可选）
# ========================================

# keyfile = '/path/to/key.pem'
# certfile = '/path/to/cert.pem'

# ========================================
# 环境变量说明
# ========================================
"""
支持的环境变量：

- GUNICORN_WORKERS: Worker 数量（默认：2 * CPU + 1，最大 8）
- HOST_IP: 绑定 IP（默认：0.0.0.0）
- HOST_PORT: 绑定端口（默认：9380）
- SECRET_KEY: Flask 密钥（生产环境必须设置！）
- GUNICORN_ACCESS_LOG: 访问日志路径（默认：stdout）
- GUNICORN_ERROR_LOG: 错误日志路径（默认：stdout）
- GUNICORN_LOG_LEVEL: 日志级别（默认：info）

数据库连接池配置（在 conf/service_conf.yaml）：
- mysql.pool_size: 每个 worker 的连接数（推荐：5）
- mysql.max_overflow: 最大溢出连接（推荐：10）
- mysql.pool_pre_ping: 连接前检查（推荐：true）
- mysql.pool_recycle: 连接回收时间（推荐：3600 秒）

计算公式：
total_connections = workers × (pool_size + max_overflow)
确保: total_connections < MySQL max_connections - 20
"""
```

---

### 2. WSGI 入口文件

**文件**: `api/wsgi.py`

```python
# -*- coding: utf-8 -*-
"""
WSGI 应用入口
用于 Gunicorn 生产部署
"""

import os
import sys

# 添加项目路径到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置环境变量（如果未设置）
os.environ.setdefault('PYTHONPATH', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入 Flask 应用
from api.ragflow_server import app

# Gunicorn 会使用这个 application 对象
application = app

# 健康检查端点（如果未定义）
if not hasattr(app, 'health_endpoint_registered'):
    @app.route('/health', methods=['GET'])
    def health_check():
        """健康检查端点"""
        try:
            from api.db import db
            db.session.execute('SELECT 1')
            return {'status': 'healthy', 'service': 'ragflow-api'}, 200
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}, 503

    app.health_endpoint_registered = True

if __name__ == '__main__':
    # 开发模式（不推荐生产使用）
    app.run(host='0.0.0.0', port=9380, debug=False)
```

---

### 3. 数据库配置优化

**文件**: `conf/service_conf.yaml`

```yaml
mysql:
  # ========================================
  # 连接池配置（关键！）
  # ========================================

  # 每个 worker 的连接池大小
  # 计算: workers(8) × pool_size(5) = 40 < MySQL max_connections(151)
  pool_size: 5

  # 最大溢出连接数
  # 临时需求时可以超出 pool_size，但不超过 pool_size + max_overflow
  max_overflow: 10

  # 连接前 ping 检查（重要！）
  # 避免使用已断开的连接
  pool_pre_ping: true

  # 连接回收时间（秒）
  # 超过此时间的连接会被回收，避免 MySQL wait_timeout 问题
  pool_recycle: 3600  # 1 小时

  # 连接池超时（秒）
  # 获取连接时的最大等待时间
  pool_timeout: 30

  # 连接参数
  max_retries: 3
  retry_interval: 5

  # ========================================
  # 连接信息
  # ========================================
  name: ragflow
  user: ragflow
  password: ${MYSQL_PASSWORD}
  host: mysql
  port: 3306
  charset: utf8mb4

# ========================================
# MySQL 服务器配置建议
# ========================================
# 在 MySQL 配置文件 (my.cnf) 中添加：
#
# [mysqld]
# max_connections = 200          # 提高最大连接数
# wait_timeout = 28800            # 8 小时（默认）
# interactive_timeout = 28800
# max_allowed_packet = 64M        # 大文件上传
# innodb_buffer_pool_size = 2G    # 根据内存调整
```

---

### 4. Docker 配置

**文件**: `docker/docker-compose.yml`（修改部分）

```yaml
services:
  ragflow-server:
    image: infiniflow/ragflow:${RAGFLOW_VERSION}
    container_name: ragflow-server

    # 环境变量配置
    environment:
      # ========================================
      # 必须配置（生产环境）
      # ========================================
      - SECRET_KEY=${SECRET_KEY}  # 从 .env 读取，必须设置！

      # ========================================
      # Gunicorn 配置
      # ========================================
      - USE_GUNICORN=1             # 启用 Gunicorn
      - GUNICORN_WORKERS=6         # Worker 数量（可调整）
      - GUNICORN_LOG_LEVEL=info

      # ========================================
      # 数据库配置
      # ========================================
      - MYSQL_PASSWORD=${MYSQL_PASSWORD}
      - REDIS_PASSWORD=${REDIS_PASSWORD}

      # ========================================
      # 其他配置
      # ========================================
      - PYTHONUNBUFFERED=1
      - TZ=Asia/Shanghai

    # 端口映射
    ports:
      - "${SVR_HTTP_PORT:-9380}:9380"

    # 健康检查
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9380/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s  # 给予 60 秒启动时间

    # 优雅关闭配置
    stop_grace_period: 60s

    # 资源限制（可选）
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

    # 依赖服务
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy

    # 网络配置
    networks:
      - ragflow

    # 卷挂载
    volumes:
      - ./conf:/ragflow/conf
      - ./data:/ragflow/data
```

**文件**: `docker/.env`（新增/修改）

```bash
# ========================================
# 安全配置（必须设置！）
# ========================================

# 生成命令: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-64-character-hex-string-change-in-production

# ========================================
# Gunicorn 配置
# ========================================
USE_GUNICORN=1
GUNICORN_WORKERS=6  # 根据 CPU 核心数调整
GUNICORN_LOG_LEVEL=info

# ========================================
# 数据库配置
# ========================================
MYSQL_PASSWORD=your-mysql-password
REDIS_PASSWORD=your-redis-password

# ========================================
# 服务端口
# ========================================
SVR_HTTP_PORT=9380
```

---

### 5. 启动脚本修改

**文件**: `docker/entrypoint.sh`（修改部分）

```bash
#!/bin/bash

# ... 前面的代码不变 ...

# ========================================
# 启动 API 服务器
# ========================================

USE_GUNICORN=${USE_GUNICORN:-0}

if [ "$USE_GUNICORN" = "1" ]; then
    echo "Starting RAGFlow with Gunicorn..."

    # 检查 SECRET_KEY
    if [ -z "$SECRET_KEY" ]; then
        echo "ERROR: SECRET_KEY environment variable is not set!"
        echo "Please set SECRET_KEY in your .env file"
        exit 1
    fi

    # 启动 Gunicorn
    gunicorn \
        -c /ragflow/conf/gunicorn_conf.py \
        api.wsgi:application &

    API_PID=$!
    echo "Gunicorn started with PID $API_PID"
else
    echo "Starting RAGFlow with Flask development server..."
    python api/ragflow_server.py &
    API_PID=$!
fi

# ========================================
# 启动 Task Executors
# ========================================

# ... Task Executor 启动逻辑不变 ...

# ========================================
# 等待所有进程
# ========================================

wait $API_PID
```

---

## 📊 性能评估

### 并发能力

| Worker 数 | 单 Worker QPS | 总 QPS | 数据库连接数 | 内存占用 |
|----------|--------------|--------|-------------|---------|
| 4 | 250 | 1000 | 60 (4×15) | ~2GB |
| 6 | 250 | 1500 | 90 (6×15) | ~3GB |
| 8 | 250 | 2000 | 120 (8×15) | ~4GB |

*基于 4 核 CPU，数据库查询 10ms 的估算*

### 资源消耗

**内存**:
- 主进程: ~500MB
- 每个 worker: ~400MB
- 总计: 500 + (workers × 400) MB

**CPU**:
- Idle: ~5%
- 中等负载: ~40-60%
- 高负载: ~80-95%

---

## 🚀 部署步骤

### 阶段 1: 准备工作

```bash
# 1. 备份当前配置
cd /Users/zxwei/zhishi/KnowFlow/docker
cp docker-compose.yml docker-compose.yml.backup
cp .env .env.backup

# 2. 生成 SECRET_KEY
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" >> .env

# 3. 检查环境变量
grep SECRET_KEY .env
```

### 阶段 2: 配置文件

```bash
# 1. 创建 Gunicorn 配置
cp /path/to/gunicorn_conf.py conf/gunicorn_conf.py

# 2. 创建 WSGI 入口
cp /path/to/wsgi.py api/wsgi.py

# 3. 修改数据库配置
# 编辑 conf/service_conf.yaml，添加连接池配置

# 4. 修改 docker-compose.yml
# 添加环境变量: USE_GUNICORN=1, SECRET_KEY, GUNICORN_WORKERS

# 5. 修改 entrypoint.sh
# 添加 Gunicorn 启动逻辑和 SECRET_KEY 检查
```

### 阶段 3: 测试验证

```bash
# 1. 启动服务
docker-compose up -d

# 2. 查看日志
docker-compose logs -f ragflow-server

# 3. 检查 worker 数量
docker exec ragflow-server ps aux | grep gunicorn

# 4. 检查数据库连接数
docker exec ragflow-mysql mysql -uragflow -p${MYSQL_PASSWORD} -e "SHOW PROCESSLIST;"

# 5. 健康检查
curl http://localhost:9380/health

# 6. 压力测试
ab -n 1000 -c 50 http://localhost:9380/api/v1/health
```

### 阶段 4: 监控调优

```bash
# 1. 监控内存使用
docker stats ragflow-server

# 2. 监控数据库连接
watch -n 5 'docker exec ragflow-mysql mysql -uragflow -p${MYSQL_PASSWORD} -e "SHOW STATUS LIKE \"Threads_connected\";"'

# 3. 监控 worker 状态
docker exec ragflow-server ps -eo pid,ppid,cmd,pmem,pcpu | grep gunicorn

# 4. 分析日志
docker logs ragflow-server 2>&1 | grep -E "ERROR|WARNING|timeout"
```

---

## 🔍 故障排查

### 问题 1: 用户登录后掉线

**诊断**:
```bash
# 检查 SECRET_KEY 是否设置
docker exec ragflow-server env | grep SECRET_KEY
```

**解决**:
```bash
# 确保 .env 中设置了 SECRET_KEY
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env
docker-compose up -d
```

### 问题 2: 数据库连接超过最大限制

**诊断**:
```sql
-- 查看当前连接数
SHOW STATUS LIKE 'Threads_connected';

-- 查看最大连接数
SHOW VARIABLES LIKE 'max_connections';
```

**解决**:
```yaml
# 降低连接池大小
# conf/service_conf.yaml
mysql:
  pool_size: 3  # 从 5 降低到 3
  max_overflow: 5  # 从 10 降低到 5
```

### 问题 3: Worker 超时被杀死

**诊断**:
```bash
# 查看日志中的 timeout 错误
docker logs ragflow-server 2>&1 | grep timeout
```

**解决**:
```python
# conf/gunicorn_conf.py
timeout = 180  # 从 120 增加到 180 秒
```

### 问题 4: Worker 启动失败

**诊断**:
```bash
# 查看详细错误日志
docker-compose logs ragflow-server | grep -A 10 "Worker"
```

**可能原因**:
- 内存不足
- 端口冲突
- 依赖服务未就绪

**解决**:
```yaml
# 增加启动等待时间
healthcheck:
  start_period: 120s  # 从 60s 增加到 120s
```

---

## 📋 配置检查清单

### 部署前检查

- [ ] 已备份当前配置文件
- [ ] 已生成并设置 SECRET_KEY 环境变量
- [ ] 已创建 `conf/gunicorn_conf.py`
- [ ] 已创建 `api/wsgi.py`
- [ ] 已修改 `conf/service_conf.yaml` 配置数据库连接池
- [ ] 已修改 `docker-compose.yml` 添加环境变量
- [ ] 已修改 `docker/entrypoint.sh` 添加 Gunicorn 启动逻辑
- [ ] 已检查 MySQL max_connections 配置

### 部署后验证

- [ ] 所有 worker 正常启动（`ps aux | grep gunicorn`）
- [ ] 健康检查通过（`curl /health`）
- [ ] 数据库连接数正常（< max_connections - 20）
- [ ] 用户登录状态持久（多次请求不掉线）
- [ ] 文档上传功能正常
- [ ] 对话功能正常
- [ ] 压力测试通过（>1000 QPS）
- [ ] 无 timeout 错误
- [ ] 无内存泄漏

---

## 📚 参考资料

- [Gunicorn 官方文档](https://docs.gunicorn.org/)
- [RAGFlow PR #7845](https://github.com/infiniflow/ragflow/pull/7845)
- [Flask 生产部署指南](https://flask.palletsprojects.com/en/2.3.x/deploying/)
- [SQLAlchemy 连接池配置](https://docs.sqlalchemy.org/en/20/core/pooling.html)

---

## 🎯 总结

### 方案优势

✅ **简化部署**: 单容器内多进程，无需复杂的多实例编排
✅ **规避坑点**: 完全规避 PR #7845 的所有已知问题
✅ **性能提升**: 4-8 workers 可达 1000-2000 QPS
✅ **资源可控**: 精确控制数据库连接和内存使用
✅ **生产就绪**: 完整的监控、健康检查和优雅关闭

### 适用场景

- 单机部署，希望提升并发能力
- 不想维护多容器/多实例架构
- QPS 需求在 1000-2000 范围
- CPU 核心数 4-8 核

### 不适用场景

- 超高并发 (>3000 QPS) → 考虑多实例方案
- 需要极致性能 → 考虑 gevent worker（但要处理 SDK 兼容性）
- 分布式部署 → 考虑 Kubernetes + 横向扩展

---

**最终建议**: 本方案是在**简化部署**和**性能提升**之间的最佳平衡点，适合大多数生产场景。
