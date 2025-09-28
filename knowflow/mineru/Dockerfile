# 多阶段构建：先下载模型
FROM mineru-vllm:latest as model-downloader

# 安装下载工具
RUN pip install --no-cache-dir \
    tqdm \
    requests \
    huggingface-hub

# 复制下载脚本
COPY download_models.py /opt/mineru/download_models.py

# 创建模型目录
RUN mkdir -p /root/.mineru/models \
    && mkdir -p /root/.cache/huggingface/hub

# 在构建时下载所有模型（这会让镜像变大，但实现完全离线）
RUN python /opt/mineru/download_models.py --type all --retry 3

# 最终镜像
FROM mineru-vllm:latest

# 从第一阶段复制已下载的模型
COPY --from=model-downloader /root/.mineru/models /root/.mineru/models
COPY --from=model-downloader /root/.cache/huggingface/hub /root/.cache/huggingface/hub

# 设置环境变量
ENV MINERU_MODEL_SOURCE=local \
    MINERU_MODELS_PRELOADED=true

# 验证模型文件
COPY download_models.py /opt/mineru/download_models.py
RUN python /opt/mineru/download_models.py --verify-only && \
    rm /opt/mineru/download_models.py

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1