FROM python:3.10-slim

LABEL maintainer="KnowFlow Team"
LABEL description="PaddleOCR-VL API Service for Document Parsing"

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        wget \
        curl && \
    rm -rf /var/lib/apt/lists/*

# 安装 PaddlePaddle GPU 版本
ARG PADDLE_VERSION="3.2.0"
ARG CUDA_VERSION="cu126"
RUN python -m pip install --no-cache-dir \
    paddlepaddle-gpu==${PADDLE_VERSION} \
    -i https://www.paddlepaddle.org.cn/packages/stable/${CUDA_VERSION}/

# 安装 PaddleOCR
ARG PADDLEOCR_VERSION=">=3.3.1,<3.4"
RUN python -m pip install --no-cache-dir \
    "paddleocr[doc-parser]${PADDLEOCR_VERSION}" && \
    python -m pip install --no-cache-dir \
    https://paddle-whl.bj.bcebos.com/nightly/${CUDA_VERSION}/safetensors/safetensors-0.6.2.dev0-cp38-abi3-linux_x86_64.whl && \
    paddlex --install serving

# 创建用户
RUN groupadd -g 1000 paddleocr && \
    useradd -m -s /bin/bash -u 1000 -g 1000 paddleocr

ENV HOME=/home/paddleocr
WORKDIR /home/paddleocr

# 可选：离线模式下载模型
ARG BUILD_FOR_OFFLINE=false
RUN if [ "${BUILD_FOR_OFFLINE}" = 'true' ]; then \
        mkdir -p "${HOME}/.paddlex/official_models" && \
        cd "${HOME}/.paddlex/official_models" && \
        wget -q https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/UVDoc_infer.tar \
            https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-LCNet_x1_0_doc_ori_infer.tar \
            https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-DocLayoutV2_infer.tar \
            https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PaddleOCR-VL_infer.tar && \
        tar -xf UVDoc_infer.tar && mv UVDoc_infer UVDoc && \
        tar -xf PP-LCNet_x1_0_doc_ori_infer.tar && mv PP-LCNet_x1_0_doc_ori_infer PP-LCNet_x1_0_doc_ori && \
        tar -xf PP-DocLayoutV2_infer.tar && mv PP-DocLayoutV2_infer PP-DocLayoutV2 && \
        tar -xf PaddleOCR-VL_infer.tar && mv PaddleOCR-VL_infer PaddleOCR-VL && \
        rm -f *.tar && \
        mkdir -p "${HOME}/.paddlex/fonts" && \
        wget -q -P "${HOME}/.paddlex/fonts" https://paddle-model-ecology.bj.bcebos.com/paddlex/PaddleX3.0/fonts/PingFang-SC-Regular.ttf && \
        chown -R paddleocr:paddleocr "${HOME}/.paddlex"; \
    fi

# 复制配置文件
COPY --chown=paddleocr:paddleocr pipeline_config.yaml /home/paddleocr/

USER paddleocr

EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["paddlex", "--serve", "--pipeline", "/home/paddleocr/pipeline_config.yaml"]
