# 前端构建阶段
FROM node:18 AS frontend-builder
WORKDIR /app/frontend
COPY web /app/frontend
# 设置npm和pnpm使用淘宝镜像源
RUN npm config set registry https://registry.npmmirror.com && \
    npm install -g pnpm
# 设置环境变量禁用交互式提示
ENV CI=true
# 安装依赖并构建
RUN pnpm config set registry https://registry.npmmirror.com && \
    pnpm i && pnpm build

# 前端服务阶段
FROM nginx:alpine AS frontend
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html
# 暴露前端端口
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# 后端构建阶段
FROM python:3.10.16-slim AS backend
WORKDIR /app

# 替换为阿里云镜像源并安装系统依赖
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /app/
# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && rm -rf ~/.cache/pip
# 复制后端代码
COPY server /app


# 暴露后端端口
EXPOSE 5000
CMD ["python3.10", "app.py"]