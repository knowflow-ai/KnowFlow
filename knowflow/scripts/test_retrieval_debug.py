#!/usr/bin/env python3
import requests
import json

url = "http://127.0.0.1:9380/api/v1/dify/retrieval"
headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ragflow-FlYjZhYjk2YjNhNzExZjBiZDFjNjZmYz'
}

# 使用具体的查询词
queries = [
    "微短剧",
    "致密气",
    "地震",
    "人工智能",
    "测井"
]

for query in queries:
    payload = {
        'knowledge_id': 'e17360bab0f111f098f866fc51ac58df',
        'query': query,
        'retrieval_setting': {
            'top_k': 3,
            'score_threshold': 0.01  # 降低阈值
        }
    }
    
    print(f"\n查询: {query}")
    print("=" * 60)
    
    response = requests.post(url, json=payload, headers=headers)
    result = response.json()
    
    if 'records' in result and len(result['records']) > 0:
        print(f"找到 {len(result['records'])} 条结果:")
        for i, record in enumerate(result['records'], 1):
            print(f"\n  #{i} {record['title']}")
            print(f"     分数: {record['score']:.4f}")
            print(f"     内容: {record['content'][:100]}...")
    else:
        print("❌ 未找到结果")
        print(f"   响应: {json.dumps(result, ensure_ascii=False)}")
