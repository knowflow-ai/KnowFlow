import mysql.connector
import pytz
from datetime import datetime
from utils import generate_uuid, encrypt_password
from database import DB_CONFIG

def get_users_with_pagination(current_page, page_size, username='', email='', current_user_id=None, user_role=None):
    """查询用户信息，支持分页和条件筛选"""
    try:
        # 建立数据库连接
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 构建WHERE子句和参数
        where_clauses = []
        params = []
        
        if username:
            where_clauses.append("nickname LIKE %s")
            params.append(f"%{username}%")
        
        if email:
            where_clauses.append("email LIKE %s")
            params.append(f"%{email}%")
        
        # 添加基于角色的权限过滤
        if current_user_id and user_role:
            if user_role == 'admin':
                # 管理员只能看到自己创建的用户 + 自己
                where_clauses.append("(created_by = %s OR id = %s)")
                params.extend([current_user_id, current_user_id])
            elif user_role == 'user':
                # 普通用户只能看到自己
                where_clauses.append("id = %s")
                params.append(current_user_id)
            # super_admin 不添加过滤条件，可以看到所有用户
        
        # 组合WHERE子句
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # 查询总记录数
        count_sql = f"SELECT COUNT(*) as total FROM user WHERE {where_sql}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']
        
        # 计算分页偏移量
        offset = (current_page - 1) * page_size
        
        # 执行分页查询
        query = f"""
        SELECT id, nickname, email, create_date, update_date, status, is_superuser
        FROM user
        WHERE {where_sql}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [page_size, offset])
        results = cursor.fetchall()
        
        # 格式化结果
        formatted_users = []
        for user in results:
            formatted_users.append({
                "id": user["id"],
                "username": user["nickname"],
                "email": user["email"],
                "createTime": user["create_date"].strftime("%Y-%m-%d %H:%M:%S") if user["create_date"] else "",
                "updateTime": user["update_date"].strftime("%Y-%m-%d %H:%M:%S") if user["update_date"] else "",
            })
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        return formatted_users, total
        
    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return [], 0

def delete_user(user_id):
    """删除指定ID的用户"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 删除 user 表中的用户记录
        query = "DELETE FROM user WHERE id = %s"
        cursor.execute(query, (user_id,))
        
        # 删除 user_tenant 表中的关联记录
        user_tenant_query = "DELETE FROM user_tenant WHERE user_id = %s"
        cursor.execute(user_tenant_query, (user_id,))

        # 删除 tenant 表中的关联记录
        tenant_query = "DELETE FROM tenant WHERE id = %s"
        cursor.execute(tenant_query, (user_id,))
    
        # 删除 tenant_llm 表中的关联记录
        tenant_llm_query = "DELETE FROM tenant_llm WHERE tenant_id = %s"
        cursor.execute(tenant_llm_query, (user_id,))
    
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
    except mysql.connector.Error as err:
        print(f"删除用户错误: {err}")
        return False

def create_user(user_data, created_by=None):
    """
    创建新用户，并加入超级管理员的团队，并使用超级管理员的模型配置。
    时间将以 UTC+8 (Asia/Shanghai) 存储。
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 检查用户表是否为空
        check_users_query = "SELECT COUNT(*) as user_count FROM user"
        cursor.execute(check_users_query)
        user_count = cursor.fetchone()['user_count']
        
        # 如果有用户，则查询超级管理员的tenant和用户配置
        if user_count > 0:
            # 查询超级管理员的tenant配置
            query_admin_tenant = """
            SELECT t.id, t.llm_id, t.embd_id, t.asr_id, t.img2txt_id, t.rerank_id, t.tts_id, t.parser_ids, t.credit
            FROM tenant t
            JOIN user u ON t.id = u.id 
            WHERE u.is_superuser = 1 OR u.email = 'admin@gmail.com'
            ORDER BY u.create_time ASC
            LIMIT 1
            """
            cursor.execute(query_admin_tenant)
            admin_tenant = cursor.fetchone()
            
            # 查询超级管理员的用户ID
            query_admin_user = """
            SELECT id FROM user 
            WHERE is_superuser = 1 OR email = 'admin@gmail.com'
            ORDER BY create_time ASC
            LIMIT 1
            """
            cursor.execute(query_admin_user)
            admin_user = cursor.fetchone()
            
            # 查询超级管理员的所有tenant_llm配置
            query_admin_user_tenant_llms = """
            SELECT llm_factory, model_type, llm_name, api_key, api_base, max_tokens, used_tokens
            FROM tenant_llm 
            WHERE tenant_id = %s
            """
            cursor.execute(query_admin_user_tenant_llms, (admin_user['id'],))
            admin_user_tenant_llms = cursor.fetchall()
        
        # 开始插入
        user_id = generate_uuid()
        # 获取基本信息
        username = user_data.get("username")
        email = user_data.get("email")
        password = user_data.get("password")
        # 加密密码
        encrypted_password = encrypt_password(password)

        # --- 修改时间获取和格式化逻辑 ---
        # 获取当前 UTC 时间
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        # 定义目标时区 (UTC+8)
        target_tz = pytz.timezone('Asia/Shanghai')
        # 将 UTC 时间转换为目标时区时间
        local_dt = utc_now.astimezone(target_tz)

        # 使用转换后的时间
        create_time = int(local_dt.timestamp() * 1000) # 使用本地化时间戳
        current_date = local_dt.strftime("%Y-%m-%d %H:%M:%S") # 使用本地化时间格式化
        # --- 时间逻辑修改结束 ---

        # 插入用户表
        user_insert_query = """
        INSERT INTO user (
            id, create_time, create_date, update_time, update_date, access_token,
            nickname, password, email, avatar, language, color_schema, timezone,
            last_login_time, is_authenticated, is_active, is_anonymous, login_channel,
            status, is_superuser, created_by
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s
        )
        """
        user_data_tuple = (
            user_id, create_time, current_date, create_time, current_date, None, # 使用修改后的时间
            username, encrypted_password, email, None, "Chinese", "Bright", "UTC+8 Asia/Shanghai",
            current_date, 1, 1, 0, "password", # last_login_time 也使用 UTC+8 时间
            1, 0, created_by
        )
        cursor.execute(user_insert_query, user_data_tuple)

        # 插入租户表
        tenant_insert_query = """
        INSERT INTO tenant (
            id, create_time, create_date, update_time, update_date, name,
            public_key, llm_id, embd_id, asr_id, img2txt_id, rerank_id, tts_id,
            parser_ids, credit, status, created_by
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        """

        if user_count > 0:
            # 如果有现有用户，复制超级管理员的模型配置
            tenant_data = (
                user_id, create_time, current_date, create_time, current_date, username + "'s Kingdom", # 使用修改后的时间
                None, str(admin_tenant['llm_id']), str(admin_tenant['embd_id']),
                str(admin_tenant['asr_id']), str(admin_tenant['img2txt_id']),
                str(admin_tenant['rerank_id']), str(admin_tenant['tts_id']),
                str(admin_tenant['parser_ids']), str(admin_tenant['credit']), 1, created_by
            )
        else:
            # 如果是第一个用户，模型ID使用空字符串
            tenant_data = (
                user_id, create_time, current_date, create_time, current_date, username + "'s Kingdom", # 使用修改后的时间
                None, '', '', '', '', '', '',
                '', "1000", 1, created_by
            )
        cursor.execute(tenant_insert_query, tenant_data)

        # 插入用户租户关系表（owner角色）
        user_tenant_insert_owner_query = """
        INSERT INTO user_tenant (
            id, create_time, create_date, update_time, update_date, user_id,
            tenant_id, role, invited_by, status
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        """
        user_tenant_data_owner = (
            generate_uuid(), create_time, current_date, create_time, current_date, user_id, # 使用修改后的时间
            user_id, "owner", user_id, 1
        )
        cursor.execute(user_tenant_insert_owner_query, user_tenant_data_owner)

        # 只有在存在其他用户时，才加入超级管理员的团队
        if user_count > 0:
            # 插入用户租户关系表（normal角色）
            user_tenant_insert_normal_query = """
            INSERT INTO user_tenant (
                id, create_time, create_date, update_time, update_date, user_id,
                tenant_id, role, invited_by, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            """
            user_tenant_data_normal = (
                generate_uuid(), create_time, current_date, create_time, current_date, user_id, # 使用修改后的时间
                admin_tenant['id'], "normal", admin_tenant['id'], 1
            )
            cursor.execute(user_tenant_insert_normal_query, user_tenant_data_normal)

            # 为新用户复制超级管理员的所有tenant_llm配置
            tenant_llm_insert_query = """
            INSERT INTO tenant_llm (
                create_time, create_date, update_time, update_date, tenant_id,
                llm_factory, model_type, llm_name, api_key, api_base, max_tokens, used_tokens
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            """

            # 遍历超级管理员的所有tenant_llm配置并复制给新用户
            for tenant_llm in admin_user_tenant_llms:
                tenant_llm_data = (
                    create_time, current_date, create_time, current_date, user_id, # 使用修改后的时间
                    str(tenant_llm['llm_factory']), str(tenant_llm['model_type']), str(tenant_llm['llm_name']),
                    str(tenant_llm['api_key']), str(tenant_llm['api_base']), str(tenant_llm['max_tokens']), 0
                )
                cursor.execute(tenant_llm_insert_query, tenant_llm_data)
        
        conn.commit()
        cursor.close()
        conn.close()

        return True
    except mysql.connector.Error as err:
        print(f"创建用户错误: {err}")
        return False

def update_user(user_id, user_data):
    """更新用户信息"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 构建更新字段
        update_fields = []
        params = []

        if user_data.get("username"):
            update_fields.append("nickname = %s")
            params.append(user_data.get("username"))

        if user_data.get("email"):
            update_fields.append("email = %s")
            params.append(user_data.get("email"))

        if not update_fields:
            cursor.close()
            conn.close()
            return True  # 没有字段需要更新

        # 添加更新时间
        update_fields.append("update_time = %s")
        update_fields.append("update_date = %s")

        # 获取当前时间
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        target_tz = pytz.timezone('Asia/Shanghai')
        local_dt = utc_now.astimezone(target_tz)
        update_time = int(local_dt.timestamp() * 1000)
        update_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        params.extend([update_time, update_date])
        params.append(user_id)

        query = f"UPDATE user SET {', '.join(update_fields)} WHERE id = %s"
        cursor.execute(query, params)

        # 检查是否有行被更新
        rows_affected = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        return rows_affected > 0
    except mysql.connector.Error as err:
        print(f"更新用户错误: {err}")
        return False

def reset_user_password(user_id, new_password):
    """
    重置指定用户的密码。
    时间将以 UTC+8 (Asia/Shanghai) 存储。
    Args:
        user_id (str): 用户ID
        new_password (str): 新的明文密码
    Returns:
        bool: 操作是否成功
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 加密新密码
        encrypted_password = encrypt_password(new_password) # 使用与创建用户时相同的加密方法

        # --- 修改时间获取和格式化逻辑 ---
        # 获取当前 UTC 时间
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        # 定义目标时区 (UTC+8)
        target_tz = pytz.timezone('Asia/Shanghai')
        # 将 UTC 时间转换为目标时区时间
        local_dt = utc_now.astimezone(target_tz)

        # 使用转换后的时间
        update_time = int(local_dt.timestamp() * 1000) # 使用本地化时间戳
        update_date = local_dt.strftime("%Y-%m-%d %H:%M:%S") # 使用本地化时间格式化
        # --- 时间逻辑修改结束 ---

        # 更新用户密码
        update_query = """
        UPDATE user
        SET password = %s, update_time = %s, update_date = %s
        WHERE id = %s
        """
        cursor.execute(update_query, (encrypted_password, update_time, update_date, user_id))

        # 检查是否有行被更新
        if cursor.rowcount == 0:
            conn.rollback() # 如果没有更新，回滚
            cursor.close()
            conn.close()
            print(f"用户 {user_id} 未找到，密码未更新。")
            return False # 用户不存在

        conn.commit() # 提交事务
        cursor.close()
        conn.close()
        print(f"用户 {user_id} 密码已成功重置。")
        return True

    except mysql.connector.Error as err:
        print(f"重置密码时数据库错误: {err}")
        # 可以在这里添加更详细的日志记录
        # 如果 conn 存在且打开，尝试回滚
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
            cursor.close()
            conn.close()
        return False
    except Exception as e:
        print(f"重置密码时发生未知错误: {e}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
            cursor.close()
            conn.close()
        return False

def get_assignable_users_with_pagination(current_page, page_size, username='', email='', current_user_id=None, user_role=None):
    """
    查询可分配权限的用户信息（排除超级管理员），支持分页和条件筛选
    超级管理员自动拥有所有权限，不需要单独分配
    """
    try:
        # 建立数据库连接
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 构建WHERE子句和参数
        where_clauses = ["is_superuser != 1"]  # 排除超级管理员
        params = []
        
        if username:
            where_clauses.append("nickname LIKE %s")
            params.append(f"%{username}%")
        
        if email:
            where_clauses.append("email LIKE %s")
            params.append(f"%{email}%")
        
        # 排除拥有super_admin角色的用户
        where_clauses.append("""
            id NOT IN (
                SELECT DISTINCT ur.user_id 
                FROM rbac_user_roles ur 
                JOIN rbac_roles r ON ur.role_id = r.id 
                WHERE r.code = 'super_admin' AND ur.is_active = 1
            )
        """)
        
        # 添加基于角色的权限过滤
        if current_user_id and user_role:
            if user_role == 'admin':
                # 管理员只能看到自己创建的用户 + 自己
                where_clauses.append("(created_by = %s OR id = %s)")
                params.extend([current_user_id, current_user_id])
            elif user_role == 'user':
                # 普通用户只能看到自己
                where_clauses.append("id = %s")
                params.append(current_user_id)
            # super_admin 不添加过滤条件，可以看到所有用户
        
        # 组合WHERE子句
        where_sql = " AND ".join(where_clauses)
        
        # 查询总记录数
        count_sql = f"SELECT COUNT(*) as total FROM user WHERE {where_sql}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']
        
        # 计算分页偏移量
        offset = (current_page - 1) * page_size
        
        # 执行分页查询
        query = f"""
        SELECT id, nickname, email, create_date, update_date, status, is_superuser
        FROM user
        WHERE {where_sql}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [page_size, offset])
        results = cursor.fetchall()
        
        # 格式化结果
        formatted_users = []
        for user in results:
            formatted_users.append({
                "id": user["id"],
                "username": user["nickname"],
                "email": user["email"],
                "createTime": user["create_date"].strftime("%Y-%m-%d %H:%M:%S") if user["create_date"] else "",
                "updateTime": user["update_date"].strftime("%Y-%m-%d %H:%M:%S") if user["update_date"] else "",
            })
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        return formatted_users, total
        
    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return [], 0