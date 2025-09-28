#!/bin/bash

echo "=== MinerU 容器启动 ==="

# 如果启用了自动下载模型
if [ "$MINERU_AUTO_DOWNLOAD_MODELS" = "true" ]; then
    echo "检查并下载模型..."
    python /opt/mineru/download_models.py --type "${MINERU_MODEL_TYPE:-all}"

    if [ $? -ne 0 ]; then
        echo "警告: 部分模型下载失败，但继续启动服务"
    fi
else
    echo "跳过模型下载 (MINERU_AUTO_DOWNLOAD_MODELS=false)"
fi

# 获取原始命令
ORIGINAL_CMD="$1"
shift

# 执行原始的 MinerU 命令
echo "启动 MinerU 服务: $ORIGINAL_CMD $@"
exec "$ORIGINAL_CMD" "$@"