#!/usr/bin/env python3
"""
KnowFlow API 测试脚本
用于验证所有 API 端点并生成文档数据
"""

import requests
import json
import os
import time
from typing import Dict, Any, Optional

# 配置
BASE_URL = "http://localhost:9380"
API_KEY = "ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 测试数据
test_dataset_name = f"test_dataset_{int(time.time())}"
test_doc_path = "/Users/zxwei/zhishi/KnowFlow/test_files/sample.pdf"  # 需要准备测试文件

# 可选：使用已有的知识库和文档进行测试（如果为 None，则创建新的）
EXISTING_DATASET_ID = "4345aa0ea1a311f0b45566fc51ac58df"  # 使用数据库中已有的知识库
EXISTING_DOCUMENT_ID = "c6db195ea4b811f097ee66fc51ac58df"  # 使用数据库中已有的文档

class APITester:
    def __init__(self):
        self.results = []
        self.dataset_id = None
        self.document_id = None
        self.chunk_id = None

    def log_result(self, category: str, endpoint: str, method: str, status: str,
                   request: Optional[Dict] = None, response: Optional[Dict] = None, error: Optional[str] = None):
        """记录测试结果"""
        result = {
            "category": category,
            "endpoint": endpoint,
            "method": method,
            "status": status,
            "request": request,
            "response": response,
            "error": error
        }
        self.results.append(result)

        status_icon = "✅" if status == "SUCCESS" else "❌"
        print(f"{status_icon} {method} {endpoint} - {status}")
        if error:
            print(f"   Error: {error}")

    def test_request(self, category: str, method: str, endpoint: str,
                    data: Optional[Dict] = None, params: Optional[Dict] = None,
                    files: Optional[Dict] = None) -> tuple:
        """执行 HTTP 请求并记录结果"""
        url = f"{BASE_URL}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=HEADERS, params=params, timeout=30)
            elif method == "POST":
                if files:
                    # 文件上传不使用 JSON headers
                    headers = {"Authorization": HEADERS["Authorization"]}
                    response = requests.post(url, headers=headers, data=data, files=files, timeout=60)
                else:
                    response = requests.post(url, headers=HEADERS, json=data, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=HEADERS, json=data, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=HEADERS, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response_data = response.json() if response.text else {}

            if response.status_code < 400 and response_data.get("code") == 0:
                self.log_result(category, endpoint, method, "SUCCESS", data, response_data)
                return True, response_data
            else:
                error_msg = response_data.get("message", response.text[:200])
                self.log_result(category, endpoint, method, "FAILED", data, response_data, error_msg)
                return False, response_data

        except Exception as e:
            self.log_result(category, endpoint, method, "ERROR", data, None, str(e))
            return False, {"error": str(e)}

    def test_dataset_apis(self):
        """测试知识库相关 API"""
        print("\n" + "="*60)
        print("测试知识库 (Dataset) API")
        print("="*60)

        # 使用已有的知识库或创建新的
        if EXISTING_DATASET_ID:
            self.dataset_id = EXISTING_DATASET_ID
            print(f"   使用已有知识库 ID: {self.dataset_id}")
        else:
            # 1. 创建知识库 (使用数据库中真实的配置)
            create_data = {
                "name": test_dataset_name,
                "description": "API 测试知识库",
                "embedding_model": "BAAI/bge-m3@SILICONFLOW",  # 使用数据库中的真实 embedding model
                "chunk_method": "smart",  # 使用智能分块方法
                "parser_config": {
                    "layout_recognize": "mineru",  # 使用 MinerU 布局解析器
                    "chunk_token_num": 256
                }
            }
            success, resp = self.test_request(
                "Dataset Management", "POST", "/api/v1/datasets",
                data=create_data
            )

            if success and resp.get("data"):
                self.dataset_id = resp["data"].get("id")
                print(f"   Created dataset ID: {self.dataset_id}")

        # 2. 列出知识库
        self.test_request(
            "Dataset Management", "GET", "/api/v1/datasets",
            params={"page": 1, "page_size": 10}
        )

        # 3. 更新知识库
        if self.dataset_id:
            update_data = {
                "description": "更新后的描述"
            }
            self.test_request(
                "Dataset Management", "PUT", f"/api/v1/datasets/{self.dataset_id}",
                data=update_data
            )

        # 4. 获取单个知识库
        if self.dataset_id:
            self.test_request(
                "Dataset Management", "GET", "/api/v1/datasets",
                params={"id": self.dataset_id}
            )

    def test_document_apis(self):
        """测试文档相关 API"""
        if not self.dataset_id:
            print("\n⚠️  跳过文档测试：没有可用的 dataset_id")
            return

        print("\n" + "="*60)
        print("测试文档 (Document) API")
        print("="*60)

        # 使用已有的文档或上传新的
        if EXISTING_DOCUMENT_ID:
            self.document_id = EXISTING_DOCUMENT_ID
            print(f"   使用已有文档 ID: {self.document_id}")
        elif os.path.exists(test_doc_path):
            # 1. 上传文档
            with open(test_doc_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(test_doc_path), f, 'application/pdf')
                }
                form_data = {
                    'parser_id': 'smart',  # 使用智能分块方法
                    'parser_config': json.dumps({
                        "chunk_token_num": 256,
                        "layout_recognize": "mineru"  # MinerU 布局解析器
                    })
                }

                success, resp = self.test_request(
                    "Document Management", "POST",
                    f"/api/v1/datasets/{self.dataset_id}/documents",
                    data=form_data, files=files
                )

                if success and resp.get("data"):
                    docs = resp["data"] if isinstance(resp["data"], list) else [resp["data"]]
                    if docs:
                        self.document_id = docs[0].get("id")
                        print(f"   Uploaded document ID: {self.document_id}")
        else:
            print(f"   ⚠️  测试文件不存在: {test_doc_path}")
            # 尝试使用文本创建文档
            create_doc_data = {
                "name": "test_doc.txt",
                "content": "这是一个测试文档内容",
                "parser_id": "smart"
            }
            success, resp = self.test_request(
                "Document Management", "POST",
                f"/api/v1/datasets/{self.dataset_id}/documents",
                data=create_doc_data
            )
            if success and resp.get("data"):
                self.document_id = resp["data"].get("id")

        # 2. 列出文档
        self.test_request(
            "Document Management", "GET",
            f"/api/v1/datasets/{self.dataset_id}/documents",
            params={"page": 1, "page_size": 10}
        )

        # 3. 获取单个文档
        if self.document_id:
            self.test_request(
                "Document Management", "GET",
                f"/api/v1/datasets/{self.dataset_id}/documents/{self.document_id}"
            )

        # 4. 更新文档
        if self.document_id:
            update_doc_data = {
                "name": "updated_name.pdf"
            }
            self.test_request(
                "Document Management", "PUT",
                f"/api/v1/datasets/{self.dataset_id}/documents/{self.document_id}",
                data=update_doc_data
            )

        # 如果是新上传的文档，等待解析完成
        if self.document_id and not EXISTING_DOCUMENT_ID:
            print("   等待文档解析...")
            for i in range(30):  # 最多等待30秒
                time.sleep(2)
                success, resp = self.test_request(
                    "Document Management", "GET",
                    f"/api/v1/datasets/{self.dataset_id}/documents/{self.document_id}",
                )
                if success and resp.get("data"):
                    status = resp["data"].get("status")
                    if status == "1":  # 解析完成
                        print(f"   文档解析完成")
                        break
                    elif status == "2":  # 解析失败
                        print(f"   文档解析失败")
                        break

    def test_chunk_apis(self):
        """测试分块相关 API"""
        if not self.dataset_id or not self.document_id:
            print("\n⚠️  跳过分块测试：没有可用的 dataset_id 或 document_id")
            return

        print("\n" + "="*60)
        print("测试分块 (Chunk) API")
        print("="*60)

        # 1. 列出文档的分块
        success, resp = self.test_request(
            "Chunk Management", "GET",
            f"/api/v1/datasets/{self.dataset_id}/documents/{self.document_id}/chunks",
            params={"page": 1, "page_size": 10}
        )

        if success and resp.get("data") and resp["data"].get("chunks"):
            chunks = resp["data"]["chunks"]
            if chunks:
                self.chunk_id = chunks[0].get("id")
                print(f"   Found chunk ID: {self.chunk_id}")

        # 2. 检索分块（使用 SDK API）
        retrieval_data = {
            "question": "测试查询内容",
            "dataset_ids": [self.dataset_id],  # SDK API 使用 dataset_ids
            "page": 1,
            "page_size": 5
        }
        self.test_request(
            "Chunk Management", "POST",
            "/api/v1/retrieval",
            data=retrieval_data
        )

    def test_cleanup(self):
        """清理测试数据"""
        print("\n" + "="*60)
        print("清理测试数据")
        print("="*60)

        # 删除文档
        if self.dataset_id and self.document_id:
            delete_doc_data = {
                "ids": [self.document_id]
            }
            self.test_request(
                "Document Management", "DELETE",
                f"/api/v1/datasets/{self.dataset_id}/documents",
                data=delete_doc_data
            )

        # 删除知识库
        if self.dataset_id:
            delete_dataset_data = {
                "ids": [self.dataset_id]
            }
            self.test_request(
                "Dataset Management", "DELETE",
                "/api/v1/datasets",
                data=delete_dataset_data
            )

    def save_results(self, filename="api_test_results.json"):
        """保存测试结果"""
        output_path = os.path.join(os.path.dirname(__file__), filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"\n测试结果已保存到: {output_path}")

    def print_summary(self):
        """打印测试总结"""
        total = len(self.results)
        success = sum(1 for r in self.results if r["status"] == "SUCCESS")
        failed = sum(1 for r in self.results if r["status"] in ["FAILED", "ERROR"])

        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        print(f"总计: {total} 个API")
        print(f"成功: {success} ✅")
        print(f"失败: {failed} ❌")
        print(f"成功率: {success/total*100:.1f}%")

    def run_all_tests(self):
        """运行所有测试"""
        print("\n🚀 开始 API 测试...")
        print(f"Base URL: {BASE_URL}")
        print(f"API Key: {API_KEY[:20]}...")

        try:
            self.test_dataset_apis()
            self.test_document_apis()
            self.test_chunk_apis()
        finally:
            # self.test_cleanup()  # 可以注释掉以保留测试数据检查
            self.print_summary()
            self.save_results()

if __name__ == "__main__":
    tester = APITester()
    tester.run_all_tests()
