# ===============================================
# RAG 评估系统 - 生产环境 Dockerfile
# 前后端一体化部署，源码不公开
# ===============================================

FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci && npm cache clean --force

COPY frontend/ ./
RUN npm run build

FROM python:3.10-slim

LABEL maintainer="RAG Evaluation Team"
LABEL description="RAG Evaluation System - All-in-one Container"

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

COPY backend/*.py /app/
COPY backend/services/ /app/services/
COPY backend/models/ /app/models/

# 编译 Python 文件为 .pyc (使用 -b 生成 .pyc 在源文件旁边，而不是 __pycache__)
RUN python3 -m compileall -b /app && \
    find /app -type f -name "*.py" ! -name "__init__.py" -delete

COPY --from=frontend-builder /build/frontend/dist /app/static

RUN echo 'server {\n\
    listen 80;\n\
    server_name _;\n\
    root /app/static;\n\
    index index.html;\n\
    \n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
    \n\
    location /api/ {\n\
        proxy_pass http://127.0.0.1:5002;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n\
        proxy_set_header X-Forwarded-Proto $scheme;\n\
        proxy_connect_timeout 60s;\n\
        proxy_send_timeout 60s;\n\
        proxy_read_timeout 300s;\n\
    }\n\
    \n\
    location /health {\n\
        proxy_pass http://127.0.0.1:5002/health;\n\
        access_log off;\n\
    }\n\
}' > /etc/nginx/sites-available/default

RUN echo '[supervisord]\n\
nodaemon=true\n\
user=root\n\
logfile=/var/log/supervisor/supervisord.log\n\
pidfile=/var/run/supervisord.pid\n\
loglevel=info\n\
\n\
[program:nginx]\n\
command=/usr/sbin/nginx -g "daemon off;"\n\
autostart=true\n\
autorestart=true\n\
priority=10\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
\n\
[program:backend]\n\
command=python3 app_new.pyc\n\
directory=/app\n\
autostart=true\n\
autorestart=true\n\
priority=20\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
environment=PYTHONPATH="/app",PYTHONUNBUFFERED="1"\n\
' > /etc/supervisor/conf.d/rag-evaluation.conf

RUN mkdir -p /var/log/supervisor /app/tmp /app/logs /app/data && \
    chmod -R 755 /app

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
