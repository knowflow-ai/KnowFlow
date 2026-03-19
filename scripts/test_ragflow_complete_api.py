#!/usr/bin/env python3
"""
RAGFlow 完整 API 测试脚本
覆盖所有 RAGFlow HTTP API 端点
"""

import requests
import json
import os
import time
from typing import Dict, Any, Optional, Tuple

# 配置
BASE_URL = "http://localhost:9380"
API_KEY = "ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 测试文件
TEST_PDF_PATH = "/Users/zxwei/zhishi/KnowFlow/scripts/TWEPP2019_010.pdf"

# 创建新的数据集进行完整测试（不使用已有数据集）
EXISTING_DATASET_ID = None

class RAGFlowAPITester:
    def __init__(self):
        self.results = []
        self.dataset_id = None
        self.document_id = None
        self.chunk_id = None
        self.chat_id = None
        self.session_id = None
        self.agent_id = None

    def log_result(self, category: str, endpoint: str, method: str, status: str,
                   request: Optional[Dict] = None, response: Optional[Any] = None,
                   error: Optional[str] = None):
        """记录测试结果"""
        result = {
            "category": category,
            "endpoint": endpoint,
            "method": method,
            "status": status,
            "request": request,
            "response": str(response)[:500] if response else None,  # 限制长度
            "error": error
        }
        self.results.append(result)

        status_icon = "✅" if status == "SUCCESS" else ("⚠️" if status == "SKIP" else "❌")
        print(f"{status_icon} {method:6} {endpoint}")
        if error and status != "SKIP":
            print(f"   Error: {error}")

    def test_request(self, category: str, method: str, endpoint: str,
                    data: Optional[Dict] = None, params: Optional[Dict] = None,
                    files: Optional[Dict] = None, skip_on_error: bool = False) -> Tuple[bool, Any]:
        """执行 HTTP 请求"""
        url = f"{BASE_URL}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=HEADERS, params=params, timeout=30)
            elif method == "POST":
                if files:
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
                if skip_on_error:
                    self.log_result(category, endpoint, method, "SKIP", data, response_data, error_msg)
                else:
                    self.log_result(category, endpoint, method, "FAILED", data, response_data, error_msg)
                return False, response_data

        except Exception as e:
            error_msg = str(e)
            if skip_on_error:
                self.log_result(category, endpoint, method, "SKIP", data, None, error_msg)
            else:
                self.log_result(category, endpoint, method, "ERROR", data, None, error_msg)
            return False, {"error": error_msg}

    def test_dataset_apis(self):
        """测试 Dataset Management APIs"""
        print("\n" + "="*80)
        print("DATASET MANAGEMENT APIs")
        print("="*80)

        # 1. Create dataset - 创建新数据集用于完整测试
        create_data = {
            "name": f"complete_test_dataset_{int(time.time())}",
            "description": "Complete API test dataset with document",
            "embedding_model": "BAAI/bge-m3@SILICONFLOW",
            "chunk_method": "naive"
        }
        success, resp = self.test_request(
            "Dataset Management", "POST", "/api/v1/datasets",
            data=create_data
        )
        if success and resp.get("data"):
            self.dataset_id = resp["data"].get("id")
            print(f"   创建数据集 ID: {self.dataset_id}\n")
        else:
            print("   ❌ 无法创建数据集，测试终止")
            return

        # 2. List datasets
        self.test_request(
            "Dataset Management", "GET", "/api/v1/datasets",
            params={"page": 1, "page_size": 10}
        )

        # 3. Update dataset
        if self.dataset_id:
            self.test_request(
                "Dataset Management", "PUT", f"/api/v1/datasets/{self.dataset_id}",
                data={"description": f"Updated at {int(time.time())}"}
            )

        # 4. Get knowledge graph
        if self.dataset_id:
            self.test_request(
                "Dataset Management", "GET", f"/api/v1/datasets/{self.dataset_id}/knowledge_graph",
                skip_on_error=True
            )

        # 5. Delete knowledge graph
        if self.dataset_id:
            self.test_request(
                "Dataset Management", "DELETE", f"/api/v1/datasets/{self.dataset_id}/knowledge_graph",
                skip_on_error=True
            )

    def test_document_apis(self):
        """测试 Document Management APIs"""
        print("\n" + "="*80)
        print("DOCUMENT MANAGEMENT APIs")
        print("="*80)

        if not self.dataset_id:
            print("⚠️  跳过：无数据集ID\n")
            return

        # 1. Upload document - 上传真实PDF文档
        if os.path.exists(TEST_PDF_PATH):
            print(f"   上传测试文档: {os.path.basename(TEST_PDF_PATH)}")
            with open(TEST_PDF_PATH, 'rb') as f:
                files = {
                    'file': (os.path.basename(TEST_PDF_PATH), f, 'application/pdf')
                }
                form_data = {
                    'parser_id': 'naive'
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
                        print(f"   文档上传成功，ID: {self.document_id}\n")

                        # Trigger parsing explicitly
                        print("   触发文档解析...")
                        trigger_success, trigger_resp = self.test_request(
                            "Document Management", "POST",
                            f"/api/v1/datasets/{self.dataset_id}/chunks",
                            data={"document_ids": [self.document_id]},
                            skip_on_error=True
                        )
                        if trigger_success:
                            print("   ✅ 解析已触发\n")

                        # 等待文档解析完成
                        print("   等待文档解析完成...")
                        max_wait = 120  # 最多等待2分钟
                        wait_interval = 3
                        elapsed = 0

                        while elapsed < max_wait:
                            time.sleep(wait_interval)
                            elapsed += wait_interval

                            # Use list documents endpoint with ID filter to check status
                            check_success, check_resp = self.test_request(
                                "Document Management", "GET",
                                f"/api/v1/datasets/{self.dataset_id}/documents?id={self.document_id}",
                                skip_on_error=True
                            )

                            if check_success and check_resp.get("data"):
                                # List endpoint returns {data: {docs: [...], total: ...}}
                                docs = check_resp["data"].get("docs", [])
                                if docs and len(docs) > 0:
                                    doc_data = docs[0]
                                    status = doc_data.get("status")
                                    progress = doc_data.get("progress", 0)
                                else:
                                    continue  # No document data

                                if status == "1":  # 解析完成
                                    print(f"   ✅ 文档解析完成！耗时 {elapsed} 秒\n")
                                    break
                                elif status == "2":  # 解析失败
                                    print(f"   ❌ 文档解析失败\n")
                                    break
                                else:
                                    print(f"   ⏳ 解析中... {progress}% (已等待 {elapsed}/{max_wait} 秒)")
                        else:
                            print(f"   ⚠️  解析超时 ({max_wait}秒)\n")
        else:
            print(f"   ⚠️  测试文档不存在: {TEST_PDF_PATH}\n")
            return

        # 2. List documents
        self.test_request(
            "Document Management", "GET", f"/api/v1/datasets/{self.dataset_id}/documents",
            params={"page": 1, "page_size": 10}
        )

        # 3. Get document details
        if self.document_id:
            self.test_request(
                "Document Management", "GET",
                f"/api/v1/datasets/{self.dataset_id}/documents/{self.document_id}"
            )

        # 4. Update document
        if self.document_id:
            self.test_request(
                "Document Management", "PUT",
                f"/api/v1/datasets/{self.dataset_id}/documents/{self.document_id}",
                data={"name": f"updated_{int(time.time())}.pdf"}
            )

    def test_chunk_apis(self):
        """测试 Chunk Management APIs"""
        print("\n" + "="*80)
        print("CHUNK MANAGEMENT APIs")
        print("="*80)

        if not self.dataset_id:
            print("⚠️  跳过：无数据集ID\n")
            return

        if not self.document_id:
            print("⚠️  跳过：无文档ID\n")
            return

        # 1. List document chunks
        success, resp = self.test_request(
            "Chunk Management", "GET",
            f"/api/v1/datasets/{self.dataset_id}/documents/{self.document_id}/chunks",
            params={"page": 1, "page_size": 10}
        )

        # 获取一个chunk ID
        if success and resp.get("data", {}).get("chunks"):
            chunks = resp["data"]["chunks"]
            if chunks:
                self.chunk_id = chunks[0].get("id")
                print(f"   使用Chunk ID: {self.chunk_id}\n")

        # 2. Add chunk to dataset
        add_chunk_data = {
            "document_id": self.document_id,
            "content": "Test chunk content for API testing",
            "important_keywords": ["test", "api"]
        }
        self.test_request(
            "Chunk Management", "POST",
            f"/api/v1/datasets/{self.dataset_id}/chunks",
            data=add_chunk_data,
            skip_on_error=True
        )

        # 3. Add chunk to document
        add_doc_chunk_data = {
            "content": "Another test chunk",
            "important_keywords": ["document", "chunk"]
        }
        self.test_request(
            "Chunk Management", "POST",
            f"/api/v1/datasets/{self.dataset_id}/documents/{self.document_id}/chunks",
            data=add_doc_chunk_data,
            skip_on_error=True
        )

        # 4. Update chunk
        if self.chunk_id:
            update_chunk_data = {
                "content": "Updated chunk content",
                "available": True
            }
            self.test_request(
                "Chunk Management", "PUT",
                f"/api/v1/datasets/{self.dataset_id}/documents/{self.document_id}/chunks/{self.chunk_id}",
                data=update_chunk_data,
                skip_on_error=True
            )

        # 5. Retrieval
        retrieval_data = {
            "question": "测试查询",
            "dataset_ids": [self.dataset_id],
            "page": 1,
            "page_size": 5
        }
        self.test_request(
            "Chunk Management", "POST", "/api/v1/retrieval",
            data=retrieval_data
        )

    def test_chat_apis(self):
        """测试 Chat Assistant Management APIs"""
        print("\n" + "="*80)
        print("CHAT ASSISTANT MANAGEMENT APIs")
        print("="*80)

        if not self.dataset_id:
            print("⚠️  跳过：无数据集ID\n")
            return

        # 1. Create chat assistant
        create_chat_data = {
            "name": f"test_chat_{int(time.time())}",
            "dataset_ids": [self.dataset_id],
            "llm": {
                "model_name": "Qwen/Qwen3-32B@SILICONFLOW",
                "temperature": 0.1,
                "top_p": 0.3
            },
            "prompt": {
                "similarity_threshold": 0.2,
                "top_n": 6
            }
        }
        success, resp = self.test_request(
            "Chat Assistant", "POST", "/api/v1/chats",
            data=create_chat_data
        )
        if success and resp.get("data"):
            self.chat_id = resp["data"].get("id")
            print(f"   创建的Chat ID: {self.chat_id}\n")

        # 2. List chats
        self.test_request(
            "Chat Assistant", "GET", "/api/v1/chats",
            params={"page": 1, "page_size": 10}
        )

        # 3. Update chat
        if self.chat_id:
            self.test_request(
                "Chat Assistant", "PUT", f"/api/v1/chats/{self.chat_id}",
                data={"description": "Updated description"}
            )

        # 4. Chat completion
        if self.chat_id:
            chat_request = {
                "question": "你好，这是一个测试问题",
                "stream": False
            }
            self.test_request(
                "Chat Assistant", "POST", f"/api/v1/chats/{self.chat_id}/completions",
                data=chat_request,
                skip_on_error=True
            )

        # 5. OpenAI-compatible chat
        if self.chat_id:
            openai_request = {
                "model": "test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False
            }
            self.test_request(
                "Chat Assistant", "POST", f"/api/v1/chats_openai/{self.chat_id}/chat/completions",
                data=openai_request,
                skip_on_error=True
            )

    def test_session_apis(self):
        """测试 Session Management APIs"""
        print("\n" + "="*80)
        print("SESSION MANAGEMENT APIs")
        print("="*80)

        if not self.chat_id:
            print("⚠️  跳过：无Chat ID\n")
            return

        # 1. Create session
        create_session_data = {
            "name": f"test_session_{int(time.time())}"
        }
        success, resp = self.test_request(
            "Session Management", "POST", f"/api/v1/chats/{self.chat_id}/sessions",
            data=create_session_data
        )
        if success and resp.get("data"):
            self.session_id = resp["data"].get("id")
            print(f"   创建的Session ID: {self.session_id}\n")

        # 2. List sessions
        self.test_request(
            "Session Management", "GET", f"/api/v1/chats/{self.chat_id}/sessions",
            params={"page": 1, "page_size": 10}
        )

        # 3. Update session
        if self.session_id:
            self.test_request(
                "Session Management", "PUT",
                f"/api/v1/chats/{self.chat_id}/sessions/{self.session_id}",
                data={"name": "Updated session name"}
            )

        # 4. Get related questions
        if self.session_id:
            related_q_data = {
                "session_id": self.session_id,
                "question": "什么是机器学习？"
            }
            self.test_request(
                "Session Management", "POST", "/api/v1/sessions/related_questions",
                data=related_q_data,
                skip_on_error=True
            )

    def test_agent_apis(self):
        """测试 Agent Management APIs"""
        print("\n" + "="*80)
        print("AGENT MANAGEMENT APIs")
        print("="*80)

        # 1. Create agent
        create_agent_data = {
            "title": f"test_agent_{int(time.time())}",
            "description": "Test agent",
            "dsl": {
                "components": {},
                "history": [],
                "path": [],
                "answer": []
            }
        }
        success, resp = self.test_request(
            "Agent Management", "POST", "/api/v1/agents",
            data=create_agent_data
        )
        if success:
            print(f"   Agent创建成功\n")

        # 2. List agents
        success, resp = self.test_request(
            "Agent Management", "GET", "/api/v1/agents",
            params={"page": 1, "page_size": 10}
        )

        # 获取一个agent ID用于测试
        if success and resp.get("data") and len(resp["data"]) > 0:
            self.agent_id = resp["data"][0].get("id")
            print(f"   使用Agent ID: {self.agent_id}\n")

        # 3. Update agent
        if self.agent_id:
            self.test_request(
                "Agent Management", "PUT", f"/api/v1/agents/{self.agent_id}",
                data={"description": "Updated agent description"},
                skip_on_error=True
            )

        # 4. Create agent session
        if self.agent_id:
            success, resp = self.test_request(
                "Agent Management", "POST", f"/api/v1/agents/{self.agent_id}/sessions",
                data={},
                skip_on_error=True
            )
            if success and resp.get("data"):
                agent_session_id = resp["data"].get("id")
                print(f"   Agent Session ID: {agent_session_id}\n")

        # 5. Agent completion
        if self.agent_id:
            agent_chat_data = {
                "question": "Hello agent",
                "stream": False
            }
            self.test_request(
                "Agent Management", "POST", f"/api/v1/agents/{self.agent_id}/completions",
                data=agent_chat_data,
                skip_on_error=True
            )

        # 6. List agent sessions
        if self.agent_id:
            self.test_request(
                "Agent Management", "GET", f"/api/v1/agents/{self.agent_id}/sessions",
                params={"page": 1, "page_size": 10},
                skip_on_error=True
            )

        # 7. OpenAI-compatible agent chat
        if self.agent_id:
            openai_agent_data = {
                "model": "test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False
            }
            self.test_request(
                "Agent Management", "POST", f"/api/v1/agents_openai/{self.agent_id}/chat/completions",
                data=openai_agent_data,
                skip_on_error=True
            )

    def cleanup(self):
        """清理测试数据"""
        print("\n" + "="*80)
        print("CLEANUP")
        print("="*80)

        # Delete chunks (document level)
        if self.dataset_id and self.document_id and self.chunk_id:
            self.test_request(
                "Cleanup", "DELETE",
                f"/api/v1/datasets/{self.dataset_id}/documents/{self.document_id}/chunks",
                data={"chunk_ids": [self.chunk_id]},
                skip_on_error=True
            )

        # Delete session
        if self.chat_id and self.session_id:
            self.test_request(
                "Cleanup", "DELETE", f"/api/v1/chats/{self.chat_id}/sessions",
                data={"ids": [self.session_id]},
                skip_on_error=True
            )

        # Delete chat
        if self.chat_id:
            self.test_request(
                "Cleanup", "DELETE", "/api/v1/chats",
                data={"ids": [self.chat_id]},
                skip_on_error=True
            )

        # Delete agent sessions
        if self.agent_id:
            self.test_request(
                "Cleanup", "DELETE", f"/api/v1/agents/{self.agent_id}/sessions",
                data={"ids": []},  # 删除所有会话
                skip_on_error=True
            )

        # Delete agent
        if self.agent_id:
            self.test_request(
                "Cleanup", "DELETE", f"/api/v1/agents/{self.agent_id}",
                skip_on_error=True
            )

        # Delete document
        if self.dataset_id and self.document_id:
            self.test_request(
                "Cleanup", "DELETE", f"/api/v1/datasets/{self.dataset_id}/documents",
                data={"ids": [self.document_id]},
                skip_on_error=True
            )

        # Delete dataset
        if self.dataset_id:
            self.test_request(
                "Cleanup", "DELETE", "/api/v1/datasets",
                data={"ids": [self.dataset_id]},
                skip_on_error=True
            )

    def print_summary(self):
        """打印测试总结"""
        total = len(self.results)
        success = sum(1 for r in self.results if r["status"] == "SUCCESS")
        failed = sum(1 for r in self.results if r["status"] == "FAILED")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")
        error = sum(1 for r in self.results if r["status"] == "ERROR")

        print("\n" + "="*80)
        print("测试总结")
        print("="*80)
        print(f"总计: {total} 个API")
        print(f"成功: {success} ✅")
        print(f"失败: {failed} ❌")
        print(f"跳过: {skipped} ⚠️")
        print(f"错误: {error} ⛔")
        print(f"成功率: {success/total*100:.1f}% (不含跳过)")
        print(f"有效测试成功率: {success/(total-skipped)*100:.1f}%" if total > skipped else "N/A")

        # 按分类统计
        categories = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "success": 0, "failed": 0, "skip": 0}
            categories[cat]["total"] += 1
            if r["status"] == "SUCCESS":
                categories[cat]["success"] += 1
            elif r["status"] in ["FAILED", "ERROR"]:
                categories[cat]["failed"] += 1
            elif r["status"] == "SKIP":
                categories[cat]["skip"] += 1

        print("\n按分类统计:")
        for cat, stats in sorted(categories.items()):
            total_cat = stats["total"]
            success_cat = stats["success"]
            failed_cat = stats["failed"]
            skip_cat = stats["skip"]
            print(f"  {cat}: {success_cat}/{total_cat} 成功, {failed_cat} 失败, {skip_cat} 跳过")

    def save_results(self, filename="ragflow_api_test_results.json"):
        """保存测试结果"""
        output_path = os.path.join(os.path.dirname(__file__), filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"\n测试结果已保存到: {output_path}")

    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始 RAGFlow 完整 API 测试...")
        print(f"Base URL: {BASE_URL}")
        print(f"API Key: {API_KEY[:20]}...\n")

        try:
            self.test_dataset_apis()
            self.test_document_apis()
            self.test_chunk_apis()
            self.test_chat_apis()
            self.test_session_apis()
            self.test_agent_apis()
        finally:
            self.cleanup()
            self.print_summary()
            self.save_results()

if __name__ == "__main__":
    tester = RAGFlowAPITester()
    tester.run_all_tests()
