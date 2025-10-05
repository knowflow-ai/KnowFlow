#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAGFlow API 客户端

提供与 RAGFlow 后端交互的统一接口，用于文档解析、进度查询等。
"""

import requests
import logging
from typing import List, Dict, Optional
import mysql.connector
from database import DB_CONFIG

logger = logging.getLogger(__name__)


class RAGFlowClient:
    """RAGFlow API 客户端"""

    def __init__(self, ragflow_url: str = "http://127.0.0.1:9380"):
        """初始化 RAGFlow 客户端

        Args:
            ragflow_url: RAGFlow 服务地址
        """
        self.base_url = ragflow_url.rstrip('/')
        logger.info(f"RAGFlowClient initialized with base_url: {self.base_url}")

    def _get_api_token_by_tenant(self, tenant_id: str) -> Optional[str]:
        """根据 tenant_id 获取 API token

        Args:
            tenant_id: 租户 ID

        Returns:
            str: API token，失败返回 None
        """
        conn = None
        cursor = None

        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)

            query = """
                SELECT token
                FROM api_token
                WHERE tenant_id = %s
                LIMIT 1
            """
            cursor.execute(query, (tenant_id,))
            result = cursor.fetchone()

            if result:
                token = result['token']
                logger.info(f"Found API token for tenant {tenant_id}: {token[:20]}...")
                return token

            logger.warning(f"No API token found for tenant {tenant_id}")
            return None

        except Exception as e:
            logger.exception(f"Failed to get API token for tenant {tenant_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _get_tenant_token(self, doc_id: str) -> Optional[str]:
        """获取文档所属 tenant 的 API token

        优先使用该 tenant 自己的 token，如果没有则回退到超级管理员的 token

        Args:
            doc_id: 文档 ID

        Returns:
            str: API token，失败返回 None
        """
        conn = None
        cursor = None

        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)

            # Step 1: 获取 tenant_id
            query1 = """
                SELECT k.tenant_id
                FROM document d
                JOIN knowledgebase k ON d.kb_id = k.id
                WHERE d.id = %s
                LIMIT 1
            """
            cursor.execute(query1, (doc_id,))
            tenant_result = cursor.fetchone()

            if not tenant_result:
                logger.error(f"Document {doc_id} not found or has no knowledgebase")
                return None

            tenant_id = tenant_result['tenant_id']
            logger.info(f"Found tenant_id={tenant_id} for document {doc_id}")

            # Step 2: 优先获取该 tenant 的 API token
            query2 = """
                SELECT token
                FROM api_token
                WHERE tenant_id = %s
                LIMIT 1
            """
            cursor.execute(query2, (tenant_id,))
            token_result = cursor.fetchone()

            if token_result:
                token = token_result['token']
                logger.info(f"Using tenant's own API token: {token[:20]}...")
                return token

            # Step 3: 回退到超级管理员的 API token
            logger.warning(f"No API token found for tenant {tenant_id}, trying admin token")
            query3 = """
                SELECT at.token
                FROM api_token at
                JOIN user u ON at.tenant_id = u.id
                WHERE u.email = 'admin@gmail.com'
                ORDER BY u.create_time ASC
                LIMIT 1
            """
            cursor.execute(query3)
            admin_token_result = cursor.fetchone()

            if admin_token_result:
                token = admin_token_result['token']
                logger.info(f"Using admin fallback API token: {token[:20]}...")
                return token

            logger.error(f"No API token found for tenant {tenant_id} or admin")
            return None

        except Exception as e:
            logger.exception(f"Failed to get tenant token for doc {doc_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def run_documents(self, doc_ids: List[str], run: int = 1, auth_token: Optional[str] = None) -> Dict:
        """调用 RAGFlow document_run API 批量解析文档

        Args:
            doc_ids: 文档 ID 列表
            run: 运行模式
                - 1: 开始解析
                - 0: 停止解析
                - 2: 取消任务
                - 3: 删除文档
            auth_token: 认证 token（JWT token，可选）。如果提供则直接使用

        Returns:
            dict: API 响应结果
        """
        if not doc_ids:
            return {"code": 400, "message": "doc_ids 不能为空"}

        # 构造请求
        url = f"{self.base_url}/v1/document/run"
        payload = {
            "doc_ids": doc_ids,
            "run": run
        }

        # 处理认证 token
        if auth_token:
            # 直接使用前端传来的 JWT token
            headers = {
                "Authorization": auth_token,  # JWT token 格式已包含前缀，直接使用
                "Content-Type": "application/json"
            }
            logger.info(f"Using provided JWT token for document_run")
        else:
            # 向后兼容：从文档查询（已废弃，仅用于调试）
            logger.warning("No auth_token provided, falling back to document lookup")
            token = self._get_tenant_token(doc_ids[0])
            if not token:
                return {"code": 401, "message": "无法获取认证 token"}
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

        logger.info(f"Calling RAGFlow document_run API: {url}, doc_ids={len(doc_ids)}, run={run}")

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            result = response.json()

            if response.status_code != 200:
                logger.error(f"RAGFlow API error: {response.status_code} - {result}")
                return {
                    "code": response.status_code,
                    "message": result.get("message", "Unknown error")
                }

            logger.info(f"RAGFlow document_run success: {result}")
            return result

        except requests.exceptions.Timeout:
            logger.error("RAGFlow API timeout")
            return {"code": 504, "message": "RAGFlow API 请求超时"}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Cannot connect to RAGFlow: {e}")
            return {"code": 503, "message": f"无法连接到 RAGFlow 服务: {e}"}
        except Exception as e:
            logger.exception(f"RAGFlow API call failed: {e}")
            return {"code": 500, "message": f"调用失败: {str(e)}"}

    def get_tasks_status(self, doc_ids: List[str]) -> List[Dict]:
        """查询文档的任务状态（从 RAGFlow task 表）

        Args:
            doc_ids: 文档 ID 列表

        Returns:
            list: 任务状态列表
        """
        if not doc_ids:
            return []

        conn = None
        cursor = None

        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)

            # 查询最新的任务状态
            placeholders = ','.join(['%s'] * len(doc_ids))
            query = f"""
                SELECT
                    t.doc_id,
                    t.progress,
                    t.progress_msg,
                    t.update_time,
                    t.chunk_ids,
                    d.name as doc_name,
                    d.run,
                    d.chunk_num
                FROM task t
                LEFT JOIN document d ON t.doc_id = d.id
                WHERE t.doc_id IN ({placeholders})
                AND t.id IN (
                    SELECT MAX(id) FROM task
                    WHERE doc_id IN ({placeholders})
                    GROUP BY doc_id
                )
                ORDER BY t.update_time DESC
            """

            # 参数需要传两次（两个 IN 子句）
            params = doc_ids + doc_ids
            cursor.execute(query, params)
            tasks = cursor.fetchall()

            # 计算实时分块数量（从 chunk_ids 解析）
            import json
            for task in tasks:
                chunk_ids_str = task.get('chunk_ids', '')
                original_chunk_num = task.get('chunk_num', 0)
                doc_id = task.get('doc_id')

                logger.info(f"[CHUNK] doc_id={doc_id}, chunk_ids长度={len(chunk_ids_str) if chunk_ids_str else 0}, document.chunk_num={original_chunk_num}, run={task.get('run')}")

                if chunk_ids_str:
                    try:
                        # 尝试 JSON 解析
                        chunk_ids = json.loads(chunk_ids_str) if isinstance(chunk_ids_str, str) else chunk_ids_str
                        if isinstance(chunk_ids, list):
                            task['chunk_num'] = len(chunk_ids)
                            logger.info(f"[CHUNK] doc_id={doc_id}, JSON解析成功: {len(chunk_ids)} 个分块")
                        else:
                            task['chunk_num'] = original_chunk_num
                    except json.JSONDecodeError:
                        # JSON 解析失败，尝试按空格分隔的格式解析（RAGFlow 默认格式）
                        try:
                            chunk_id_list = chunk_ids_str.strip().split()
                            task['chunk_num'] = len(chunk_id_list)
                            logger.info(f"[CHUNK] doc_id={doc_id}, 空格分隔解析成功: {len(chunk_id_list)} 个分块")
                        except Exception as e:
                            task['chunk_num'] = original_chunk_num
                            logger.error(f"[CHUNK] doc_id={doc_id}, 空格分隔解析失败: {e}")
                    except Exception as e:
                        task['chunk_num'] = original_chunk_num
                        logger.error(f"[CHUNK] doc_id={doc_id}, JSON解析失败: {e}")
                else:
                    # 没有 chunk_ids，使用 document.chunk_num
                    task['chunk_num'] = original_chunk_num
                    logger.info(f"[CHUNK] doc_id={doc_id}, 无chunk_ids，使用document.chunk_num: {original_chunk_num}")

            logger.info(f"Retrieved {len(tasks)} task statuses for {len(doc_ids)} documents")
            return tasks

        except Exception as e:
            logger.exception(f"Failed to get tasks status: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def get_document_info(self, doc_id: str) -> Optional[Dict]:
        """获取文档详细信息

        Args:
            doc_id: 文档 ID

        Returns:
            dict: 文档信息，失败返回 None
        """
        conn = None
        cursor = None

        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)

            query = """
                SELECT
                    id, name, kb_id, type, parser_id, parser_config,
                    run, progress, progress_msg, chunk_num, status
                FROM document
                WHERE id = %s
            """
            cursor.execute(query, (doc_id,))
            doc = cursor.fetchone()

            return doc

        except Exception as e:
            logger.exception(f"Failed to get document info for {doc_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


# 全局客户端实例
_ragflow_client: Optional[RAGFlowClient] = None


def get_ragflow_client() -> RAGFlowClient:
    """获取全局 RAGFlow 客户端实例

    Returns:
        RAGFlowClient: 客户端实例
    """
    global _ragflow_client
    if _ragflow_client is None:
        _ragflow_client = RAGFlowClient()
    return _ragflow_client
