#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC权限管理服务
提供权限检查、角色管理、用户权限查询等功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging
from database import get_db_connection
from models.rbac_models import (
    Permission, Role, UserRole, RolePermission,
    PermissionCheck, PermissionType, ResourceType, RoleType,
    SYSTEM_ROLES, SYSTEM_PERMISSIONS, TeamRole, RBAC_CONFIG
)
import uuid
from .permission_calculator import permission_calculator, PermissionResult
from .permission_cache import CachedPermissionService, permission_cache

logger = logging.getLogger(__name__)

class PermissionService:
    """权限管理服务类"""
    
    def __init__(self):
        pass
    
    def _get_db_connection(self):
        """获取数据库连接"""
        return get_db_connection()
    
    def check_permission(self, user_id: str, resource_type: ResourceType, 
                        resource_id: str, permission_type: PermissionType,
                        tenant_id: Optional[str] = None) -> PermissionCheck:
        """
        检查用户是否有指定资源的权限
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            resource_id: 资源ID
            permission_type: 权限类型
            tenant_id: 租户ID
            
        Returns:
            PermissionCheck: 权限检查结果
        """
        try:
            # 1. 检查超级管理员权限
            if self._is_super_admin(user_id):
                return PermissionCheck(
                    has_permission=True,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    permission_type=permission_type,
                    granted_roles=["super_admin"],
                    reason="超级管理员权限"
                )
            
            # 2. 检查直接资源权限
            direct_permission = self._check_direct_permission(
                user_id, resource_type, resource_id, permission_type, tenant_id
            )
            if direct_permission:
                return PermissionCheck(
                    has_permission=True,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    permission_type=permission_type,
                    granted_roles=["direct"],
                    reason="直接权限授权"
                )
            
            # 3. 检查角色权限
            role_permission = self._check_role_permission(
                user_id, resource_type, resource_id, permission_type, tenant_id
            )
            if role_permission[0]:
                return PermissionCheck(
                    has_permission=True,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    permission_type=permission_type,
                    granted_roles=role_permission[1],
                    reason="角色权限授权"
                )
            
            # 4. 检查资源所有者权限
            if self._is_resource_owner(user_id, resource_type, resource_id):
                return PermissionCheck(
                    has_permission=True,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    permission_type=permission_type,
                    granted_roles=["owner"],
                    reason="资源所有者权限"
                )
            
            return PermissionCheck(
                has_permission=False,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                permission_type=permission_type,
                reason="无相关权限"
            )
            
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return PermissionCheck(
                has_permission=False,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                permission_type=permission_type,
                reason=f"权限检查异常: {str(e)}"
            )
    
    def _is_super_admin(self, user_id: str) -> bool:
        """检查是否为超级管理员"""
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            # 1. 首先检查用户表中的 is_superuser 字段
            cursor.execute("""
                SELECT is_superuser FROM user WHERE id = %s
            """, (user_id,))
            user_result = cursor.fetchone()
            if user_result and user_result[0] == 1:
                return True
            
            # 2. 然后检查RBAC角色表中的 super_admin 角色
            cursor.execute("""
                SELECT COUNT(*) FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                WHERE ur.user_id = %s AND r.code = 'super_admin' AND ur.is_active = 1
            """, (user_id,))
            return cursor.fetchone()[0] > 0
            
        except Exception as e:
            logger.error(f"检查超级管理员权限失败: {e}")
            return False
    
    def _check_direct_permission(self, user_id: str, resource_type: ResourceType,
                               resource_id: str, permission_type: PermissionType,
                               tenant_id: Optional[str] = None) -> bool:
        """检查直接权限"""
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            sql = """
                SELECT COUNT(*) FROM rbac_resource_permissions
                WHERE user_id = %s AND resource_type = %s AND resource_id = %s
                AND permission_type = %s AND is_active = 1
                AND (expires_at IS NULL OR expires_at > NOW())
            """
            params = [user_id, resource_type.value, resource_id, permission_type.value]
            
            if tenant_id:
                sql += " AND tenant_id = %s"
                params.append(tenant_id)
            
            cursor.execute(sql, params)
            return cursor.fetchone()[0] > 0
        except Exception as e:
            logger.error(f"检查直接权限失败: {e}")
            return False
    
    def check_global_permission(self, user_id: str, permission_type: PermissionType, 
                               tenant_id: Optional[str] = None) -> 'PermissionCheck':
        """
        检查全局权限（用于全局操作如创建知识库、创建文件等）
        
        Args:
            user_id: 用户ID
            permission_type: 权限类型
            tenant_id: 租户ID
            
        Returns:
            PermissionCheck: 权限检查结果
        """
        try:
            # 1. 超级管理员检查
            if self._is_super_admin(user_id):
                return PermissionCheck(
                    has_permission=True,
                    user_id=user_id,
                    resource_type=ResourceType.SYSTEM,
                    resource_id=None,
                    permission_type=permission_type,
                    granted_roles=["超级管理员"],
                    reason="超级管理员权限"
                )
            
            # 2. 检查全局角色权限（resource_id为NULL的角色）
            db = self._get_db_connection()
            cursor = db.cursor()
            
            user_sql = """
                SELECT DISTINCT r.code, r.name FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                JOIN rbac_role_permissions rp ON r.id = rp.role_id
                JOIN rbac_permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = %s AND ur.is_active = 1
                AND p.permission_type = %s
                AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
                AND ur.resource_id IS NULL
            """
            params = [user_id, permission_type.value]
            
            if tenant_id:
                user_sql += " AND ur.tenant_id = %s"
                params.append(tenant_id)
            
            cursor.execute(user_sql, params)
            user_roles = cursor.fetchall()
            
            if user_roles:
                role_names = [role[1] for role in user_roles]
                return PermissionCheck(
                    has_permission=True,
                    user_id=user_id,
                    resource_type=ResourceType.SYSTEM,
                    resource_id=None,
                    permission_type=permission_type,
                    granted_roles=role_names,
                    reason="全局角色权限授权"
                )
            
            return PermissionCheck(
                has_permission=False,
                user_id=user_id,
                resource_type=ResourceType.SYSTEM,
                resource_id=None,
                permission_type=permission_type,
                reason="无相关全局权限"
            )
            
        except Exception as e:
            logger.error(f"检查全局权限失败: {e}")
            return PermissionCheck(
                has_permission=False,
                user_id=user_id,
                resource_type=ResourceType.SYSTEM,
                resource_id=None,
                permission_type=permission_type,
                reason=f"全局权限检查异常: {str(e)}"
            )
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'db' in locals() and db:
                db.close()
    
    def _check_role_permission(self, user_id: str, resource_type: ResourceType,
                             resource_id: str, permission_type: PermissionType,
                             tenant_id: Optional[str] = None) -> Tuple[bool, List[str]]:
        """检查角色权限（包含用户直接角色和团队角色）"""
        db = None
        cursor = None
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            # 1. 检查用户直接角色权限
            user_sql = """
                SELECT DISTINCT r.code, r.name FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                JOIN rbac_role_permissions rp ON r.id = rp.role_id
                JOIN rbac_permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = %s AND ur.is_active = 1
                AND p.resource_type = %s AND p.permission_type = %s
                AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
                AND ur.resource_id = %s
            """
            user_params = [user_id, resource_type.value, permission_type.value, resource_id]
            
            if tenant_id:
                user_sql += " AND ur.tenant_id = %s"
                user_params.append(tenant_id)
            
            cursor.execute(user_sql, user_params)
            user_roles = cursor.fetchall()
            
            # 2. 检查用户团队角色权限
            team_sql = """
                SELECT DISTINCT r.code, r.name FROM rbac_team_roles tr
                JOIN user_tenant ut ON tr.team_id = ut.tenant_id
                JOIN rbac_roles r ON tr.role_code = r.code
                JOIN rbac_role_permissions rp ON r.id = rp.role_id
                JOIN rbac_permissions p ON rp.permission_id = p.id
                WHERE ut.user_id = %s AND ut.status = 1 AND tr.is_active = 1
                AND p.resource_type = %s AND p.permission_type = %s
                AND (tr.expires_at IS NULL OR tr.expires_at > NOW())
                AND tr.resource_id = %s
            """
            team_params = [user_id, resource_type.value, permission_type.value, resource_id]
            
            if tenant_id:
                team_sql += " AND tr.tenant_id = %s"
                team_params.append(tenant_id)
            
            cursor.execute(team_sql, team_params)
            team_roles = cursor.fetchall()
            
            # 3. 合并结果
            all_roles = list(user_roles) + list(team_roles)
            
            if all_roles:
                role_names = []
                for role in all_roles:
                    role_name = f"{role[1]}(通过团队)" if role in team_roles else role[1]
                    role_names.append(role_name)
                return True, role_names
            return False, []
            
        except Exception as e:
            logger.error(f"检查角色权限失败: {e}")
            return False, []
        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()
    
    def _is_resource_owner(self, user_id: str, resource_type: ResourceType, resource_id: str) -> bool:
        """检查是否为资源所有者"""
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            if resource_type == ResourceType.KNOWLEDGEBASE:
                # 检查knowledgebase表是否存在
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = 'knowledgebase'
                """)
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    logger.warning("knowledgebase表不存在，跳过资源所有者检查")
                    return False
                
                cursor.execute("""
                    SELECT COUNT(*) FROM knowledgebase
                    WHERE id = %s AND created_by = %s
                """, (resource_id, user_id))
                return cursor.fetchone()[0] > 0
            elif resource_type == ResourceType.TEAM:
                cursor.execute("""
                    SELECT COUNT(*) FROM user_tenant
                    WHERE tenant_id = %s AND user_id = %s AND role = 'owner'
                """, (resource_id, user_id))
                return cursor.fetchone()[0] > 0
            
            return False
        except Exception as e:
            logger.error(f"检查资源所有者失败: {e}")
            return False
        finally:
            if 'cursor' in locals():
                cursor.close()
    
    def grant_role_to_user(self, user_id: str, role_code: str, 
                          granted_by: str, tenant_id: Optional[str] = None,
                          resource_type: Optional[ResourceType] = None,
                          resource_id: Optional[str] = None,
                          expires_at: Optional[datetime] = None) -> bool:
        """
        为用户授予角色（单一角色语义：如果已有角色则更新，否则创建新角色）
        
        Args:
            user_id: 用户ID
            role_code: 角色代码
            granted_by: 授权人
            tenant_id: 租户ID
            resource_type: 资源类型（可选，用于资源级权限）
            resource_id: 资源ID（可选，用于资源级权限）
            expires_at: 过期时间（可选）
            
        Returns:
            bool: 是否成功
        """
        cursor = None
        db = None
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            # 获取角色ID
            cursor.execute("SELECT id FROM rbac_roles WHERE code = %s", (role_code,))
            role_result = cursor.fetchone()
            if not role_result:
                logger.error(f"角色不存在: {role_code}")
                return False
            
            role_id = role_result[0]
            
            # 检查用户是否已有对应资源的角色记录
            if resource_type and resource_id:
                # 资源级权限检查
                check_sql = """
                    SELECT id FROM rbac_user_roles
                    WHERE user_id = %s AND resource_type = %s AND resource_id = %s
                """
                cursor.execute(check_sql, (user_id, resource_type.value, resource_id))
            else:
                # 全局角色检查
                check_sql = "SELECT id FROM rbac_user_roles WHERE user_id = %s AND resource_type IS NULL AND resource_id IS NULL"
                cursor.execute(check_sql, (user_id,))
            existing_record = cursor.fetchone()
            
            if existing_record:
                # 更新现有记录
                if resource_type and resource_id:
                    # 更新资源级权限记录
                    update_sql = """
                        UPDATE rbac_user_roles
                        SET role_id = %s, tenant_id = %s, granted_by = %s,
                            granted_at = NOW(), expires_at = %s, is_active = 1, updated_at = NOW()
                        WHERE user_id = %s AND resource_type = %s AND resource_id = %s
                    """
                    cursor.execute(update_sql, (
                        role_id, tenant_id, granted_by, expires_at, user_id, resource_type.value, resource_id
                    ))
                else:
                    # 更新全局权限记录
                    update_sql = """
                        UPDATE rbac_user_roles
                        SET role_id = %s, tenant_id = %s, granted_by = %s,
                            granted_at = NOW(), expires_at = %s, is_active = 1, updated_at = NOW()
                        WHERE user_id = %s AND resource_type IS NULL AND resource_id IS NULL
                    """
                    cursor.execute(update_sql, (
                        role_id, tenant_id, granted_by, expires_at, user_id
                    ))
            else:
                # 插入新记录
                insert_sql = """
                    INSERT INTO rbac_user_roles
                    (user_id, role_id, tenant_id, resource_type, resource_id,
                     granted_by, granted_at, expires_at, is_active, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, 1, NOW())
                """
                cursor.execute(insert_sql, (
                    user_id, role_id, tenant_id,
                    resource_type.value if resource_type else None,
                    resource_id, granted_by, expires_at
                ))
            
            db.commit()
            logger.info(f"成功为用户 {user_id} 授予角色 {role_code}")
            return True
            
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"授予角色失败: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
    
    def revoke_role_from_user(self, user_id: str, role_code: str,
                             tenant_id: Optional[str] = None,
                             resource_id: Optional[str] = None) -> bool:
        """
        撤销用户角色
        
        Args:
            user_id: 用户ID
            role_code: 角色代码
            tenant_id: 租户ID
            resource_id: 资源ID
            
        Returns:
            bool: 是否成功
        """
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            sql = """
                UPDATE rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                SET ur.is_active = 0, ur.updated_at = NOW()
                WHERE ur.user_id = %s AND r.code = %s
            """
            params = [user_id, role_code]
            
            if tenant_id:
                sql += " AND ur.tenant_id = %s"
                params.append(tenant_id)
            if resource_id:
                sql += " AND ur.resource_id = %s"
                params.append(resource_id)
            
            cursor.execute(sql, params)
            db.commit()
            
            logger.info(f"成功撤销用户 {user_id} 的角色 {role_code}")
            return True
            
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"撤销角色失败: {e}")
            return False
    
    def get_user_roles(self, user_id: str, tenant_id: Optional[str] = None) -> List[Role]:
        """
        获取用户的角色列表（遵循单一角色语义：返回优先级最高的一个）
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            
        Returns:
            List[Role]: 角色列表（长度最多为1）
        """
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            sql = """
                SELECT DISTINCT r.id, r.name, r.code, r.description, r.role_type,
                       r.is_system, r.tenant_id, r.created_at, r.updated_at
                FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                WHERE ur.user_id = %s AND ur.is_active = 1
                AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
                AND ur.resource_type IS NULL AND ur.resource_id IS NULL
            """
            params = [user_id]
            
            if tenant_id:
                sql += " AND ur.tenant_id = %s"
                params.append(tenant_id)
            
            # 仅返回一个：按角色优先级排序
            sql += """
                ORDER BY CASE r.code
                    WHEN 'super_admin' THEN 1
                    WHEN 'admin' THEN 2
                    WHEN 'editor' THEN 3
                    WHEN 'viewer' THEN 4
                    WHEN 'user' THEN 5
                    ELSE 999
                END
                LIMIT 1
            """
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            roles = []
            for row in rows:
                role = Role(
                    id=row[0],
                    name=row[1],
                    code=row[2],
                    description=row[3],
                    role_type=RoleType(row[4]),
                    is_system=bool(row[5]),
                    tenant_id=row[6],
                    created_at=row[7],
                    updated_at=row[8]
                )
                roles.append(role)
            
            return roles
            
        except Exception as e:
            logger.error(f"获取用户角色失败: {e}")
            return []
    
    def get_all_roles(self, tenant_id: Optional[str] = None) -> List[Role]:
        """
        获取所有可用的角色
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            List[Role]: 角色列表
        """
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            sql = """
                 SELECT id, name, code, description, role_type,
                        is_system, tenant_id, created_at, updated_at
                 FROM rbac_roles
             """
            params = []
            
            if tenant_id:
                sql += " WHERE (tenant_id = %s OR tenant_id IS NULL)"
                params.append(tenant_id)
            
            sql += " ORDER BY name"
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            roles = []
            for row in rows:
                role = Role(
                    id=row[0],
                    name=row[1],
                    code=row[2],
                    description=row[3],
                    role_type=RoleType(row[4]),
                    is_system=bool(row[5]),
                    tenant_id=row[6],
                    created_at=row[7],
                    updated_at=row[8]
                )
                roles.append(role)
            
            return roles
            
        except Exception as e:
            logger.error(f"获取所有角色失败: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    def get_assignable_roles(self, current_user_id: str, tenant_id: Optional[str] = None) -> List[Role]:
        """
        获取当前用户可以分配的角色列表
        根据RBAC配置进行权限过滤

        Args:
            current_user_id: 当前用户ID
            tenant_id: 租户ID

        Returns:
            List[Role]: 可分配的角色列表
        """
        try:
            # 获取所有角色
            all_roles = self.get_all_roles(tenant_id)

            # 超级管理员可以分配所有角色
            if self._is_super_admin(current_user_id):
                return all_roles

            # 非超级管理员过滤受限角色
            restricted_roles = RBAC_CONFIG.get("RESTRICTED_ROLES", [])
            return [role for role in all_roles if role.code not in restricted_roles]

        except Exception as e:
            logger.error(f"获取可分配角色失败: {e}")
            return []

    def get_user_permissions(self, user_id: str, resource_type: Optional[ResourceType] = None,
                           tenant_id: Optional[str] = None) -> List[Permission]:
        """
        获取用户的所有权限
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型过滤
            tenant_id: 租户ID
            
        Returns:
            List[Permission]: 权限列表
        """
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            sql = """
                SELECT DISTINCT p.id, p.name, p.code, p.description,
                       p.resource_type, p.permission_type, p.created_at, p.updated_at
                FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                JOIN rbac_role_permissions rp ON r.id = rp.role_id
                JOIN rbac_permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = %s AND ur.is_active = 1
                AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
            """
            params = [user_id]
            
            if resource_type:
                sql += " AND p.resource_type = %s"
                params.append(resource_type.value)
            
            if tenant_id:
                sql += " AND ur.tenant_id = %s"
                params.append(tenant_id)
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            permissions = []
            for row in rows:
                permission = Permission(
                    id=row[0],
                    name=row[1],
                    code=row[2],
                    description=row[3],
                    resource_type=ResourceType(row[4]),
                    permission_type=PermissionType(row[5]),
                    created_at=row[6],
                    updated_at=row[7]
                )
                permissions.append(permission)
            
            return permissions
            
        except Exception as e:
            logger.error(f"获取用户权限失败: {e}")
            return []
    
    def has_permission(self, user_id: str, permission_code: str,
                      resource_id: Optional[str] = None,
                      tenant_id: Optional[str] = None) -> bool:
        """
        简化的权限检查方法
        
        Args:
            user_id: 用户ID
            permission_code: 权限代码
            resource_id: 资源ID
            tenant_id: 租户ID
            
        Returns:
            bool: 是否有权限
        """
        try:
            # 从权限代码解析资源类型和权限类型
            if permission_code.startswith('kb_'):
                resource_type = ResourceType.KNOWLEDGEBASE
                perm_type = permission_code.replace('kb_', '')
            elif permission_code.startswith('doc_'):
                resource_type = ResourceType.DOCUMENT
                perm_type = permission_code.replace('doc_', '')
            elif permission_code.startswith('team_'):
                resource_type = ResourceType.TEAM
                perm_type = permission_code.replace('team_', '')
            else:
                return False
            
            try:
                permission_type = PermissionType(perm_type)
            except ValueError:
                return False
            
            result = self.check_permission(
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id or '',
                permission_type=permission_type,
                tenant_id=tenant_id
            )
            
            return result.has_permission
            
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return False

    def _role_exists(self, role_code: str, tenant_id: str = "default") -> bool:
        """检查角色是否存在"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            query = "SELECT COUNT(*) FROM rbac_roles WHERE code = %s"
            cursor.execute(query, (role_code,))
            count = cursor.fetchone()[0]
            
            return count > 0
            
        except Exception as e:
            logger.error(f"检查角色存在性失败: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_user_team_roles(self, user_id: str, tenant_id: str = "default") -> List[TeamRole]:
        """
        获取用户通过团队获得的角色
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            
        Returns:
            List[TeamRole]: 团队角色列表
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 查询用户所属的团队，然后查询这些团队的角色
            query = """
            SELECT DISTINCT 
                tr.id,
                tr.team_id,
                tr.role_code,
                tr.resource_type,
                tr.resource_id,
                tr.tenant_id,
                tr.granted_by,
                tr.granted_at,
                tr.expires_at,
                tr.is_active
            FROM rbac_team_roles tr
            JOIN user_tenant ut ON tr.team_id = ut.tenant_id
            WHERE ut.user_id = %s 
                AND ut.status = 1 
                AND tr.tenant_id = %s 
                AND tr.is_active = 1
                AND (tr.expires_at IS NULL OR tr.expires_at > NOW())
            """
            
            cursor.execute(query, (user_id, tenant_id))
            results = cursor.fetchall()
            
            team_roles = []
            for row in results:
                team_role = TeamRole(
                    id=row['id'],
                    team_id=row['team_id'],
                    role_code=row['role_code'],
                    resource_type=ResourceType(row['resource_type']) if row['resource_type'] else None,
                    resource_id=row['resource_id'],
                    tenant_id=row['tenant_id'],
                    granted_by=row['granted_by'],
                    granted_at=row['granted_at'].isoformat() if row['granted_at'] else None,
                    expires_at=row['expires_at'].isoformat() if row['expires_at'] else None,
                    is_active=bool(row['is_active'])
                )
                team_roles.append(team_role)
                
            return team_roles
            
        except Exception as e:
            logger.error(f"获取用户团队角色失败: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def grant_team_role(self, team_id: str, role_code: str, resource_type: ResourceType = None, 
                       resource_id: str = None, tenant_id: str = "default", 
                       granted_by: str = None) -> bool:
        """
        为团队授予角色（单一角色语义：同一作用域内仅保留一个角色，重复分配直接替换）
        
        Args:
            team_id: 团队ID
            role_code: 角色代码
            resource_type: 资源类型
            resource_id: 资源ID
            tenant_id: 租户ID
            granted_by: 授权者ID
            
        Returns:
            bool: 是否授权成功
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 检查角色是否存在
            if not self._role_exists(role_code, tenant_id):
                logger.error(f"角色不存在: {role_code}")
                return False
            
            # 单一角色语义：删除同一作用域下已有的团队角色
            delete_query = "DELETE FROM rbac_team_roles WHERE team_id = %s AND tenant_id = %s"
            delete_params = [team_id, tenant_id]
            if resource_type is not None:
                delete_query += " AND resource_type = %s"
                delete_params.append(resource_type.value)
            else:
                delete_query += " AND resource_type IS NULL"
            if resource_id is not None:
                delete_query += " AND resource_id = %s"
                delete_params.append(resource_id)
            else:
                delete_query += " AND resource_id IS NULL"
            cursor.execute(delete_query, delete_params)
            
            # 生成ID
            team_role_id = str(uuid.uuid4()).replace('-', '')
            
            # 插入团队角色映射
            query = """
            INSERT INTO rbac_team_roles 
            (id, team_id, role_code, resource_type, resource_id, tenant_id, granted_by, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE 
                is_active = 1, 
                granted_by = VALUES(granted_by),
                granted_at = CURRENT_TIMESTAMP
            """
            
            cursor.execute(query, (
                team_role_id, team_id, role_code, 
                resource_type.value if resource_type else None,
                resource_id, tenant_id, granted_by
            ))
            
            conn.commit()
            logger.info(f"团队角色授权成功(替换同域已有角色): team_id={team_id}, role={role_code}, resource={resource_id}")
            return True
            
        except Exception as e:
            logger.error(f"团队角色授权失败: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def revoke_team_role(self, team_id: str, role_code: str = None, resource_type: ResourceType = None,
                        resource_id: str = None, tenant_id: str = "default") -> bool:
        """
        撤销团队角色
        
        Args:
            team_id: 团队ID
            role_code: 角色代码(可选，为空则撤销该资源的所有角色)
            resource_type: 资源类型
            resource_id: 资源ID
            tenant_id: 租户ID
            
        Returns:
            bool: 是否撤销成功
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 构建删除条件
            where_conditions = ["team_id = %s", "tenant_id = %s"]
            params = [team_id, tenant_id]
            
            if role_code:
                where_conditions.append("role_code = %s")
                params.append(role_code)
                
            if resource_type:
                where_conditions.append("resource_type = %s")
                params.append(resource_type.value)
                
            if resource_id:
                where_conditions.append("resource_id = %s")
                params.append(resource_id)
            
            where_clause = " AND ".join(where_conditions)
            
            # 执行删除
            query = f"DELETE FROM rbac_team_roles WHERE {where_clause}"
            cursor.execute(query, params)
            
            affected_rows = cursor.rowcount
            conn.commit()
            
            logger.info(f"团队角色撤销成功: team_id={team_id}, 影响行数={affected_rows}")
            return affected_rows > 0
            
        except Exception as e:
            logger.error(f"团队角色撤销失败: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def get_team_roles(self, team_id: str, resource_type: ResourceType = None, 
                      resource_id: str = None, tenant_id: str = "default") -> List[TeamRole]:
        """
        获取团队角色列表
        
        Args:
            team_id: 团队ID
            resource_type: 资源类型(可选)
            resource_id: 资源ID(可选)
            tenant_id: 租户ID
            
        Returns:
            List[TeamRole]: 团队角色列表
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 构建查询条件
            where_conditions = ["team_id = %s", "tenant_id = %s", "is_active = 1"]
            params = [team_id, tenant_id]
            
            if resource_type:
                where_conditions.append("resource_type = %s")
                params.append(resource_type.value)
                
            if resource_id:
                where_conditions.append("resource_id = %s")
                params.append(resource_id)
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
            SELECT 
                id, team_id, role_code, resource_type, resource_id, 
                tenant_id, granted_by, granted_at, expires_at, is_active
            FROM rbac_team_roles 
            WHERE {where_clause}
            ORDER BY granted_at DESC
            """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            team_roles = []
            for row in results:
                team_role = TeamRole(
                    id=row['id'],
                    team_id=row['team_id'],
                    role_code=row['role_code'],
                    resource_type=ResourceType(row['resource_type']) if row['resource_type'] else None,
                    resource_id=row['resource_id'],
                    tenant_id=row['tenant_id'],
                    granted_by=row['granted_by'],
                    granted_at=row['granted_at'].isoformat() if row['granted_at'] else None,
                    expires_at=row['expires_at'].isoformat() if row['expires_at'] else None,
                    is_active=bool(row['is_active'])
                )
                team_roles.append(team_role)
                
            return team_roles
            
        except Exception as e:
            logger.error(f"获取团队角色失败: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_all_permissions(self) -> List[Dict]:
        """获取所有权限列表"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = """
            SELECT id, code, name, description, resource_type, permission_type, 
                   created_at, updated_at
            FROM rbac_permissions 
            ORDER BY resource_type, permission_type
            """
            
            cursor.execute(query)
            permissions = cursor.fetchall()
            
            # 转换为更友好的格式
            result = []
            for perm in permissions:
                result.append({
                    'id': perm['id'],
                    'code': perm['code'],
                    'name': perm['name'],
                    'description': perm['description'],
                    'resource_type': perm['resource_type'],
                    'permission_type': perm['permission_type'],
                    'created_at': perm['created_at'].isoformat() if perm['created_at'] else None,
                    'updated_at': perm['updated_at'].isoformat() if perm['updated_at'] else None
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取所有权限失败: {str(e)}")
            return []
        finally:
            if conn:
                conn.close()
    
    def get_role_permissions(self, role_code: str) -> List[Dict]:
        """获取角色权限映射"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = """
            SELECT p.id, p.code, p.name, p.description, p.resource_type, p.permission_type,
                   r.name as role_name, rp.created_at
            FROM rbac_role_permissions rp
            JOIN rbac_roles r ON rp.role_id = r.id
            JOIN rbac_permissions p ON rp.permission_id = p.id
            WHERE r.code = %s
            ORDER BY p.resource_type, p.permission_type
            """
            
            cursor.execute(query, (role_code,))
            permissions = cursor.fetchall()
            
            # 转换为更友好的格式
            result = []
            for perm in permissions:
                result.append({
                    'permission_id': perm['id'],
                    'permission_code': perm['code'],
                    'permission_name': perm['name'],
                    'description': perm['description'],
                    'resource_type': perm['resource_type'],
                    'permission_type': perm['permission_type'],
                    'role_name': perm['role_name'],
                    'granted_at': perm['created_at'].isoformat() if perm['created_at'] else None
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取角色权限映射失败: {str(e)}")
            return []
        finally:
            if conn:
                conn.close()

    def check_permission_enhanced(self, user_id: str, resource_type: ResourceType, 
                                 resource_id: str, permission_type: PermissionType,
                                 tenant_id: Optional[str] = None, use_cache: bool = True) -> PermissionResult:
        """
        增强的权限检查方法，使用新的权限计算器和缓存机制
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            resource_id: 资源ID
            permission_type: 权限类型
            tenant_id: 租户ID
            use_cache: 是否使用缓存
            
        Returns:
            PermissionResult: 详细的权限检查结果
        """
        tenant_id = tenant_id or "default"
        
        # 使用缓存权限服务
        cached_service = CachedPermissionService(permission_calculator, permission_cache)
        return cached_service.check_permission(
            user_id, resource_type, resource_id, permission_type, tenant_id, use_cache
        )
    
    def get_user_effective_permissions(self, user_id: str, resource_type: ResourceType, 
                                     resource_id: str, tenant_id: str = "default") -> Dict[str, PermissionResult]:
        """
        获取用户对特定资源的所有有效权限
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            resource_id: 资源ID
            tenant_id: 租户ID
            
        Returns:
            Dict[str, PermissionResult]: 权限名称到权限结果的映射
        """
        return permission_calculator.get_user_effective_permissions(
            user_id, resource_type, resource_id, tenant_id
        )
    
    def compare_user_permissions(self, user1_id: str, user2_id: str, 
                               resource_type: ResourceType, resource_id: str,
                               tenant_id: str = "default") -> Dict[str, any]:
        """
        比较两个用户的权限差异
        
        Args:
            user1_id: 第一个用户ID
            user2_id: 第二个用户ID
            resource_type: 资源类型
            resource_id: 资源ID
            tenant_id: 租户ID
            
        Returns:
            Dict[str, any]: 权限比较结果
        """
        return permission_calculator.compare_user_permissions(
            user1_id, user2_id, resource_type, resource_id, tenant_id
        )
    
    def invalidate_user_permissions(self, user_id: str) -> int:
        """
        使用户权限缓存失效
        
        Args:
            user_id: 用户ID
            
        Returns:
            int: 失效的缓存条目数
        """
        return permission_cache.invalidate_user(user_id)
    
    def invalidate_resource_permissions(self, resource_type: ResourceType, resource_id: str) -> int:
        """
        使资源权限缓存失效
        
        Args:
            resource_type: 资源类型
            resource_id: 资源ID
            
        Returns:
            int: 失效的缓存条目数
        """
        return permission_cache.invalidate_resource(resource_type, resource_id)
    
    def invalidate_team_permissions(self, team_id: str) -> int:
        """
        使团队权限缓存失效
        
        Args:
            team_id: 团队ID
            
        Returns:
            int: 失效的缓存条目数
        """
        return permission_cache.invalidate_team(team_id)
    
    def get_permission_cache_stats(self) -> Dict[str, any]:
        """
        获取权限缓存统计信息
        
        Returns:
            Dict[str, any]: 缓存统计信息
        """
        return permission_cache.get_stats()
    
    def cleanup_permission_cache(self) -> int:
        """
        清理过期的权限缓存
        
        Returns:
            int: 清理的缓存条目数
        """
        return permission_cache.cleanup_expired()

# 全局权限服务实例
permission_service = PermissionService()