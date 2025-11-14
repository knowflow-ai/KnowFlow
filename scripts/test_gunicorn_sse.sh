#!/bin/bash

# Gunicorn SSE 性能测试包装脚本

# 参数配置
SCRIPT_NAME="Gunicorn-gthread"
URL="http://localhost:9380/v1/conversation/completion"
AUTHORIZATION="$1"  # 从命令行参数获取
CONVERSATION_ID="95e9f904bdff11f082e366fc51ac58de"

if [ -z "$AUTHORIZATION" ]; then
    echo "错误: 请提供 Authorization token"
    echo "用法: $0 <Authorization-Token>"
    exit 1
fi

# 调用通用测试脚本
/Users/zxwei/zhishi/KnowFlow/scripts/test_sse_performance.sh "$SCRIPT_NAME" "$URL" "$AUTHORIZATION" "$CONVERSATION_ID"
