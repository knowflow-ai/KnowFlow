#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC权限管理模型
定义角色、权限、用户角色关联等数据模型
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class PermissionType(Enum):
    """权限类型枚举"""
    READ = "read"
    WRITE = "write" 
    DELETE = "delete"
    ADMIN = "admin"
    SHARE = "share"
    EXPORT = "export"

class ResourceType(Enum):
    """资源类型枚举"""
    KNOWLEDGEBASE = "knowledgebase"
    DOCUMENT = "document"
    TEAM = "team"
    SYSTEM = "system"
    USER = "user"

class RoleType(Enum):
    """角色类型枚举"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    USER = "user"

@dataclass
class Role:
    """角色数据类"""
    id: Optional[str] = None
    name: str = ""
    code: str = ""
    description: str = ""
    role_type: RoleType = RoleType.USER
    is_system: bool = False
    tenant_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Permission:
    """权限数据类"""
    id: Optional[str] = None
    name: str = ""
    code: str = ""
    description: str = ""
    resource_type: ResourceType = ResourceType.SYSTEM
    permission_type: PermissionType = PermissionType.READ
    is_system: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class UserRole:
    """用户角色关联数据类"""
    id: Optional[str] = None
    user_id: str = ""
    role_id: str = ""
    resource_type: Optional[ResourceType] = None
    resource_id: Optional[str] = None
    granted_by: Optional[str] = None
    granted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    tenant_id: Optional[str] = None

@dataclass
class RolePermission:
    """角色权限关联数据类"""
    id: Optional[str] = None
    role_id: str = ""
    permission_id: str = ""
    is_active: bool = True
    created_at: Optional[datetime] = None

@dataclass
class PermissionCheck:
    """权限检查结果数据类"""
    has_permission: bool = False
    user_id: str = ""
    resource_type: ResourceType = ResourceType.SYSTEM
    resource_id: str = ""
    permission_type: PermissionType = PermissionType.READ
    granted_roles: List[str] = None
    reason: str = ""
    
    def __post_init__(self):
        if self.granted_roles is None:
            self.granted_roles = []

@dataclass
class TeamRole:
    """团队角色映射"""
    id: Optional[str] = None
    team_id: str = ""  # 团队ID (tenant_id)
    role_code: str = ""  # 角色代码
    resource_type: Optional[ResourceType] = None  # 资源类型
    resource_id: Optional[str] = None  # 资源ID
    tenant_id: str = "default"  # 租户ID
    granted_by: Optional[str] = None  # 授权者
    granted_at: Optional[str] = None  # 授权时间
    expires_at: Optional[str] = None  # 过期时间
    is_active: bool = True  # 是否激活

# 预定义的系统角色和权限
SYSTEM_ROLES = {
    RoleType.SUPER_ADMIN: {
        "name": "超级管理员",
        "description": "拥有系统所有权限",
        "permissions": [p for p in PermissionType]
    },
    RoleType.ADMIN: {
        "name": "管理员",
        "description": "拥有租户内所有权限",
        "permissions": [PermissionType.READ, PermissionType.WRITE, PermissionType.DELETE, PermissionType.SHARE, PermissionType.ADMIN]
    },
    RoleType.EDITOR: {
        "name": "编辑者",
        "description": "可以读取、编辑和分享资源",
        "permissions": [PermissionType.READ, PermissionType.WRITE, PermissionType.SHARE]
    },
    RoleType.VIEWER: {
        "name": "查看者",
        "description": "只能查看资源",
        "permissions": [PermissionType.READ]
    },
    RoleType.USER: {
        "name": "用户",
        "description": "基础用户权限",
        "permissions": [PermissionType.READ]
    }
}

SYSTEM_PERMISSIONS = {
    # 知识库权限
    "kb_read": {
        "name": "查看知识库",
        "code": "kb_read",
        "resource_type": ResourceType.KNOWLEDGEBASE,
        "permission_type": PermissionType.READ
    },
    "kb_write": {
        "name": "编辑知识库",
        "code": "kb_write",
        "resource_type": ResourceType.KNOWLEDGEBASE,
        "permission_type": PermissionType.WRITE
    },
    "kb_delete": {
        "name": "删除知识库",
        "code": "kb_delete",
        "resource_type": ResourceType.KNOWLEDGEBASE,
        "permission_type": PermissionType.DELETE
    },
    "kb_admin": {
        "name": "管理知识库",
        "code": "kb_admin",
        "resource_type": ResourceType.KNOWLEDGEBASE,
        "permission_type": PermissionType.ADMIN
    },
    "kb_share": {
        "name": "分享知识库",
        "code": "kb_share",
        "resource_type": ResourceType.KNOWLEDGEBASE,
        "permission_type": PermissionType.SHARE
    },
    # 文档权限
    "doc_read": {
        "name": "查看文档",
        "code": "doc_read",
        "resource_type": ResourceType.DOCUMENT,
        "permission_type": PermissionType.READ
    },
    "doc_write": {
        "name": "编辑文档",
        "code": "doc_write",
        "resource_type": ResourceType.DOCUMENT,
        "permission_type": PermissionType.WRITE
    },
    "doc_delete": {
        "name": "删除文档",
        "code": "doc_delete",
        "resource_type": ResourceType.DOCUMENT,
        "permission_type": PermissionType.DELETE
    },
    # 团队权限
    "team_read": {
        "name": "查看团队",
        "code": "team_read",
        "resource_type": ResourceType.TEAM,
        "permission_type": PermissionType.READ
    },
    "team_admin": {
        "name": "管理团队",
        "code": "team_admin",
        "resource_type": ResourceType.TEAM,
        "permission_type": PermissionType.ADMIN
    }
}

# 权限控制配置
RBAC_CONFIG = {
    # 受限角色：非超级管理员不能分配的角色列表
    "RESTRICTED_ROLES": ["admin"],

    # 角色层级：定义角色的权限层级（将来可扩展）
    "ROLE_HIERARCHY": {
        "super_admin": ["admin", "editor", "viewer", "user"],
        "admin": ["editor", "viewer", "user"],
        "editor": ["viewer", "user"],
        "viewer": ["user"],
        "user": []
    }
}