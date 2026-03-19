#!/bin/bash

# SSE 性能测试脚本（通用版）
# 测量从发送请求到收到第一条 SSE 数据的时间

SCRIPT_NAME=$1
URL=$2
AUTHORIZATION=$3
CONVERSATION_ID=$4

if [ -z "$SCRIPT_NAME" ] || [ -z "$URL" ] || [ -z "$AUTHORIZATION" ] || [ -z "$CONVERSATION_ID" ]; then
    echo "用法: $0 <测试名称> <URL> <Authorization> <ConversationID>"
    exit 1
fi

echo "=== $SCRIPT_NAME SSE 性能测试 ==="
echo ""

# 测试数据 - 7轮对话历史
REQUEST_DATA='{
  "conversation_id": "'$CONVERSATION_ID'",
  "messages": [
    {"content":"你好！ 我是你的助理，有什么可以帮到你的吗？","id":"0391398c-7f83-4ee4-821a-aff162dd29d2","role":"assistant"},
    {"content":"在建（构）筑物下、水体下、铁路下及主要井巷煤柱开采中，需要遵守哪些具体规定？","doc_ids":[],"id":"test-query","role":"user"},
    {"content":"在建（构）筑物下、水体下、铁路下及主要井巷煤柱开采中，必须设立观测站，观测地表和岩层移动与变形，查明垮落带和导水裂缝带的高度，以及水文地质条件变化等情况。取得的实际资料作为本井田建（构）筑物下、水体下、铁路下的以及主要井巷煤柱开采的依据。[ID:2]\n\n必须经过试采。试采前，必须按其重要程度以及可能受到的影响，采取相应技术措施并编制开采设计。试采前，还必须完成建(构)筑物、水体、铁路，主要井巷工程及其地质、水文地质调查，观测点设置以及加固和保护等准备工作；试采时，必须及时观测，对受到开采影响的受护体，必须及时维修。试采结束后，必须由原试采方案设计单位提出试采总结报告。[ID:3]\n\n受水淹区积水威胁的区域，必须在排除积水、消除威胁后方可进行采掘作业。如果无法排除积水，开采倾斜、缓倾斜煤层的，必须按照《建筑物、水体、铁路及主要井巷煤柱留设与压煤开采规程》中有关水体下开采的规定，编制专项开采设计，由煤矿企业主要负责人审批后，方可进行。严禁开采地表水体、强含水层、采空区水淹区域下且水患威胁未消除的急倾斜煤层。[ID:4]","created_at":1763107685.596125,"id":"test-query","role":"assistant"},
    {"content":"在建（构）筑物下、水体下、铁路下及主要井巷煤柱开采中，需要遵守哪些具体规定","doc_ids":[],"id":"25cd8980-0bab-4dfa-9d55-c330c8b91462","role":"user"},
    {"content":"在建（构）筑物下、水体下、铁路下及主要井巷煤柱开采中，需要设立观测站，观测地表和岩层移动与变形，查明垮落带和导水裂缝带的高度，以及水文地质条件变化等情况。[ID:2]必须按其重要程度以及可能受到的影响，采取相应技术措施并编制开采设计，进行试采。[ID:3]试采前，需要完成建（构）筑物、水体、铁路，主要井巷工程及其地质、水文地质调查，观测点设置以及加固和保护等准备工作。[ID:3]在开采过程中，若遇到受水淹区积水威胁的区域，必须在排除积水、消除威胁后才可以进行采掘作业；如无法排除积水，则需要依据特殊规定，编制专项开采设计并获得审批后，方可进行开采。严禁在无法排除水患的条件下开采急倾斜煤层。[ID:4]","created_at":1763108334.134903,"id":"25cd8980-0bab-4dfa-9d55-c330c8b91462","role":"assistant"},
    {"content":"在建（构）筑物下、水体下、铁路下及主要井巷煤柱开采中，需要遵守哪些具体规定","doc_ids":[],"id":"a6772d98-cdbb-4963-8fbe-839fdaded075","role":"user"},
    {"content":"在建（构）筑物下、水体下、铁路下及主要井巷煤柱开采中，需要遵守的具体规定如下：\n\n1. 必须设立观测站，观测地表和岩层移动与变形，查明垮落带和导水裂缝带的高度，以及水文地质条件变化等情况，这些实际资料作为本井田建（构）筑物下、水体下、铁路下的以及主要井巷煤柱开采的依据。[ID:2]\n\n2. 建（构）筑物下、水体下、铁路下以及主要井巷煤柱开采，必须经过试采。试采前，必须按其重要程度以及可能受到的影响，采取相应技术措施并编制开采设计。[ID:3]\n\n3. 试采前，必须完成建(构)筑物、水体、铁路、主要井巷工程及其地质、水文地质调查，观测点设置以及加固和保护等准备工作；试采时，必须及时观测，对受到开采影响的受护体，必须及时维修。试采结束后，还必须由原试采方案设计单位提出试采总结报告。[ID:3]\n\n4. 受水淹区积水威胁的区域，必须在排除积水、消除威胁后方可进行采掘作业。如果无法排除积水，开采倾斜、缓倾斜煤层的，必须按照《建筑物、水体、铁路及主要井巷煤柱留设与压煤开采规程》中有关水体下开采的规定，编制专项开采设计，由煤矿企业主要负责人审批后，方可进行。严禁开采地表水体、强含水层、采空区水淹区域下且水患威胁未消除的急倾斜煤层。[ID:4]","created_at":1763108874.420225,"id":"a6772d98-cdbb-4963-8fbe-839fdaded075","role":"assistant"},
    {"id":"9c74fa53-0b1b-4e80-9da7-04a36ebeb5ac","content":"在建（构）筑物下、水体下、铁路下及主要井巷煤柱开采中，需要遵守哪些具体规定","role":"user","doc_ids":[]}
  ]
}'

# 创建临时目录
TEMP_DIR="/tmp/sse_perf_${SCRIPT_NAME}"
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

echo "开始测试 50 个请求..."
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
START_TIME=$(date +%s.%N)

# 并发发送 50 个请求
for i in {1..50}; do
  {
    # 记录请求开始时间
    REQUEST_START=$(date +%s.%N)

    # 发送请求并获取 SSE 流，只读取第一条数据
    # 使用 curl 的 --max-time 设置超时（60秒）
    # 使用 || true 防止 head 导致的 SIGPIPE 错误
    FIRST_DATA=$(curl -s -N --max-time 60 \
      -X POST "$URL" \
      -H "Authorization: $AUTHORIZATION" \
      -H "Content-Type: application/json" \
      --data-raw "$REQUEST_DATA" 2>&1 | head -n 1 || true)

    # 记录收到第一条数据的时间
    REQUEST_END=$(date +%s.%N)

    # 计算时间差
    TIME_TO_FIRST_DATA=$(echo "$REQUEST_END - $REQUEST_START" | bc)

    # 检查是否成功收到数据（检查是否包含 "data:" 字符串）
    if echo "$FIRST_DATA" | grep -q "data:"; then
      echo "$i,$TIME_TO_FIRST_DATA,success" >> "$TEMP_DIR/results.csv"
      echo "请求 $i 完成 (首次响应耗时: ${TIME_TO_FIRST_DATA}s)"
    else
      echo "$i,$TIME_TO_FIRST_DATA,failed" >> "$TEMP_DIR/results.csv"
      echo "请求 $i 失败 (耗时: ${TIME_TO_FIRST_DATA}s)"
    fi
  } &
done

# 等待所有请求完成
wait

END_TIME=$(date +%s.%N)
echo ""
echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"

# 计算总耗时
TOTAL_TIME=$(echo "$END_TIME - $START_TIME" | bc)

# 计算 QPS
QPS=$(echo "scale=2; 50 / $TOTAL_TIME" | bc)

echo ""
echo "=== 测试结果 ==="
echo "总请求数: 50"
echo "总耗时: ${TOTAL_TIME}s"
echo "QPS: $QPS 请求/秒"
echo ""

# 分析请求耗时
if [ -f "$TEMP_DIR/results.csv" ]; then
    echo "=== 请求耗时统计 ==="

    # 统计成功和失败
    SUCCESS_COUNT=$(grep -c "success" "$TEMP_DIR/results.csv")
    FAILED_COUNT=$(grep -c "failed" "$TEMP_DIR/results.csv")
    echo "成功请求: $SUCCESS_COUNT"
    echo "失败请求: $FAILED_COUNT"
    echo ""

    # 只统计成功的请求
    AVG_TIME=$(awk -F',' '/success/ {sum+=$2; count++} END {if(count>0) printf "%.3f", sum/count; else print "N/A"}' "$TEMP_DIR/results.csv")
    echo "平均首次响应时间: ${AVG_TIME}s"

    MIN_TIME=$(awk -F',' '/success/ {if(NR==1 || $2<min) min=$2} END {if(min) printf "%.3f", min; else print "N/A"}' "$TEMP_DIR/results.csv")
    MAX_TIME=$(awk -F',' '/success/ {if($2>max) max=$2} END {if(max) printf "%.3f", max; else print "N/A"}' "$TEMP_DIR/results.csv")
    echo "最小首次响应时间: ${MIN_TIME}s"
    echo "最大首次响应时间: ${MAX_TIME}s"

    P95_TIME=$(awk -F',' '/success/ {print $2}' "$TEMP_DIR/results.csv" | sort -n | awk 'BEGIN{c=0} {total[c]=$1; c++} END{if(c>0) print total[int(c*0.95)]; else print "N/A"}')
    echo "P95 首次响应时间: ${P95_TIME}s"
fi

echo ""
echo "详细结果保存在: $TEMP_DIR/results.csv"
echo ""
echo "测试完成！"
