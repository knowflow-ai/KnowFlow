#!/bin/bash

# 评测系统API完整测试脚本
BASE_URL="http://localhost:5000/api/v1"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "KnowFlow 评测系统 API 测试"
echo "=========================================="
echo ""

# 测试计数
TOTAL=0
PASSED=0
FAILED=0

# 测试函数
test_api() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4

    TOTAL=$((TOTAL + 1))
    echo -n "[$TOTAL] 测试 $name ... "

    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X $method "$BASE_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $http_code)"
        PASSED=$((PASSED + 1))
        # echo "   Response: $(echo $body | head -c 100)..."
    else
        echo -e "${RED}✗ FAIL${NC} (HTTP $http_code)"
        FAILED=$((FAILED + 1))
        echo "   Response: $body"
    fi
}

echo "=== 1. 系统健康检查 ==="
test_api "健康检查" "GET" "/evaluation/health"
echo ""

echo "=== 2. 配置管理 API ==="
test_api "获取配置" "GET" "/evaluation/config"
test_api "更新配置" "PUT" "/evaluation/config" '{"api":{"provider":"openai","model":"gpt-4"}}'
test_api "测试连接" "POST" "/evaluation/test-connection" '{"provider":"openai","apiKey":"sk-test","endpoint":"https://api.openai.com/v1","model":"gpt-4"}'
echo ""

echo "=== 3. 统计数据 API ==="
test_api "获取统计数据" "GET" "/evaluation/statistics"
echo ""

echo "=== 4. 数据集管理 API ==="
test_api "获取数据集列表" "GET" "/evaluation/datasets"
# test_api "上传数据集" "POST" "/evaluation/datasets" # 需要文件上传
echo ""

echo "=== 5. 评测任务 API ==="
test_api "获取任务列表" "GET" "/evaluation/tasks"
# test_api "创建评测任务" "POST" "/evaluation/tasks" '{"name":"测试任务","kb_id":"test","dataset_id":"test","metrics":["faithfulness"]}'
echo ""

echo "=== 6. 评测报告 API ==="
test_api "获取报告列表" "GET" "/evaluation/reports"
# test_api "获取报告详情" "GET" "/evaluation/reports/test-task-id"
echo ""

echo "=== 7. 指标管理 API ==="
test_api "获取指标列表" "GET" "/evaluation/metrics"
test_api "获取指标分组" "GET" "/evaluation/metrics/groups"
echo ""

echo "=== 8. 知识库 API ==="
test_api "获取知识库列表" "GET" "/knowledgebases?current_page=1&size=10"
echo ""

echo "=========================================="
echo "测试汇总"
echo "=========================================="
echo "总计: $TOTAL"
echo -e "${GREEN}通过: $PASSED${NC}"
echo -e "${RED}失败: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
    exit 0
else
    echo -e "${RED}✗ 有 $FAILED 个测试失败${NC}"
    exit 1
fi
