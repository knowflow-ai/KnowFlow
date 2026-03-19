import mysql.connector
from datetime import datetime
from utils import generate_uuid
from database import DB_CONFIG


def get_teams_with_pagination(current_page, page_size, name='', current_user_id=None, user_role=None):
    """查询团队信息，支持分页和条件筛选"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 构建WHERE子句和参数
        where_clauses = []
        params = []
        
        if name:
            where_clauses.append("t.name LIKE %s")
            params.append(f"%{name}%")
        
        # 添加基于角色的权限过滤
        if current_user_id and user_role:
            if user_role == 'admin':
                # 管理员只能看到自己创建的团队
                where_clauses.append("t.created_by = %s")
                params.append(current_user_id)
            elif user_role == 'user':
                # 普通用户只能看到自己参与的团队
                where_clauses.append("""
                    EXISTS (
                        SELECT 1 FROM user_tenant ut 
                        WHERE ut.tenant_id = t.id AND ut.user_id = %s AND ut.status = 1
                    )
                """)
                params.append(current_user_id)
            # super_admin 不添加过滤条件，可以看到所有团队
        
        # 组合WHERE子句
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # 查询总记录数，排除个人租户
        count_sql = f"""
        SELECT COUNT(*) as total
        FROM tenant t
        WHERE {where_sql}
        AND NOT EXISTS (
            SELECT 1 FROM user u
            WHERE u.id = t.id
        )
        """
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']
        
        # 计算分页偏移量
        offset = (current_page - 1) * page_size
        
        # 执行分页查询，包含负责人信息和成员数量，排除个人租户
        query = f"""
        SELECT
            t.id,
            t.name,
            t.create_date,
            t.update_date,
            t.status,
            (SELECT u.nickname FROM user_tenant ut JOIN user u ON ut.user_id = u.id
            WHERE ut.tenant_id = t.id AND ut.role = 'owner' LIMIT 1) as owner_name,
            (SELECT COUNT(*) FROM user_tenant ut WHERE ut.tenant_id = t.id AND ut.status = 1) as member_count
        FROM
            tenant t
        WHERE
            {where_sql}
            AND NOT EXISTS (
                SELECT 1 FROM user u
                WHERE u.id = t.id
            )
        ORDER BY
            t.create_date DESC
        LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [page_size, offset])
        results = cursor.fetchall()
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        # 格式化结果
        formatted_teams = []
        for team in results:
            owner_name = team["owner_name"] if team["owner_name"] else "未指定"
            formatted_teams.append({
                "id": team["id"],
                # 修复：使用实际的团队名称，而不是“负责人的团队”
                "name": team["name"],
                "ownerName": owner_name,
                "memberCount": team["member_count"],
                "createTime": team["create_date"].strftime("%Y-%m-%d %H:%M:%S") if team["create_date"] else "",
                "updateTime": team["update_date"].strftime("%Y-%m-%d %H:%M:%S") if team["update_date"] else "",
                "status": team["status"]
            })
        
        return formatted_teams, total
        
    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return [], 0


def get_team_by_id(team_id):
    """根据ID获取团队详情"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT id, name, create_date, update_date, status, credit
        FROM tenant
        WHERE id = %s
        """
        cursor.execute(query, (team_id,))
        team = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if team:
            return {
                "id": team["id"],
                "name": team["name"],
                "createTime": team["create_date"].strftime("%Y-%m-%d %H:%M:%S") if team["create_date"] else "",
                "updateTime": team["update_date"].strftime("%Y-%m-%d %H:%M:%S") if team["update_date"] else "",
                "status": team["status"],
                "credit": team["credit"]
            }
        return None
        
    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return None


def create_team(name, owner_id, description="", created_by=None):
    """创建新团队"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 查询超级管理员的配置作为默认值
        admin_query = """
        SELECT t.llm_id, t.embd_id, t.asr_id, t.img2txt_id, t.rerank_id, t.tts_id, t.parser_ids
        FROM tenant t
        JOIN user u ON t.id = u.id
        WHERE u.is_superuser = 1 OR u.email = 'admin@gmail.com'
        ORDER BY u.create_time ASC
        LIMIT 1
        """
        cursor.execute(admin_query)
        admin_config = cursor.fetchone()

        # 如果没有找到超级管理员配置，使用默认值
        if not admin_config:
            default_parser_ids = "naive:General,qa:Q&A,resume:Resume,manual:Manual,table:Table,paper:Paper,book:Book,laws:Laws,presentation:Presentation,picture:Picture,one:One,audio:Audio,email:Email,tag:Tag,smart:Smart"
            admin_config = {
                'llm_id': '',
                'embd_id': '',
                'asr_id': '',
                'img2txt_id': '',
                'rerank_id': '',
                'tts_id': '',
                'parser_ids': default_parser_ids
            }

        # 生成团队ID
        team_id = generate_uuid()
        current_datetime = datetime.now()
        create_time = int(current_datetime.timestamp() * 1000)
        current_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

        # 创建团队记录，继承超级管理员的配置
        team_query = """
        INSERT INTO tenant (
            id, name, create_time, create_date, update_time, update_date,
            status, credit, llm_id, embd_id, asr_id, img2txt_id, rerank_id, tts_id, parser_ids, created_by
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """
        team_data = (
            team_id, name, create_time, current_date, create_time, current_date,
            '1', 0,
            admin_config['llm_id'] or '',
            admin_config['embd_id'] or '',
            admin_config['asr_id'] or '',
            admin_config['img2txt_id'] or '',
            admin_config['rerank_id'] or '',
            admin_config['tts_id'] or '',
            admin_config['parser_ids'] or '',
            created_by
        )
        cursor.execute(team_query, team_data)
        
        # 添加创建者为团队所有者
        member_query = """
        INSERT INTO user_tenant (
            id, create_time, create_date, update_time, update_date, user_id,
            tenant_id, role, invited_by, status
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        """
        member_data = (
            generate_uuid(), create_time, current_date, create_time, current_date, owner_id,
            team_id, "owner", "system", 1
        )
        cursor.execute(member_query, member_data)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return team_id
        
    except mysql.connector.Error as err:
        print(f"创建团队数据库错误: {err}")
        print(f"错误代码: {err.errno}")
        print(f"SQL状态: {err.sqlstate}")
        return None
    except Exception as e:
        print(f"创建团队其他错误: {e}")
        return None


def update_team(team_id, name=None, description=None):
    """更新团队信息"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 构建更新字段
        update_fields = []
        params = []
        
        if name is not None:
            update_fields.append("name = %s")
            params.append(name)
            
        if description is not None:
            update_fields.append("description = %s")
            params.append(description)
            
        if not update_fields:
            return False
            
        # 添加更新时间
        current_datetime = datetime.now()
        update_time = int(current_datetime.timestamp() * 1000)
        update_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        
        update_fields.extend(["update_time = %s", "update_date = %s"])
        params.extend([update_time, update_date, team_id])
        
        query = f"UPDATE tenant SET {', '.join(update_fields)} WHERE id = %s"
        cursor.execute(query, params)
        
        affected_rows = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return affected_rows > 0
        
    except mysql.connector.Error as err:
        print(f"更新团队错误: {err}")
        return False


def delete_team(team_id):
    """删除指定ID的团队"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 删除团队成员关联
        member_query = "DELETE FROM user_tenant WHERE tenant_id = %s"
        cursor.execute(member_query, (team_id,))
        
        # 删除团队
        team_query = "DELETE FROM tenant WHERE id = %s"
        cursor.execute(team_query, (team_id,))
        
        affected_rows = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return affected_rows > 0
        
    except mysql.connector.Error as err:
        print(f"删除团队错误: {err}")
        return False


def get_team_members(team_id):
    """获取团队成员列表"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT ut.user_id, u.nickname, u.email, ut.role, ut.create_date
        FROM user_tenant ut
        JOIN user u ON ut.user_id = u.id
        WHERE ut.tenant_id = %s AND ut.status = 1
        ORDER BY ut.create_date DESC
        """
        cursor.execute(query, (team_id,))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # 格式化结果
        formatted_members = []
        for member in results:
            # 将 role 转换为前端需要的格式
            role = "管理员" if member["role"] == "owner" else "普通成员"
            
            formatted_members.append({
                "userId": member["user_id"],
                "username": member["nickname"],
                "role": member["role"],  # 保持原始角色值 "owner" 或 "normal"
                "joinTime": member["create_date"].strftime("%Y-%m-%d %H:%M:%S") if member["create_date"] else ""
            })
        
        return formatted_members
        
    except mysql.connector.Error as err:
        print(f"获取团队成员错误: {err}")
        return []


def add_team_member(team_id, user_id, role="member"):
    """添加团队成员，如果已存在则更新其状态为激活"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 检查是否已存在记录（无论状态如何）
        check_query = """
        SELECT id, status FROM user_tenant 
        WHERE tenant_id = %s AND user_id = %s
        """
        cursor.execute(check_query, (team_id, user_id))
        existing = cursor.fetchone()
        
        current_datetime = datetime.now()
        update_time = int(current_datetime.timestamp() * 1000)
        update_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        
        if existing:
            # 如果存在，更新其状态为1（激活），并更新角色
            update_query = """
            UPDATE user_tenant
            SET status = 1, role = %s, update_time = %s, update_date = %s
            WHERE id = %s
            """
            cursor.execute(update_query, (role, update_time, update_date, existing[0]))
        else:
            # 如果不存在，插入新记录
            insert_query = """
            INSERT INTO user_tenant (
                id, create_time, create_date, update_time, update_date, user_id,
                tenant_id, role, invited_by, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            """
            create_time = update_time
            current_date = update_date
            from utils import generate_uuid
            user_tenant_data = (
                generate_uuid(), create_time, current_date, create_time, current_date, user_id,
                team_id, role, "system", 1
            )
            cursor.execute(insert_query, user_tenant_data)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except mysql.connector.Error as err:
        print(f"添加团队成员错误: {err}")
        return False


def remove_team_member(team_id, user_id):
    """移除团队成员，将其状态设置为0（非激活）"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 更新状态为0（非激活）
        update_query = """
        UPDATE user_tenant
        SET status = 0
        WHERE tenant_id = %s AND user_id = %s
        """
        cursor.execute(update_query, (team_id, user_id))
        
        affected_rows = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return affected_rows > 0
        
    except mysql.connector.Error as err:
        print(f"移除团队成员错误: {err}")
        return False