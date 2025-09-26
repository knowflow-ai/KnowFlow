#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""
RBAC集成工具模块
提供主项目与KnowFlow RBAC系统的集成适配功能
"""

import requests
import logging
import os
from functools import wraps
from flask import request as flask_request, jsonify, current_app
from flask_login import login_required, current_user

from api.utils.api_utils import get_json_result
from api.settings import RetCode

logger = logging.getLogger(__name__)

# RBAC服务配置
KNOWFLOW_API_URL = os.getenv("KNOWFLOW_API_URL", "http://localhost:5000")
RBAC_SERVICE_URL = f"{KNOWFLOW_API_URL}/api/v1/rbac"
RBAC_ENABLED = True  # 全局开关，可通过环境变量控制

class RBACPermissionType:
    """RBAC权限类型枚举"""
    KB_READ = "read"         # 知识库读取权限
    KB_WRITE = "write"       # 知识库写入权限  
    KB_ADMIN = "admin"       # 知识库管理权限

class RBACResourceType:
    """RBAC资源类型枚举"""
    KNOWLEDGEBASE = "knowledgebase"
    DOCUMENT = "document"


def grant_role_to_user(user_id: str, role_code: str, resource_type: str | None = None,
                       resource_id: str | None = None, tenant_id: str | None = None) -> bool:
    """为用户授予角色（可选资源级）

    仅用于在不改变旧接口签名/返回的前提下，在业务创建成功后同步 RBAC 数据。
    返回布尔，不抛异常，失败记日志但不影响旧流程。
    """
    try:
        payload = {
            "role_code": role_code,
            "tenant_id": tenant_id or "default",
        }
        if resource_type:
            payload["resource_type"] = resource_type
        if resource_id:
            payload["resource_id"] = resource_id

        resp = requests.post(f"{RBAC_SERVICE_URL}/users/{user_id}/roles", json=payload, timeout=5)
        if resp.status_code == 200:
            return True
        logger.error(f"授予角色失败: {resp.status_code} - {resp.text}")
        return False
    except Exception as e:
        logger.error(f"授予角色异常: {e}")
        return False

def get_user_tenant_info():
    """获取当前用户和租户信息"""
    try:
        user_id = getattr(current_user, 'id', None)
        # 从request的上下文中获取tenant_id（通过装饰器设置）
        tenant_id = getattr(flask_request, 'tenant_id', None)
        if not tenant_id:
            tenant_id = 'default'  # 默认租户
        
        return user_id, tenant_id
    except Exception as e:
        logger.warning(f"获取用户租户信息失败: {e}")
        return None, None

def batch_check_rbac_permissions(user_id, resource_type, resource_ids, permission_type, tenant_id=None):
    """
    批量检查用户对多个资源的权限

    Args:
        user_id: 用户ID
        resource_type: 资源类型
        resource_ids: 资源ID列表
        permission_type: 权限类型
        tenant_id: 租户ID

    Returns:
        dict: {resource_id: bool} 权限映射
    """
    if not RBAC_ENABLED:
        logger.info("RBAC未启用，跳过批量权限检查")
        return {rid: True for rid in resource_ids}

    if not user_id or not resource_ids:
        logger.warning("用户ID或资源ID列表为空，批量权限检查失败")
        return {rid: False for rid in resource_ids}

    try:
        payload = {
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_ids": resource_ids,
            "permission_type": permission_type
        }

        response = requests.post(
            f"{RBAC_SERVICE_URL}/permissions/batch-check",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            permissions = result.get('permissions', {})
            logger.debug(f"批量权限检查完成: user={user_id}, checked {len(permissions)} resources")
            return permissions
        else:
            logger.error(f"批量权限检查失败: {response.status_code} - {response.text}")
            return {rid: False for rid in resource_ids}

    except Exception as e:
        logger.error(f"批量权限检查异常: {e}")
        return {rid: False for rid in resource_ids}

def check_rbac_permission(user_id, resource_type, resource_id, permission_type, tenant_id=None):
    """
    检查用户是否具有特定资源的权限（只检查资源级别权限，不涉及全局角色）

    Args:
        user_id: 用户ID
        resource_type: 资源类型
        resource_id: 资源ID
        permission_type: 权限类型
        tenant_id: 租户ID

    Returns:
        bool: 是否有权限
    """
    if not RBAC_ENABLED:
        logger.info("RBAC未启用，跳过权限检查")
        return True
        
    if not user_id:
        logger.warning("用户ID为空，权限检查失败")
        return False
        
    def _check_permission_for_user(check_user_id):
        """内部函数：检查指定用户ID的权限"""
        try:
            payload = {
                "user_id": check_user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "permission_type": permission_type
                # 不传tenant_id，让RBAC服务使用默认值'default'
            }
            
            response = requests.post(
                f"{RBAC_SERVICE_URL}/permissions/check",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                has_permission = result.get('has_permission', False)
                logger.debug(f"资源权限检查结果: user={check_user_id}, resource={resource_id}, permission={permission_type}, result={has_permission}")
                return has_permission
            else:
                logger.debug(f"资源权限检查失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.debug(f"资源权限检查异常: {e}")
            return False
    
    # 首先检查原始用户ID
    has_permission = _check_permission_for_user(user_id)
    
    # 如果权限检查失败，尝试回退机制：根据当前用户查找真实用户ID
    if not has_permission:
        try:
            from flask_login import current_user
            if hasattr(current_user, 'email') and current_user.email:
                # 根据邮箱查找真实的用户ID
                import mysql.connector
                from database import get_db_connection
                
                db = get_db_connection()
                cursor = db.cursor()
                cursor.execute("SELECT id FROM user WHERE email = %s", (current_user.email,))
                result = cursor.fetchone()
                cursor.close()
                db.close()
                
                if result and result[0] != user_id:
                    real_user_id = result[0]
                    logger.info(f"Token用户ID不匹配，尝试使用真实用户ID: {user_id} -> {real_user_id}")
                    has_permission = _check_permission_for_user(real_user_id)
                    
        except Exception as e:
            logger.debug(f"回退权限检查失败: {e}")
    
    return has_permission

def rbac_permission_required(
    permission_type,
    resource_type=RBACResourceType.KNOWLEDGEBASE,
    resource_id_param='kb_id',
    fallback_check=None,
    deny_code=RetCode.AUTHENTICATION_ERROR,
    deny_message="权限不足，请联系系统管理员进行授权"
):
    """
    RBAC资源权限检查装饰器（只检查资源级别权限，不涉及全局角色）
    
    Args:
        permission_type: 权限类型 (kb_read, kb_write, kb_admin)
        resource_type: 资源类型 (默认为knowledgebase)
        resource_id_param: 从请求中提取资源ID的参数名
        fallback_check: 当RBAC检查失败时的回退检查函数
    """
    def decorator(func):
        @login_required
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # 1. 获取用户和租户信息
                user_id, tenant_id = get_user_tenant_info()
                if not user_id:
                    return get_json_result(
                        data=False, 
                        message="用户认证失败", 
                        code=RetCode.AUTHENTICATION_ERROR
                    )
                
                # 2. 从请求中提取资源ID
                resource_id = None
                
                # 从URL路径参数提取
                if resource_id_param in kwargs:
                    resource_id = kwargs[resource_id_param]
                # 从查询参数提取    
                elif hasattr(flask_request, 'args') and resource_id_param in flask_request.args:
                    resource_id = flask_request.args.get(resource_id_param)
                # 从JSON Body提取
                elif hasattr(flask_request, 'json') and flask_request.json and resource_id_param in flask_request.json:
                    resource_id = flask_request.json.get(resource_id_param)
                # 从表单数据提取（multipart/form-data 或 application/x-www-form-urlencoded）
                elif hasattr(flask_request, 'form') and resource_id_param in flask_request.form:
                    resource_id = flask_request.form.get(resource_id_param)
                
                if not resource_id:
                    logger.warning(f"无法从请求中提取资源ID参数: {resource_id_param}")
                    return get_json_result(
                        data=False, 
                        message="缺少必要的资源标识", 
                        code=RetCode.ARGUMENT_ERROR
                    )
                
                # 3. 只检查资源级别的RBAC权限，不检查全局角色
                has_permission = check_rbac_permission(
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    permission_type=permission_type
                    # 不传tenant_id，让RBAC底层使用default
                )
                
                # 4. 如果RBAC检查失败且有回退检查，执行回退逻辑
                if not has_permission and fallback_check:
                    logger.info(f"资源权限检查失败，执行回退检查: {fallback_check.__name__}")
                    has_permission = fallback_check(resource_id, user_id)
                
                # 5. 权限验证失败
                if not has_permission:
                    logger.warning(f"资源权限不足: user={user_id}, resource={resource_id}, permission={permission_type}")
                    return get_json_result(
                        data=False,
                        message=deny_message,
                        code=deny_code
                    )
                
                # 6. 权限验证通过，执行原函数
                logger.debug(f"资源权限检查通过: user={user_id}, resource={resource_id}, permission={permission_type}")
                return func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"权限检查异常: {e}")
                return get_json_result(
                    data=False, 
                    message="权限检查服务异常", 
                    code=RetCode.EXCEPTION_ERROR
                )
        
        return wrapper
    return decorator

def kb_admin_required(resource_id_param='kb_id', fallback_check=None):
    """知识库管理权限装饰器"""
    return rbac_permission_required(
        permission_type=RBACPermissionType.KB_ADMIN,
        resource_id_param=resource_id_param,
        fallback_check=fallback_check
    )

def kb_write_required(resource_id_param='kb_id', fallback_check=None):
    """知识库写入权限装饰器"""
    return rbac_permission_required(
        permission_type=RBACPermissionType.KB_WRITE,
        resource_id_param=resource_id_param,
        fallback_check=fallback_check
    )

def kb_read_required(resource_id_param='kb_id', fallback_check=None):
    """知识库读取权限装饰器"""
    return rbac_permission_required(
        permission_type=RBACPermissionType.KB_READ,
        resource_id_param=resource_id_param,
        fallback_check=fallback_check
    )

def check_global_permission(user_id, permission_type, tenant_id=None):
    """
    检查用户是否具有全局权限
    
    Args:
        user_id: 用户ID
        permission_type: 权限类型 (read, write, admin等)
        tenant_id: 租户ID
        
    Returns:
        bool: 是否有全局权限
    """
    if not RBAC_ENABLED:
        logger.info("RBAC未启用，跳过全局权限检查")
        return True
        
    if not user_id:
        logger.warning("用户ID为空，全局权限检查失败")
        return False
        
    try:
        payload = {
            "user_id": user_id,
            "permission_type": permission_type,
            "tenant_id": tenant_id or "default"
        }
        
        response = requests.post(
            f"{RBAC_SERVICE_URL}/permissions/check-global",
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            has_permission = result.get('has_permission', False)
            logger.debug(f"全局权限检查结果: user={user_id}, permission={permission_type}, result={has_permission}")
            return has_permission
        else:
            logger.error(f"全局权限检查失败: {response.status_code} - {response.text}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"全局权限检查网络错误: {e}")
        return False
    except Exception as e:
        logger.error(f"全局权限检查异常: {e}")
        return False

def check_global_kb_admin_permission(user_id, tenant_id=None):
    """
    检查用户是否具有全局知识库管理员权限（兼容性方法）
    
    Args:
        user_id: 用户ID
        tenant_id: 租户ID
        
    Returns:
        bool: 是否有全局kb_admin权限
    """
    # 使用新的全局权限检查方法，检查admin权限（用于创建知识库等全局操作）
    return check_global_permission(user_id, "admin", tenant_id)

def global_kb_admin_required(deny_message="您没有创建知识库的权限，请联系管理员"):
    """
    全局知识库管理员权限装饰器
    用于需要全局kb_admin权限的操作，如创建知识库
    """
    def decorator(func):
        @login_required
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # 获取用户和租户信息
                user_id, tenant_id = get_user_tenant_info()
                if not user_id:
                    return get_json_result(
                        data=False, 
                        message="用户认证失败", 
                        code=RetCode.AUTHENTICATION_ERROR
                    )
                
                # 检查全局kb_admin权限
                has_permission = check_global_kb_admin_permission(user_id, tenant_id)
                
                if not has_permission:
                    logger.warning(f"用户 {user_id} 缺少全局kb_admin权限")
                    return get_json_result(
                        data=False,
                        message=deny_message,
                        code=RetCode.AUTHENTICATION_ERROR
                    )
                
                # 权限验证通过，执行原函数
                logger.debug(f"全局kb_admin权限检查通过: user={user_id}")
                return func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"全局权限检查异常: {e}")
                return get_json_result(
                    data=False, 
                    message="权限检查服务异常", 
                    code=RetCode.EXCEPTION_ERROR
                )
        
        return wrapper
    return decorator

def global_permission_required(permission_type, deny_message=None):
    """
    通用全局权限装饰器
    用于需要全局权限的操作，如创建知识库、创建文件等
    
    Args:
        permission_type: 权限类型 (read, write, admin等)
        deny_message: 自定义拒绝消息
    """
    def decorator(func):
        @login_required
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # 获取用户和租户信息
                user_id, tenant_id = get_user_tenant_info()
                if not user_id:
                    return get_json_result(
                        data=False, 
                        message="用户认证失败", 
                        code=RetCode.AUTHENTICATION_ERROR
                    )
                
                # 检查全局权限
                has_permission = check_global_permission(user_id, permission_type, tenant_id)
                
                if not has_permission:
                    message = deny_message or f"您没有{permission_type}权限，请联系管理员"
                    logger.warning(f"用户 {user_id} 缺少全局{permission_type}权限")
                    return get_json_result(
                        data=False,
                        message=message,
                        code=RetCode.AUTHENTICATION_ERROR
                    )
                
                # 权限验证通过，执行原函数
                logger.debug(f"全局{permission_type}权限检查通过: user={user_id}")
                return func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"全局权限检查异常: {e}")
                return get_json_result(
                    data=False, 
                    message="权限检查服务异常", 
                    code=RetCode.EXCEPTION_ERROR
                )
        
        return wrapper
    return decorator

# 为文档权限提供便捷方法（基于知识库权限）
def doc_read_required(fallback_check=None):
    """文档读取权限装饰器（基于知识库权限）"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 从doc_id获取kb_id，然后检查知识库读取权限
            from api.db.services.document_service import DocumentService
            
            doc_id = kwargs.get('doc_id') or flask_request.args.get('doc_id')
            if not doc_id:
                return get_json_result(
                    data=False, 
                    message="缺少文档ID", 
                    code=RetCode.ARGUMENT_ERROR
                )
            
            # 获取文档所属的知识库ID
            try:
                kb_id = DocumentService.get_kb_id_by_doc_id(doc_id)
                if not kb_id:
                    return get_json_result(
                        data=False, 
                        message="文档不存在或已删除", 
                        code=RetCode.DATA_ERROR
                    )
                
                # 使用知识库读取权限检查
                kwargs['kb_id'] = kb_id
                return kb_read_required(resource_id_param='kb_id', fallback_check=fallback_check)(func)(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"获取文档知识库ID失败: {e}")
                return get_json_result(
                    data=False, 
                    message="权限检查失败", 
                    code=RetCode.EXCEPTION_ERROR
                )
        
        return wrapper
    return decorator

def doc_write_required(fallback_check=None):
    """文档写入权限装饰器（基于知识库权限）"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from api.db.services.document_service import DocumentService
            
            doc_id = kwargs.get('doc_id') or flask_request.args.get('doc_id')
            if not doc_id:
                return get_json_result(
                    data=False, 
                    message="缺少文档ID", 
                    code=RetCode.ARGUMENT_ERROR
                )
            
            try:
                kb_id = DocumentService.get_kb_id_by_doc_id(doc_id)
                if not kb_id:
                    return get_json_result(
                        data=False, 
                        message="文档不存在或已删除", 
                        code=RetCode.DATA_ERROR
                    )
                
                kwargs['kb_id'] = kb_id
                return kb_write_required(resource_id_param='kb_id', fallback_check=fallback_check)(func)(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"获取文档知识库ID失败: {e}")
                return get_json_result(
                    data=False, 
                    message="权限检查失败", 
                    code=RetCode.EXCEPTION_ERROR
                )
        
        return wrapper
    return decorator
