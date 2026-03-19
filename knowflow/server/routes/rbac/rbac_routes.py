#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC权限管理路由
提供角色、权限管理的API接口
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Blueprint, request, jsonify, g
from typing import Optional
import logging
from datetime import datetime, timedelta
from services.rbac.permission_service import permission_service
# 移除中间件装饰器的导入
# from services.rbac.permission_decorator import (
#     require_login, admin_required, super_admin_required,
#     require_permission, require_role
# )
from models.rbac_models import ResourceType, PermissionType, RoleType

logger = logging.getLogger(__name__)

# 创建蓝图
rbac_bp = Blueprint('rbac', __name__, url_prefix='/api/v1/rbac')

def _format_role_data(role):
    """统一的角色数据格式化方法"""
    return {
        'id': role.id,
        'name': role.name,
        'code': role.code,
        'description': role.description,
        'role_type': role.role_type.value,
        'is_system': role.is_system,
        'tenant_id': role.tenant_id,
        'created_at': role.created_at.isoformat() if role.created_at else None,
        'updated_at': role.updated_at.isoformat() if role.updated_at else None
    }

def _build_roles_response(roles):
    """统一的角色响应构建方法"""
    roles_data = [_format_role_data(role) for role in roles]
    return {
        'success': True,
        'data': roles_data,
        'total': len(roles_data)
    }

def _handle_roles_error(error_msg, exception):
    """统一的错误处理方法"""
    logger.error(f"{error_msg}: {exception}")
    return {
        'success': False,
        'error': error_msg,
        'message': str(exception),
        'code': 500
    }, 500

@rbac_bp.route('/permissions/check', methods=['POST'])
def check_permission():
    """
    检查用户权限
    
    Request Body:
    {
        "resource_type": "knowledgebase",
        "resource_id": "kb_123",
        "permission_type": "read",
        "user_id": "user_123"  // 可选，默认为当前用户
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': '请求数据不能为空',
                'code': 400
            }), 400
        
        # 验证必需参数
        required_fields = ['resource_type', 'resource_id', 'permission_type', 'user_id']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'error': f'缺少必需参数: {field}',
                    'code': 400
                }), 400
        
        # 解析参数
        try:
            resource_type = ResourceType(data['resource_type'])
            permission_type = PermissionType(data['permission_type'])
        except ValueError as e:
            return jsonify({
                'error': f'无效的参数值: {str(e)}',
                'code': 400
            }), 400
        
        resource_id = data['resource_id']
        user_id = data['user_id']
        tenant_id = data.get('tenant_id', 'default')
        
        # 执行权限检查
        permission_check = permission_service.check_permission(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            permission_type=permission_type,
            tenant_id=tenant_id
        )
        
        return jsonify({
            'has_permission': permission_check.has_permission,
            'user_id': permission_check.user_id,
            'resource_type': permission_check.resource_type.value,
            'resource_id': permission_check.resource_id,
            'permission_type': permission_check.permission_type.value,
            'granted_roles': permission_check.granted_roles,
            'reason': permission_check.reason
        })
        
    except Exception as e:
        logger.error(f"权限检查失败: {e}")
        return jsonify({
            'error': '权限检查失败',
            'message': str(e),
            'code': 500
        }), 500

@rbac_bp.route('/permissions/batch-check', methods=['POST'])
def batch_check_permissions():
    """
    批量检查用户对多个资源的权限

    Request Body:
    {
        "user_id": "user_123",
        "resource_type": "knowledgebase",
        "resource_ids": ["kb_1", "kb_2", "kb_3"],
        "permission_type": "read",
        "tenant_id": "default"  // 可选
    }

    Response:
    {
        "permissions": {
            "kb_1": true,
            "kb_2": false,
            "kb_3": true
        }
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': '请求数据不能为空',
                'code': 400
            }), 400

        # 验证必需参数
        required_fields = ['user_id', 'resource_type', 'resource_ids', 'permission_type']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'error': f'缺少必需参数: {field}',
                    'code': 400
                }), 400

        # 验证 resource_ids 是列表
        if not isinstance(data['resource_ids'], list):
            return jsonify({
                'error': 'resource_ids 必须是列表',
                'code': 400
            }), 400

        if len(data['resource_ids']) == 0:
            return jsonify({
                'error': 'resource_ids 不能为空列表',
                'code': 400
            }), 400

        # 限制批量检查的数量，避免性能问题
        if len(data['resource_ids']) > 100:
            return jsonify({
                'error': 'resource_ids 数量不能超过100个',
                'code': 400
            }), 400

        # 解析参数
        try:
            resource_type = ResourceType(data['resource_type'])
            permission_type = PermissionType(data['permission_type'])
        except ValueError as e:
            return jsonify({
                'error': f'无效的参数值: {str(e)}',
                'code': 400
            }), 400

        user_id = data['user_id']
        resource_ids = data['resource_ids']
        tenant_id = data.get('tenant_id', 'default')

        # 使用优化的批量权限检查方法
        permissions = permission_service.batch_check_permissions(
            user_id=user_id,
            resource_type=resource_type,
            resource_ids=resource_ids,
            permission_type=permission_type,
            tenant_id=tenant_id
        )

        return jsonify({
            'permissions': permissions
        })

    except Exception as e:
        logger.error(f"批量权限检查失败: {e}")
        return jsonify({
            'error': '批量权限检查失败',
            'message': str(e),
            'code': 500
        }), 500

@rbac_bp.route('/permissions/check-global', methods=['POST'])
def check_global_permission():
    """
    检查用户全局权限
    
    Request Body:
    {
        "user_id": "user123",
        "permission_type": "write",
        "tenant_id": "tenant123"  // 可选
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': '请求数据不能为空',
                'code': 400
            }), 400
        
        user_id = data.get('user_id')
        permission_type = data.get('permission_type')
        tenant_id = data.get('tenant_id', 'default')
        
        if not user_id or not permission_type:
            return jsonify({
                'error': '缺少必需参数: user_id, permission_type',
                'code': 400
            }), 400
        
        # 解析权限类型
        try:
            perm_type = PermissionType(permission_type)
        except ValueError:
            return jsonify({
                'error': f'无效的权限类型: {permission_type}',
                'code': 400
            }), 400
        
        # 执行全局权限检查
        permission_check = permission_service.check_global_permission(
            user_id=user_id,
            permission_type=perm_type,
            tenant_id=tenant_id
        )
        
        return jsonify({
            'has_permission': permission_check.has_permission,
            'user_id': permission_check.user_id,
            'resource_type': permission_check.resource_type.value,
            'resource_id': permission_check.resource_id,
            'permission_type': permission_check.permission_type.value,
            'granted_roles': permission_check.granted_roles,
            'reason': permission_check.reason
        })
        
    except Exception as e:
        logger.error(f"全局权限检查失败: {e}")
        return jsonify({
            'error': '全局权限检查失败',
            'message': str(e),
            'code': 500
        }), 500

@rbac_bp.route('/users/batch-roles', methods=['POST'])
def batch_get_user_roles():
    """
    批量获取多个用户的角色信息

    Request Body:
    {
        "user_ids": ["user_id1", "user_id2", "user_id3"],
        "tenant_id": "default"  // 可选
    }

    Response:
    {
        "user_roles": {
            "user_id1": [
                {
                    "id": "role_id",
                    "name": "角色名称",
                    "code": "role_code",
                    ...
                }
            ],
            "user_id2": [...]
        }
    }
    """
    try:
        data = request.get_json()
        if not data or 'user_ids' not in data:
            return jsonify({
                'error': '缺少必需参数: user_ids',
                'code': 400
            }), 400

        user_ids = data['user_ids']
        if not isinstance(user_ids, list):
            return jsonify({
                'error': 'user_ids 必须是列表',
                'code': 400
            }), 400

        if len(user_ids) == 0:
            return jsonify({
                'error': 'user_ids 不能为空',
                'code': 400
            }), 400

        # 限制批量查询数量
        if len(user_ids) > 50:
            return jsonify({
                'error': 'user_ids 数量不能超过50个',
                'code': 400
            }), 400

        tenant_id = data.get('tenant_id', 'default')

        # 批量获取用户角色
        user_roles_map = permission_service.batch_get_user_roles(user_ids, tenant_id)

        # 格式化返回数据
        formatted_result = {}
        for user_id, roles in user_roles_map.items():
            formatted_result[user_id] = []
            for role in roles:
                formatted_result[user_id].append({
                    'id': role.id,
                    'name': role.name,
                    'code': role.code,
                    'description': role.description,
                    'role_type': role.role_type.value,
                    'is_system': role.is_system,
                    'tenant_id': role.tenant_id,
                    'created_at': role.created_at.isoformat() if role.created_at else None,
                    'updated_at': role.updated_at.isoformat() if role.updated_at else None
                })

        return jsonify({
            'user_roles': formatted_result,
            'total_users': len(formatted_result)
        })

    except Exception as e:
        logger.error(f"批量获取用户角色失败: {e}")
        return jsonify({
            'error': '批量获取用户角色失败',
            'message': str(e),
            'code': 500
        }), 500

@rbac_bp.route('/users/<user_id>/roles', methods=['GET'])
def get_user_roles(user_id: str):
    """
    获取用户的所有角色
    """
    try:
        tenant_id = request.args.get('tenant_id', 'default')
        roles = permission_service.get_user_roles(user_id, tenant_id)
        
        roles_data = []
        for role in roles:
            roles_data.append({
                'id': role.id,
                'name': role.name,
                'code': role.code,
                'description': role.description,
                'role_type': role.role_type.value,
                'is_system': role.is_system,
                'tenant_id': role.tenant_id,
                'created_at': role.created_at.isoformat() if role.created_at else None,
                'updated_at': role.updated_at.isoformat() if role.updated_at else None
            })
        
        return jsonify({
            'user_id': user_id,
            'roles': roles_data,
            'total': len(roles_data)
        })
        
    except Exception as e:
        logger.error(f"获取用户角色失败: {e}")
        return jsonify({
            'error': '获取用户角色失败',
            'message': str(e),
            'code': 500
        }), 500

@rbac_bp.route('/users/<user_id>/permissions', methods=['GET'])
def get_user_permissions(user_id: str):
    """
    获取用户的所有权限
    """
    try:
        tenant_id = request.args.get('tenant_id', 'default')
        resource_type_param = request.args.get('resource_type')
        
        resource_type = None
        if resource_type_param:
            try:
                resource_type = ResourceType(resource_type_param)
            except ValueError:
                return jsonify({
                    'error': f'无效的资源类型: {resource_type_param}',
                    'code': 400
                }), 400
        
        permissions = permission_service.get_user_permissions(user_id, resource_type, tenant_id)
        
        permissions_data = []
        for permission in permissions:
            permissions_data.append({
                'id': permission.id,
                'name': permission.name,
                'code': permission.code,
                'description': permission.description,
                'resource_type': permission.resource_type.value,
                'permission_type': permission.permission_type.value,
                'created_at': permission.created_at.isoformat() if permission.created_at else None,
                'updated_at': permission.updated_at.isoformat() if permission.updated_at else None
            })
        
        return jsonify({
            'user_id': user_id,
            'permissions': permissions_data,
            'total': len(permissions_data),
            'resource_type_filter': resource_type_param
        })
        
    except Exception as e:
        logger.error(f"获取用户权限失败: {e}")
        return jsonify({
            'error': '获取用户权限失败',
            'message': str(e),
            'code': 500
        }), 500

@rbac_bp.route('/users/<user_id>/roles', methods=['POST'])
def grant_role_to_user(user_id: str):
    """
    为用户授予角色
    
    Request Body:
    {
        "role_code": "editor",
        "tenant_id": "tenant_123",  // 可选
        "resource_type": "knowledgebase",  // 可选，用于资源级权限
        "resource_id": "kb_123",  // 可选，用于资源级权限
        "expires_at": "2024-12-31T23:59:59"  // 可选，过期时间
    }
    """
    try:
        data = request.get_json()
        if not data or 'role_code' not in data:
            return jsonify({
                'error': '缺少必需参数: role_code',
                'code': 400
            }), 400
        
        role_code = data['role_code']
        tenant_id = data.get('tenant_id', 'default')
        resource_type = None
        resource_id = data.get('resource_id')
        expires_at = None
        
        # 验证角色代码是否有效
        valid_roles = ['super_admin', 'admin', 'editor', 'viewer', 'user']
        if role_code not in valid_roles:
            return jsonify({
                'error': f'无效的角色代码: {role_code}',
                'code': 400
            }), 400
        
        # 解析资源类型
        if 'resource_type' in data:
            try:
                resource_type = ResourceType(data['resource_type'])
            except ValueError:
                return jsonify({
                    'error': f'无效的资源类型: {data["resource_type"]}',
                    'code': 400
                }), 400
        
        # 解析过期时间
        if 'expires_at' in data:
            try:
                expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    'error': '无效的过期时间格式',
                    'code': 400
                }), 400
        
        # 授予角色
        success = permission_service.grant_role_to_user(
            user_id=user_id,
            role_code=role_code,
            granted_by='system',
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            expires_at=expires_at
        )
        
        if success:
            return jsonify({
                'message': f'成功为用户 {user_id} 授予角色 {role_code}',
                'user_id': user_id,
                'role_code': role_code,
                'granted_by': 'system',
                'tenant_id': tenant_id,
                'resource_type': resource_type.value if resource_type else None,
                'resource_id': resource_id,
                'expires_at': expires_at.isoformat() if expires_at else None
            })
        else:
            return jsonify({
                'error': '授予角色失败',
                'code': 500
            }), 500
        
    except Exception as e:
        logger.error(f"授予角色失败: {e}")
        return jsonify({
            'error': '授予角色失败',
            'message': str(e),
            'code': 500
        }), 500

@rbac_bp.route('/users/<user_id>/roles/<role_code>', methods=['DELETE'])
def revoke_role_from_user(user_id: str, role_code: str):
    """
    撤销用户角色
    """
    try:
        tenant_id = request.args.get('tenant_id', 'default')
        resource_id = request.args.get('resource_id')
        
        success = permission_service.revoke_role_from_user(
            user_id=user_id,
            role_code=role_code,
            tenant_id=tenant_id,
            resource_id=resource_id
        )
        
        if success:
            return jsonify({
                'message': f'成功撤销用户 {user_id} 的角色 {role_code}',
                'user_id': user_id,
                'role_code': role_code,
                'tenant_id': tenant_id,
                'resource_id': resource_id
            })
        else:
            return jsonify({
                'error': '撤销角色失败',
                'code': 500
            }), 500
        
    except Exception as e:
        logger.error(f"撤销角色失败: {e}")
        return jsonify({
            'error': '撤销角色失败',
            'message': str(e),
            'code': 500
        }), 500

@rbac_bp.route('/permissions/simple-check', methods=['POST'])
def simple_permission_check():
    """
    简化的权限检查接口
    
    Request Body:
    {
        "permission_code": "kb_read",
        "resource_id": "kb_123",  // 可选
        "user_id": "user_123"  // 必需
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': '请求数据不能为空',
                'code': 400
            }), 400
        
        required_fields = ['permission_code', 'user_id']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'error': f'缺少必需参数: {field}',
                    'code': 400
                }), 400
        
        permission_code = data['permission_code']
        resource_id = data.get('resource_id')
        user_id = data['user_id']
        tenant_id = data.get('tenant_id', 'default')
        
        has_permission = permission_service.has_permission(
            user_id=user_id,
            permission_code=permission_code,
            resource_id=resource_id,
            tenant_id=tenant_id
        )
        
        return jsonify({
            'has_permission': has_permission,
            'user_id': user_id,
            'permission_code': permission_code,
            'resource_id': resource_id,
            'tenant_id': tenant_id
        })
        
    except Exception as e:
        logger.error(f"简化权限检查失败: {e}")
        return jsonify({
            'error': '权限检查失败',
            'message': str(e),
            'code': 500
        }), 500

@rbac_bp.route('/roles', methods=['GET'])
def get_all_roles():
    """
    获取所有角色列表
    """
    try:
        roles = permission_service.get_all_roles()
        return jsonify(_build_roles_response(roles))

    except Exception as e:
        return jsonify(*_handle_roles_error("获取角色列表失败", e))

@rbac_bp.route('/assignable-roles', methods=['GET'])
def get_assignable_roles():
    """
    获取可分配的角色列表（根据当前用户权限过滤）
    - 超级管理员：返回所有角色
    - 普通管理员：过滤掉受限角色（如admin）
    - 无用户信息：返回所有角色（向后兼容）
    """
    try:
        current_user_id = getattr(g, 'current_user_id', None)
        tenant_id = request.args.get('tenant_id')

        if current_user_id:
            # 有用户信息时，根据权限过滤
            roles = permission_service.get_assignable_roles(current_user_id, tenant_id)
        else:
            # 无用户信息时，返回所有角色（向后兼容）
            roles = permission_service.get_all_roles(tenant_id)

        return jsonify(_build_roles_response(roles))

    except Exception as e:
        return jsonify(*_handle_roles_error("获取可分配角色列表失败", e))

@rbac_bp.route('/teams/batch-roles', methods=['POST'])
def batch_get_team_roles():
    """
    批量获取多个团队的角色信息

    Request Body:
    {
        "team_ids": ["team_id1", "team_id2", "team_id3"],
        "tenant_id": "default"  // 可选
    }
    """
    try:
        data = request.get_json()
        if not data or 'team_ids' not in data:
            return jsonify({
                'error': '缺少必需参数: team_ids',
                'code': 400
            }), 400

        team_ids = data['team_ids']
        if not isinstance(team_ids, list):
            return jsonify({
                'error': 'team_ids 必须是列表',
                'code': 400
            }), 400

        if len(team_ids) == 0:
            return jsonify({
                'error': 'team_ids 不能为空',
                'code': 400
            }), 400

        # 限制批量查询数量
        if len(team_ids) > 50:
            return jsonify({
                'error': 'team_ids 数量不能超过50个',
                'code': 400
            }), 400

        tenant_id = data.get('tenant_id', 'default')

        # 批量获取团队角色
        team_roles_map = permission_service.batch_get_team_roles(team_ids, tenant_id)

        return jsonify({
            'team_roles': team_roles_map,
            'total_teams': len(team_roles_map)
        })

    except Exception as e:
        logger.error(f"批量获取团队角色失败: {e}")
        return jsonify({
            'error': '批量获取团队角色失败',
            'message': str(e),
            'code': 500
        }), 500

@rbac_bp.route('/permissions', methods=['GET'])
def get_all_permissions():
    """获取所有权限列表"""
    try:
        permissions = permission_service.get_all_permissions()
        return jsonify(permissions)
    except Exception as e:
        logger.error(f"获取权限列表失败: {str(e)}")
        return jsonify({
            'error': f'获取权限列表失败: {str(e)}',
            'code': 500
        }), 500

@rbac_bp.route('/roles/<role_code>/permissions', methods=['GET'])
def get_role_permissions(role_code: str):
    """获取角色权限映射"""
    try:
        permissions = permission_service.get_role_permissions(role_code)
        return jsonify(permissions)
    except Exception as e:
        logger.error(f"获取角色权限映射失败: {str(e)}")
        return jsonify({
            'error': f'获取角色权限映射失败: {str(e)}',
            'code': 500
        }), 500

@rbac_bp.route('/health', methods=['GET'])
def health_check():
    """
    RBAC系统健康检查
    """
    return jsonify({
        'status': 'healthy',
        'service': 'RBAC权限管理系统',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat()
    })

# 错误处理
@rbac_bp.errorhandler(400)
def bad_request(error):
    return jsonify({
        'error': '请求参数错误',
        'message': str(error),
        'code': 400
    }), 400

@rbac_bp.errorhandler(401)
def unauthorized(error):
    return jsonify({
        'error': '未授权访问',
        'message': '请先登录',
        'code': 401
    }), 401

@rbac_bp.errorhandler(403)
def forbidden(error):
    return jsonify({
        'error': '权限不足',
        'message': '您没有执行此操作的权限',
        'code': 403
    }), 403

@rbac_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': '服务器内部错误',
        'message': '系统异常，请稍后重试',
        'code': 500
    }), 500