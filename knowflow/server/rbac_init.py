#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC权限管理系统初始化模块
集成到主服务，自动创建表结构和默认管理员账户
"""

import logging
from datetime import datetime
from typing import List, Dict, Any
import hashlib
import uuid
from database import get_db_connection
from models.rbac_models import SYSTEM_ROLES, SYSTEM_PERMISSIONS, RoleType, PermissionType, ResourceType

logger = logging.getLogger(__name__)

class RBACInitializer:
    """
    RBAC权限管理系统初始化器
    """
    
    def __init__(self):
        self.db = None
        self.cursor = None
    
    def _get_db_connection(self):
        """获取数据库连接"""
        if not self.db:
            try:
                self.db = get_db_connection()
                self.db.autocommit = True
                self.cursor = self.db.cursor()
            except Exception as e:
                logger.error(f"数据库连接失败: {e}")
                raise
        return self.db
    
    def initialize(self):
        """
        执行完整的RBAC系统初始化
        
        Returns:
            bool: 是否成功初始化
        """
        try:
            logger.info("开始RBAC权限管理系统初始化...")
            
            # 获取数据库连接
            self._get_db_connection()
            
            # 检查是否已经初始化
            if self._is_rbac_initialized():
                logger.info("RBAC系统已初始化，跳过")
                return True
            
            # 1. 创建权限相关表
            self._create_tables()
            
            # 2. 插入系统权限
            self._insert_system_permissions()
            
            # 3. 插入系统角色
            self._insert_system_roles()
            
            # 4. 建立角色权限关联
            self._setup_role_permissions()
            
            # 5. 创建默认超级管理员账户
            self._create_default_admin()
            
            # 6. 创建团队角色表
            self._create_team_roles_table()
            
            # 7. 验证初始化结果
            self._verify_initialization()
            
            logger.info("RBAC权限管理系统初始化完成！")
            return True
            
        except Exception as e:
            logger.error(f"RBAC初始化失败: {e}")
            if self.db:
                self.db.rollback()
            return False
        finally:
            self._close_connection()
    
    def _is_rbac_initialized(self):
        """检查RBAC是否已经初始化"""
        try:
            # 确保有数据库连接
            if not self.db or not self.cursor:
                self._get_db_connection()
            
            # 检查核心表是否存在且有数据
            self.cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = DATABASE() AND table_name = 'rbac_roles'
            """)
            table_exists = self.cursor.fetchone()[0] > 0
            
            if not table_exists:
                return False
            
            # 检查是否有系统角色数据
            self.cursor.execute("SELECT COUNT(*) FROM rbac_roles WHERE is_system = 1")
            roles_count = self.cursor.fetchone()[0]
            
            return roles_count > 0
            
        except Exception as e:
            logger.debug(f"RBAC初始化检查失败: {e}")
            return False
    
    def _create_tables(self):
        """创建RBAC相关数据表"""
        logger.info("创建RBAC数据表...")
        
        # RBAC权限表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL COMMENT '权限名称',
                code VARCHAR(50) NOT NULL UNIQUE COMMENT '权限代码',
                description TEXT COMMENT '权限描述',
                resource_type ENUM('knowledgebase', 'document', 'team', 'user', 'system') NOT NULL COMMENT '资源类型',
                permission_type ENUM('read', 'write', 'delete', 'admin', 'share', 'export') NOT NULL COMMENT '权限类型',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_resource_type (resource_type),
                INDEX idx_permission_type (permission_type),
                INDEX idx_code (code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC权限表'
        """)
        
        # RBAC角色表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL COMMENT '角色名称',
                code VARCHAR(50) NOT NULL COMMENT '角色代码',
                description TEXT COMMENT '角色描述',
                role_type ENUM('super_admin', 'admin', 'editor', 'viewer', 'user') NOT NULL COMMENT '角色类型',
                is_system BOOLEAN DEFAULT FALSE COMMENT '是否为系统角色',
                tenant_id VARCHAR(50) NULL COMMENT '租户ID',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_code_tenant (code, tenant_id),
                INDEX idx_role_type (role_type),
                INDEX idx_tenant_id (tenant_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC角色表'
        """)
        
        # RBAC用户角色关联表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_user_roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL COMMENT '用户ID',
                role_id INT NOT NULL COMMENT '角色ID',
                tenant_id VARCHAR(50) NULL COMMENT '租户ID',
                resource_type ENUM('knowledgebase', 'document', 'team', 'user', 'system') NULL COMMENT '资源类型',
                resource_id VARCHAR(50) NULL COMMENT '资源ID',
                granted_by VARCHAR(50) NULL COMMENT '授权人',
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '授权时间',
                expires_at TIMESTAMP NULL COMMENT '过期时间',
                is_active BOOLEAN DEFAULT TRUE COMMENT '是否有效',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES rbac_roles(id) ON DELETE CASCADE,
                INDEX idx_user_id (user_id),
                INDEX idx_role_id (role_id),
                INDEX idx_tenant_id (tenant_id),
                INDEX idx_resource (resource_type, resource_id),
                INDEX idx_active_expires (is_active, expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC用户角色关联表'
        """)
        
        # RBAC角色权限关联表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_role_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                role_id INT NOT NULL COMMENT '角色ID',
                permission_id INT NOT NULL COMMENT '权限ID',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES rbac_roles(id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES rbac_permissions(id) ON DELETE CASCADE,
                UNIQUE KEY uk_role_permission (role_id, permission_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC角色权限关联表'
        """)
        
        # RBAC资源权限表（用于直接授权）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_resource_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                resource_type ENUM('knowledgebase', 'document', 'team', 'user', 'system') NOT NULL COMMENT '资源类型',
                resource_id VARCHAR(50) NOT NULL COMMENT '资源ID',
                user_id VARCHAR(50) NOT NULL COMMENT '用户ID',
                permission_type ENUM('read', 'write', 'delete', 'admin', 'share', 'export') NOT NULL COMMENT '权限类型',
                granted_by VARCHAR(50) NULL COMMENT '授权人',
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '授权时间',
                expires_at TIMESTAMP NULL COMMENT '过期时间',
                is_active BOOLEAN DEFAULT TRUE COMMENT '是否有效',
                tenant_id VARCHAR(50) NULL COMMENT '租户ID',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_resource (resource_type, resource_id),
                INDEX idx_user_id (user_id),
                INDEX idx_permission_type (permission_type),
                INDEX idx_tenant_id (tenant_id),
                INDEX idx_active_expires (is_active, expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC资源权限表'
        """)
        
        self.db.commit()
        logger.info("RBAC数据表创建完成")
    
    def _create_team_roles_table(self):
        """创建团队角色表"""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS rbac_team_roles (
                    id VARCHAR(32) PRIMARY KEY COMMENT '主键ID',
                    team_id VARCHAR(32) NOT NULL COMMENT '团队ID',
                    role_code VARCHAR(50) NOT NULL COMMENT '角色代码',
                    resource_type ENUM('knowledgebase', 'document', 'team', 'user', 'system') NULL COMMENT '资源类型',
                    resource_id VARCHAR(50) NULL COMMENT '资源ID',
                    tenant_id VARCHAR(50) NOT NULL DEFAULT 'default' COMMENT '租户ID',
                    granted_by VARCHAR(50) NULL COMMENT '授权人',
                    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '授权时间',
                    expires_at TIMESTAMP NULL COMMENT '过期时间',
                    is_active BOOLEAN DEFAULT TRUE COMMENT '是否有效',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_team_id (team_id),
                    INDEX idx_role_code (role_code),
                    INDEX idx_resource (resource_type, resource_id),
                    INDEX idx_tenant_id (tenant_id),
                    INDEX idx_active_expires (is_active, expires_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC团队角色关联表'
            """)
            logger.info("团队角色表创建完成")
        except Exception as e:
            logger.error(f"创建团队角色表失败: {e}")
    
    def _insert_system_permissions(self):
        """插入系统权限"""
        logger.info("插入系统权限...")
        
        for perm_code, perm_data in SYSTEM_PERMISSIONS.items():
            try:
                self.cursor.execute("""
                    INSERT IGNORE INTO rbac_permissions (name, code, description, resource_type, permission_type)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    perm_data['name'],
                    perm_data['code'],
                    perm_data.get('description', ''),
                    perm_data['resource_type'].value,
                    perm_data['permission_type'].value
                ))
                
                if self.cursor.rowcount > 0:
                    logger.info(f"插入权限: {perm_data['name']} ({perm_code})")
                    
            except Exception as e:
                logger.error(f"插入权限失败 {perm_code}: {e}")
        
        self.db.commit()
        logger.info("系统权限插入完成")
    
    def _insert_system_roles(self):
        """插入系统角色"""
        logger.info("插入系统角色...")
        
        for role_type, role_data in SYSTEM_ROLES.items():
            try:
                self.cursor.execute("""
                    INSERT IGNORE INTO rbac_roles (name, code, description, role_type, is_system)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    role_data['name'],
                    role_type.value,
                    role_data['description'],
                    role_type.value,
                    True
                ))
                
                if self.cursor.rowcount > 0:
                    logger.info(f"插入角色: {role_data['name']} ({role_type.value})")
                    
            except Exception as e:
                logger.error(f"插入角色失败 {role_type.value}: {e}")
        
        self.db.commit()
        logger.info("系统角色插入完成")
    
    def _setup_role_permissions(self):
        """建立角色权限关联"""
        logger.info("建立角色权限关联...")
        
        # 先获取所有角色和权限的映射
        self.cursor.execute("SELECT id, code FROM rbac_roles")
        roles_map = {code: role_id for role_id, code in self.cursor.fetchall()}
        
        self.cursor.execute("SELECT id, code FROM rbac_permissions")
        permissions_map = {code: perm_id for perm_id, code in self.cursor.fetchall()}
        
        for role_type, role_data in SYSTEM_ROLES.items():
            try:
                if role_type.value not in roles_map:
                    continue
                
                role_id = roles_map[role_type.value]
                permissions = role_data['permissions']
                
                for perm_type in permissions:
                    # 为每种资源类型创建权限关联
                    for resource_type in ResourceType:
                        # 构造权限代码
                        if resource_type == ResourceType.KNOWLEDGEBASE:
                            perm_code = f"kb_{perm_type.value}"
                        elif resource_type == ResourceType.DOCUMENT:
                            perm_code = f"doc_{perm_type.value}"
                        elif resource_type == ResourceType.TEAM:
                            perm_code = f"team_{perm_type.value}"
                        else:
                            continue
                        
                        if perm_code in permissions_map:
                            perm_id = permissions_map[perm_code]
                            
                            # 插入角色权限关联
                            self.cursor.execute("""
                                INSERT IGNORE INTO rbac_role_permissions (role_id, permission_id)
                                VALUES (%s, %s)
                            """, (role_id, perm_id))
                
                logger.info(f"角色 {role_type.value} 权限关联完成")
                
            except Exception as e:
                logger.error(f"建立角色权限关联失败 {role_type.value}: {e}")
        
        self.db.commit()
        logger.info("角色权限关联建立完成")
    
    def _create_admin_tenant(self, admin_user_id, admin_email):
        """为管理员创建租户记录"""
        try:
            # 检查是否已存在该租户
            self.cursor.execute("SELECT id FROM tenant WHERE id = %s", (admin_user_id,))
            existing_tenant = self.cursor.fetchone()
            
            if existing_tenant:
                logger.info(f"管理员租户已存在: {admin_user_id}")
            else:
                # 创建租户记录
                current_time = datetime.now()
                create_time = int(current_time.timestamp() * 1000)
                create_date = current_time.strftime("%Y-%m-%d %H:%M:%S")
                
                self.cursor.execute("""
                    INSERT INTO tenant (
                        id, name, llm_id, embd_id, asr_id, img2txt_id, rerank_id,
                        parser_ids, credit, status, create_time, create_date, update_time, update_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    admin_user_id, '系统管理员', 'qwen-plus', 'BAAI/bge-large-zh-v1.5', 'local',
                    'local', 'BAAI/bge-reranker-v2-m3', 'naive:General,qa:Q&A,resume:Resume,manual:Manual,table:Table,paper:Paper,book:Book,laws:Laws,presentation:Presentation,picture:Picture,one:One,audio:Audio,email:Email,tag:Tag,smart:Smart,regex:Regex,parent_child:Parent-Child,title:Title',
                    1000000, '1', create_time, create_date, create_time, create_date
                ))
                
                logger.info(f"创建管理员租户: {admin_user_id}")
                
            # 创建用户-租户关联记录
            self.cursor.execute("SELECT id FROM user_tenant WHERE user_id = %s AND tenant_id = %s", 
                               (admin_user_id, admin_user_id))
            existing_user_tenant = self.cursor.fetchone()
            
            if not existing_user_tenant:
                current_time = datetime.now()
                create_time = int(current_time.timestamp() * 1000)
                create_date = current_time.strftime("%Y-%m-%d %H:%M:%S")
                
                user_tenant_id = str(uuid.uuid4()).replace('-', '')
                self.cursor.execute("""
                    INSERT INTO user_tenant (
                        id, user_id, tenant_id, role, invited_by, status,
                        create_time, create_date, update_time, update_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_tenant_id, admin_user_id, admin_user_id, 'owner', admin_user_id, '1',
                    create_time, create_date, create_time, create_date
                ))
                
                logger.info(f"创建用户-租户关联: {admin_user_id}")
            else:
                logger.info(f"用户-租户关联已存在: {admin_user_id}")
                
        except Exception as e:
            logger.error(f"创建管理员租户失败: {e}")
            raise

    def _create_default_admin(self):
        """创建默认超级管理员账户"""
        logger.info("创建默认超级管理员账户...")
        
        try:
            admin_email = "admin@gmail.com"
            admin_password = "admin"
            admin_nickname = "系统管理员"
            
            # 检查是否已存在该用户
            self.cursor.execute("SELECT id FROM user WHERE email = %s", (admin_email,))
            existing_user = self.cursor.fetchone()
            
            if existing_user:
                admin_user_id = existing_user[0]
                logger.info(f"管理员用户已存在: {admin_email} (ID: {admin_user_id})")
            else:
                # 创建管理员用户
                admin_user_id = str(uuid.uuid4()).replace('-', '')
                current_time = datetime.now()
                create_time = int(current_time.timestamp() * 1000)
                create_date = current_time.strftime("%Y-%m-%d %H:%M:%S")
                
                # 使用系统的密码加密方法
                import base64
                from werkzeug.security import generate_password_hash
                base64_password = base64.b64encode(admin_password.encode()).decode()
                hashed_password = generate_password_hash(base64_password)
                
                self.cursor.execute("""
                    INSERT INTO user (
                        id, email, nickname, password, 
                        create_time, create_date, update_time, update_date,
                        status, is_superuser, is_authenticated, is_active, is_anonymous
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    admin_user_id, admin_email, admin_nickname, hashed_password,
                    create_time, create_date, create_time, create_date,
                    '1', 1, '1', '1', '0'  # status, is_superuser, is_authenticated, is_active, is_anonymous
                ))
                
                logger.info(f"创建管理员用户: {admin_email} (ID: {admin_user_id})")
            
            # 创建管理员对应的租户记录
            self._create_admin_tenant(admin_user_id, admin_email)
            
            # 为管理员分配super_admin角色
            self.cursor.execute("SELECT id FROM rbac_roles WHERE code = 'super_admin'")
            super_admin_role = self.cursor.fetchone()
            
            if super_admin_role:
                role_id = super_admin_role[0]
                
                # 检查是否已分配角色
                self.cursor.execute("""
                    SELECT id FROM rbac_user_roles 
                    WHERE user_id = %s AND role_id = %s AND is_active = 1
                """, (admin_user_id, role_id))
                
                if not self.cursor.fetchone():
                    # 分配super_admin角色
                    self.cursor.execute("""
                        INSERT INTO rbac_user_roles 
                        (user_id, role_id, tenant_id, granted_by, granted_at, is_active)
                        VALUES (%s, %s, 'default', 'system', NOW(), 1)
                    """, (admin_user_id, role_id))
                    
                    logger.info(f"为管理员 {admin_email} 分配super_admin角色")
                else:
                    logger.info(f"管理员 {admin_email} 已有super_admin角色")
            
            self.db.commit()
            logger.info(f"默认管理员账户设置完成: {admin_email} / {admin_password}")
            
        except Exception as e:
            logger.error(f"创建默认管理员账户失败: {e}")
            raise
    
    def _verify_initialization(self):
        """验证初始化结果"""
        logger.info("验证初始化结果...")
        
        try:
            # 统计各表记录数
            tables = ['rbac_permissions', 'rbac_roles', 'rbac_user_roles', 'rbac_role_permissions']
            for table in tables:
                try:
                    self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = self.cursor.fetchone()[0]
                    logger.info(f"{table} 表记录数: {count}")
                except Exception as e:
                    logger.warning(f"统计表 {table} 记录数失败: {e}")
            
            # 验证默认管理员
            try:
                self.cursor.execute("""
                    SELECT u.email, r.name as role_name 
                    FROM user u
                    JOIN rbac_user_roles ur ON u.id = ur.user_id
                    JOIN rbac_roles r ON ur.role_id = r.id
                    WHERE u.email = 'admin@gmail.com' AND ur.is_active = 1
                """)
                admin_info = self.cursor.fetchone()
                if admin_info:
                    logger.info(f"默认管理员验证成功: {admin_info[0]} ({admin_info[1]})")
                else:
                    logger.warning("默认管理员验证失败")
            except Exception as e:
                logger.warning(f"验证默认管理员失败: {e}")
            
            logger.info("初始化结果验证完成")
            
        except Exception as e:
            logger.error(f"验证初始化结果失败: {e}")
    
    def _close_connection(self):
        """关闭数据库连接"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.db:
                self.db.close()
        except Exception:
            pass

# 全局初始化函数
def initialize_rbac_system():
    """
    初始化RBAC权限管理系统
    
    Returns:
        bool: 是否成功初始化
    """
    try:
        initializer = RBACInitializer()
        return initializer.initialize()
    except Exception as e:
        logger.error(f"RBAC系统初始化失败: {e}")
        return False

if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 直接执行初始化
    success = initialize_rbac_system()
    if success:
        print("✓ RBAC系统初始化成功")
    else:
        print("✗ RBAC系统初始化失败")