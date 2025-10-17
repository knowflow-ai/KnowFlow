#!/usr/bin/env python3
"""
KnowFlow Server API 测试脚本
测试 KnowFlow Server 的所有 API 端点（排除 Permission Cache APIs）
"""

import requests
import json
import os
import time
from typing import Dict, Any, Optional, List

# 配置
KNOWFLOW_BASE_URL = "http://localhost:5000"
RAGFLOW_BASE_URL = "http://localhost:9380"
API_KEY = "ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh"

# 测试数据
TEST_USER_EMAIL = f"test_user_{int(time.time())}@test.com"
TEST_USER_PASSWORD = "Test@123456"
TEST_TEAM_NAME = f"test_team_{int(time.time())}"
TEST_KB_NAME = f"test_kb_{int(time.time())}"
TEST_PDF_PATH = "/Users/zxwei/zhishi/KnowFlow/test_files/sample.pdf"

# 使用已有的测试数据（避免重复创建）
EXISTING_USER_ID = "69736c5e723611efb51b0242ac120007"
EXISTING_KB_ID = "689df954aafa11f09a8966fc51ac58de"  # 全局知识库
EXISTING_DOC_ID = "c6db195ea4b811f097ee66fc51ac58df"


class KnowFlowAPITester:
    """KnowFlow Server API 测试器"""

    def __init__(self):
        self.results = []
        self.jwt_token = None
        self.created_user_id = None
        self.created_team_id = None
        self.created_kb_id = None
        self.created_doc_id = None
        self.uploaded_file_id = None

    def log_result(self, category: str, endpoint: str, method: str, status: str,
                   request: Optional[Dict] = None, response: Optional[Dict] = None,
                   error: Optional[str] = None):
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
                    files: Optional[Dict] = None, use_jwt: bool = False,
                    base_url: str = KNOWFLOW_BASE_URL,
                    expect_non_standard_response: bool = False) -> tuple:
        """执行 HTTP 请求并记录结果"""
        url = f"{base_url}{endpoint}"

        # 设置headers
        if use_jwt and self.jwt_token:
            headers = {
                "Authorization": self.jwt_token,
                "Content-Type": "application/json"
            }
        else:
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == "POST":
                if files:
                    # 文件上传不使用 JSON headers
                    headers.pop("Content-Type", None)
                    response = requests.post(url, headers=headers, data=data, files=files, timeout=60)
                else:
                    response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response_data = response.json() if response.text else {}

            # 判断成功的条件
            is_success = False
            if expect_non_standard_response:
                # RBAC API 等返回非标准格式的接口
                if response.status_code >= 400:
                    is_success = False
                elif isinstance(response_data, list):
                    # 返回列表的情况，认为是成功
                    is_success = True
                elif isinstance(response_data, dict):
                    # 返回字典的情况，检查多种成功标志
                    is_success = (
                        response_data.get("success") is True or  # {"success": true, ...}
                        response_data.get("status") == "healthy" or  # {"status": "healthy", ...}
                        ("data" in response_data and response_data.get("code") is None) or  # {"data": ..., ...} 但没有 code
                        ("error" not in response_data and "code" not in response_data)  # 没有 error 和 code 字段
                    )
                else:
                    is_success = False
            else:
                # 标准格式：{"code": 0, "data": {...}}
                is_success = response.status_code < 400 and response_data.get("code") == 0

            if is_success:
                self.log_result(category, endpoint, method, "SUCCESS", data, response_data)
                return True, response_data
            else:
                error_msg = response_data.get("message") or response_data.get("error") or response.text[:200]
                self.log_result(category, endpoint, method, "FAILED", data, response_data, error_msg)
                return False, response_data

        except Exception as e:
            self.log_result(category, endpoint, method, "ERROR", data, None, str(e))
            return False, {"error": str(e)}

    # ==================== 认证管理 APIs ====================

    def test_authentication_apis(self):
        """测试认证相关API"""
        print("\n" + "="*60)
        print("测试认证管理 APIs")
        print("="*60)

        # 1. 健康检查
        self.test_request(
            "Authentication", "GET", "/health"
        )

        # 2. RBAC系统状态检查
        self.test_request(
            "Authentication", "GET", "/api/v1/admin/rbac/status"
        )

        # 3. 登录（需要真实的用户名密码，这里使用默认管理员）
        # 注意：这个API可能需要特定的管理员账户

        print(f"\n   使用 API Key 进行后续测试")

    # ==================== 用户管理 APIs ====================

    def test_user_management_apis(self):
        """测试用户管理API"""
        print("\n" + "="*60)
        print("测试用户管理 APIs")
        print("="*60)

        # 1. 获取当前用户信息
        success, resp = self.test_request(
            "User Management", "GET", "/api/v1/users/me"
        )

        # 2. 获取用户列表
        self.test_request(
            "User Management", "GET", "/api/v1/users",
            params={"current_page": 1, "size": 10}
        )

        # 3. 获取可分配权限的用户列表
        self.test_request(
            "User Management", "GET", "/api/v1/users/assignable",
            params={"current_page": 1, "size": 10}
        )

        # 4. 创建用户
        create_user_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "nickname": "Test User",
            "status": "1"
        }
        success, resp = self.test_request(
            "User Management", "POST", "/api/v1/users",
            data=create_user_data
        )
        if success and resp.get("data"):
            self.created_user_id = resp["data"].get("id")
            if self.created_user_id:
                print(f"   Created user ID: {self.created_user_id}")

        # 如果创建失败，使用已有用户ID
        if not self.created_user_id:
            self.created_user_id = EXISTING_USER_ID
            print(f"   Using existing user ID: {self.created_user_id}")

        # 5. 更新用户信息
        if self.created_user_id:
            update_user_data = {
                "nickname": "Updated Test User"
            }
            self.test_request(
                "User Management", "PUT", f"/api/v1/users/{self.created_user_id}",
                data=update_user_data
            )

        # 6. 获取用户角色
        if self.created_user_id:
            self.test_request(
                "User Management", "GET", f"/api/v1/users/{self.created_user_id}/roles",
                params={"tenant_id": "default"}
            )

        # 7. 分配角色给用户
        if self.created_user_id:
            assign_role_data = {
                "role_code": "user",
                "tenant_id": "default"
            }
            self.test_request(
                "User Management", "POST", f"/api/v1/users/{self.created_user_id}/roles",
                data=assign_role_data
            )

        # 8. 获取用户权限
        if self.created_user_id:
            self.test_request(
                "User Management", "GET", f"/api/v1/users/{self.created_user_id}/permissions",
                params={"tenant_id": "default"}
            )

        # 9. 重置用户密码（仅测试，不实际重置）
        # 跳过以避免影响测试用户

        # 10. 撤销用户角色
        if self.created_user_id:
            self.test_request(
                "User Management", "DELETE", f"/api/v1/users/{self.created_user_id}/roles/user",
                params={"tenant_id": "default"}
            )

    # ==================== 团队管理 APIs ====================

    def test_team_management_apis(self):
        """测试团队管理API"""
        print("\n" + "="*60)
        print("测试团队管理 APIs")
        print("="*60)

        # 1. 创建团队
        create_team_data = {
            "name": TEST_TEAM_NAME,
            "description": "Test team for API testing"
        }
        success, resp = self.test_request(
            "Team Management", "POST", "/api/v1/teams",
            data=create_team_data
        )
        if success and resp.get("data"):
            self.created_team_id = resp["data"].get("id")
            if self.created_team_id:
                print(f"   Created team ID: {self.created_team_id}")

        # 2. 获取团队列表
        self.test_request(
            "Team Management", "GET", "/api/v1/teams",
            params={"current_page": 1, "size": 10}
        )

        # 3. 获取团队详情
        if self.created_team_id:
            self.test_request(
                "Team Management", "GET", f"/api/v1/teams/{self.created_team_id}"
            )

        # 4. 更新团队信息
        if self.created_team_id:
            update_team_data = {
                "name": f"{TEST_TEAM_NAME}_updated",
                "description": "Updated description"
            }
            self.test_request(
                "Team Management", "PUT", f"/api/v1/teams/{self.created_team_id}",
                data=update_team_data
            )

        # 5. 获取团队成员
        if self.created_team_id:
            self.test_request(
                "Team Management", "GET", f"/api/v1/teams/{self.created_team_id}/members"
            )

        # 6. 添加团队成员
        if self.created_team_id and self.created_user_id:
            add_member_data = {
                "user_id": self.created_user_id,
                "role": "member"
            }
            self.test_request(
                "Team Management", "POST", f"/api/v1/teams/{self.created_team_id}/members",
                data=add_member_data
            )

        # 7. 获取团队角色
        if self.created_team_id:
            self.test_request(
                "Team Management", "GET", f"/api/v1/teams/{self.created_team_id}/roles"
            )

        # 8. 分配团队角色
        if self.created_team_id:
            assign_role_data = {
                "role_code": "editor",
                "resource_type": "knowledgebase",
                "resource_id": EXISTING_KB_ID
            }
            self.test_request(
                "Team Management", "POST", f"/api/v1/teams/{self.created_team_id}/roles",
                data=assign_role_data
            )

        # 9. 删除团队成员
        if self.created_team_id and self.created_user_id:
            self.test_request(
                "Team Management", "DELETE",
                f"/api/v1/teams/{self.created_team_id}/members/{self.created_user_id}"
            )

    # ==================== 租户管理 APIs ====================

    def test_tenant_management_apis(self):
        """测试租户管理API"""
        print("\n" + "="*60)
        print("测试租户管理 APIs")
        print("="*60)

        # 1. 获取租户列表
        self.test_request(
            "Tenant Management", "GET", "/api/v1/tenants"
        )

        # 2. 获取模型列表
        self.test_request(
            "Tenant Management", "GET", "/api/v1/tenants/models"
        )

        # 3. 获取管理员默认设置
        self.test_request(
            "Tenant Management", "GET", "/api/v1/tenants/admin-defaults"
        )

        # 4. 更新租户（需要租户ID，跳过以避免影响现有配置）
        # self.test_request(
        #     "Tenant Management", "PUT", f"/api/v1/tenants/{tenant_id}",
        #     data={"setting": "value"}
        # )

    # ==================== 知识库管理 APIs ====================

    def test_knowledgebase_management_apis(self):
        """测试知识库管理API"""
        print("\n" + "="*60)
        print("测试知识库管理 APIs")
        print("="*60)

        # 1. 创建知识库
        create_kb_data = {
            "name": TEST_KB_NAME,
            "description": "Test KB for API testing",
            "embedding_model": "BAAI/bge-m3",
            "chunk_method": "smart",
            "parser_config": {
                "layout_recognize": "mineru",
                "chunk_token_num": 256
            }
        }
        success, resp = self.test_request(
            "Knowledgebase Management", "POST", "/api/v1/knowledgebases",
            data=create_kb_data
        )
        if success and resp.get("data"):
            self.created_kb_id = resp["data"].get("id")
            if self.created_kb_id:
                print(f"   Created KB ID: {self.created_kb_id}")

        # 如果创建失败，使用已有KB
        if not self.created_kb_id:
            self.created_kb_id = EXISTING_KB_ID
            print(f"   Using existing KB ID: {self.created_kb_id}")

        # 2. 获取知识库列表
        self.test_request(
            "Knowledgebase Management", "GET", "/api/v1/knowledgebases",
            params={"current_page": 1, "size": 10}
        )

        # 3. 获取知识库详情
        if self.created_kb_id:
            self.test_request(
                "Knowledgebase Management", "GET", f"/api/v1/knowledgebases/{self.created_kb_id}"
            )

        # 4. 更新知识库
        if self.created_kb_id:
            update_kb_data = {
                "description": "Updated KB description"
            }
            self.test_request(
                "Knowledgebase Management", "PUT", f"/api/v1/knowledgebases/{self.created_kb_id}",
                data=update_kb_data
            )

        # 5. 获取知识库权限列表
        if self.created_kb_id:
            self.test_request(
                "Knowledgebase Management", "GET", f"/api/v1/knowledgebases/{self.created_kb_id}/permissions"
            )

        # 6. 为用户授予知识库权限
        if self.created_kb_id and self.created_user_id:
            grant_permission_data = {
                "user_id": self.created_user_id,
                "permission_level": "read"
            }
            self.test_request(
                "Knowledgebase Management", "POST",
                f"/api/v1/knowledgebases/{self.created_kb_id}/permissions/users",
                data=grant_permission_data
            )

        # 7. 检查用户权限
        if self.created_kb_id and self.created_user_id:
            check_permission_data = {
                "user_id": self.created_user_id,
                "permission_type": "read"
            }
            self.test_request(
                "Knowledgebase Management", "POST",
                f"/api/v1/knowledgebases/{self.created_kb_id}/permissions/check",
                data=check_permission_data
            )

        # 8. 获取知识库文档列表
        if self.created_kb_id:
            self.test_request(
                "Knowledgebase Management", "GET",
                f"/api/v1/knowledgebases/{self.created_kb_id}/documents",
                params={"current_page": 1, "size": 10}
            )

        # 9. 获取系统Embedding配置
        self.test_request(
            "Knowledgebase Management", "GET", "/api/v1/knowledgebases/system_embedding_config"
        )

        # 10. 撤销用户权限
        if self.created_kb_id and self.created_user_id:
            self.test_request(
                "Knowledgebase Management", "DELETE",
                f"/api/v1/knowledgebases/{self.created_kb_id}/permissions/users/{self.created_user_id}"
            )

    # ==================== 文件管理 APIs ====================

    def test_file_management_apis(self):
        """测试文件管理API"""
        print("\n" + "="*60)
        print("测试文件管理 APIs")
        print("="*60)

        # 1. 上传文件
        if os.path.exists(TEST_PDF_PATH):
            with open(TEST_PDF_PATH, 'rb') as f:
                files = {
                    'file': (os.path.basename(TEST_PDF_PATH), f, 'application/pdf')
                }
                success, resp = self.test_request(
                    "File Management", "POST", "/api/v1/files/upload",
                    files=files
                )
                if success and resp.get("data"):
                    files_list = resp["data"] if isinstance(resp["data"], list) else [resp["data"]]
                    if files_list:
                        self.uploaded_file_id = files_list[0].get("id")
                        print(f"   Uploaded file ID: {self.uploaded_file_id}")
        else:
            print(f"   ⚠️  测试文件不存在: {TEST_PDF_PATH}")

        # 2. 获取文件列表
        self.test_request(
            "File Management", "GET", "/api/v1/files",
            params={"current_page": 1, "size": 10}
        )

        # 3. 下载文件
        if self.uploaded_file_id:
            # 注意：下载API返回文件流，不是JSON
            # self.test_request(
            #     "File Management", "GET", f"/api/v1/files/{self.uploaded_file_id}/download"
            # )
            print(f"   ⏭️  跳过文件下载测试（返回文件流）")

    # ==================== 文档管理 APIs ====================

    def test_document_management_apis(self):
        """测试文档管理API"""
        print("\n" + "="*60)
        print("测试文档管理 APIs")
        print("="*60)

        # 使用已有文档ID
        doc_id = EXISTING_DOC_ID

        # 1. 获取文档分块配置
        self.test_request(
            "Document Management", "GET", f"/api/v1/documents/{doc_id}/chunking-config"
        )

        # 2. 更新文档分块配置
        update_config_data = {
            "chunking_config": {
                "strategy": "smart",
                "chunk_token_num": 512,
                "min_chunk_tokens": 20,
                "regex_pattern": ""
            }
        }
        self.test_request(
            "Document Management", "PUT", f"/api/v1/documents/{doc_id}/chunking-config",
            data=update_config_data
        )

    # ==================== RBAC权限管理 APIs ====================

    def test_rbac_management_apis(self):
        """测试RBAC权限管理API"""
        print("\n" + "="*60)
        print("测试RBAC权限管理 APIs")
        print("="*60)

        # 1. RBAC健康检查
        self.test_request(
            "RBAC Management", "GET", "/api/v1/rbac/health",
            expect_non_standard_response=True
        )

        # 2. 获取角色列表
        self.test_request(
            "RBAC Management", "GET", "/api/v1/rbac/roles",
            expect_non_standard_response=True
        )

        # 3. 获取可分配角色
        self.test_request(
            "RBAC Management", "GET", "/api/v1/rbac/assignable-roles",
            expect_non_standard_response=True
        )

        # 4. 获取我的角色
        self.test_request(
            "RBAC Management", "GET", "/api/v1/rbac/my/roles",
            expect_non_standard_response=True
        )

        # 5. 获取我的权限
        self.test_request(
            "RBAC Management", "GET", "/api/v1/rbac/my/permissions",
            expect_non_standard_response=True
        )

        # 6. 获取权限列表
        self.test_request(
            "RBAC Management", "GET", "/api/v1/rbac/permissions",
            expect_non_standard_response=True
        )

        # 7. 获取角色权限
        self.test_request(
            "RBAC Management", "GET", "/api/v1/rbac/roles/admin/permissions",
            expect_non_standard_response=True
        )

        # 8. 检查权限
        if self.created_user_id and self.created_kb_id:
            check_permission_data = {
                "user_id": self.created_user_id,
                "resource_type": "knowledgebase",
                "resource_id": self.created_kb_id,
                "permission_type": "read",
                "tenant_id": "default"
            }
            self.test_request(
                "RBAC Management", "POST", "/api/v1/rbac/permissions/check",
                data=check_permission_data,
                expect_non_standard_response=True
            )

        # 9. 批量检查权限
        if self.created_user_id and self.created_kb_id:
            batch_check_data = {
                "checks": [
                    {
                        "user_id": self.created_user_id,
                        "resource_type": "knowledgebase",
                        "resource_id": self.created_kb_id,
                        "permission_type": "read"
                    }
                ]
            }
            self.test_request(
                "RBAC Management", "POST", "/api/v1/rbac/permissions/batch-check",
                data=batch_check_data,
                expect_non_standard_response=True
            )

        # 10. 简单权限检查
        if self.created_user_id:
            simple_check_data = {
                "user_id": self.created_user_id,
                "permission_code": "kb:read"
            }
            self.test_request(
                "RBAC Management", "POST", "/api/v1/rbac/permissions/simple-check",
                data=simple_check_data,
                expect_non_standard_response=True
            )

        # 11. 获取用户角色（RBAC接口）
        if self.created_user_id:
            self.test_request(
                "RBAC Management", "GET", f"/api/v1/rbac/users/{self.created_user_id}/roles",
                expect_non_standard_response=True
            )

        # 12. 获取用户权限（RBAC接口）
        if self.created_user_id:
            self.test_request(
                "RBAC Management", "GET", f"/api/v1/rbac/users/{self.created_user_id}/permissions",
                expect_non_standard_response=True
            )

    # ==================== 文档解析服务 APIs ====================

    def test_parse_service_apis(self):
        """测试文档解析服务API"""
        print("\n" + "="*60)
        print("测试文档解析服务 APIs")
        print("="*60)

        if not os.path.exists(TEST_PDF_PATH):
            print(f"   ⚠️  测试文件不存在: {TEST_PDF_PATH}，跳过解析测试")
            return

        # 1. MinerU解析
        with open(TEST_PDF_PATH, 'rb') as f:
            files = {
                'file': (os.path.basename(TEST_PDF_PATH), f, 'application/pdf')
            }
            form_data = {
                'from_page': '0',
                'to_page': '5',
                'kb_id': self.created_kb_id or EXISTING_KB_ID
            }
            self.test_request(
                "Parse Service", "POST", "/api/parse/mineru",
                data=form_data, files=files
            )

        # 2. DOTS解析
        with open(TEST_PDF_PATH, 'rb') as f:
            files = {
                'file': (os.path.basename(TEST_PDF_PATH), f, 'application/pdf')
            }
            form_data = {
                'from_page': '0',
                'to_page': '5',
                'kb_id': self.created_kb_id or EXISTING_KB_ID
            }
            self.test_request(
                "Parse Service", "POST", "/api/parse/dots",
                data=form_data, files=files
            )

        # 3. 智能分块
        smart_chunk_data = {
            "markdown": "# Title\n\nThis is a paragraph.\n\n## Subtitle\n\nAnother paragraph.",
            "coordinate_map": {
                "0": [0, 100, 200, 50, 100],
                "2": [0, 100, 200, 150, 200]
            },
            "chunk_token_num": 256,
            "min_chunk_tokens": 10
        }
        self.test_request(
            "Parse Service", "POST", "/api/parse/smart_chunk",
            data=smart_chunk_data
        )

    # ==================== 清理测试数据 ====================

    def test_cleanup(self):
        """清理测试数据"""
        print("\n" + "="*60)
        print("清理测试数据")
        print("="*60)

        # 1. 删除上传的文件
        if self.uploaded_file_id:
            self.test_request(
                "File Management", "DELETE", f"/api/v1/files/{self.uploaded_file_id}"
            )

        # 2. 删除团队
        if self.created_team_id:
            self.test_request(
                "Team Management", "DELETE", f"/api/v1/teams/{self.created_team_id}"
            )

        # 3. 删除知识库（如果是测试创建的）
        if self.created_kb_id and self.created_kb_id != EXISTING_KB_ID:
            self.test_request(
                "Knowledgebase Management", "DELETE", f"/api/v1/knowledgebases/{self.created_kb_id}"
            )

        # 4. 删除用户（如果是测试创建的）
        if self.created_user_id and self.created_user_id != EXISTING_USER_ID:
            self.test_request(
                "User Management", "DELETE", f"/api/v1/users/{self.created_user_id}"
            )

    # ==================== 运行所有测试 ====================

    def run_all_tests(self):
        """运行所有测试"""
        print("\n🚀 开始 KnowFlow Server API 测试...")
        print(f"Base URL: {KNOWFLOW_BASE_URL}")
        print(f"API Key: {API_KEY[:20]}...")

        try:
            # 按优先级执行测试
            self.test_authentication_apis()  # P0
            self.test_user_management_apis()  # P0
            self.test_knowledgebase_management_apis()  # P0
            self.test_file_management_apis()  # P1
            self.test_document_management_apis()  # P1
            self.test_team_management_apis()  # P1
            self.test_rbac_management_apis()  # P1
            self.test_tenant_management_apis()  # P2
            self.test_parse_service_apis()  # P0
        finally:
            # self.test_cleanup()  # 可选：保留测试数据便于手动检查
            self.print_summary()
            self.save_results()

    def save_results(self, filename="knowflow_server_api_test_results.json"):
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

        # 按分类统计
        categories = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "success": 0, "failed": 0}
            categories[cat]["total"] += 1
            if r["status"] == "SUCCESS":
                categories[cat]["success"] += 1
            else:
                categories[cat]["failed"] += 1

        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        print(f"总计: {total} 个API")
        print(f"成功: {success} ✅")
        print(f"失败: {failed} ❌")
        print(f"成功率: {success/total*100:.1f}%")

        print("\n按分类统计:")
        for cat, stats in categories.items():
            rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"  {cat}: {stats['success']}/{stats['total']} ({rate:.1f}%)")


if __name__ == "__main__":
    tester = KnowFlowAPITester()
    tester.run_all_tests()
