from flask import jsonify, request, g
from services.teams.service import (
    get_teams_with_pagination, get_team_by_id, create_team, delete_team,
    get_team_members, remove_team_member
)
from services.rbac.permission_service import permission_service
from models.rbac_models import ResourceType, RoleType
from .. import teams_bp

@teams_bp.route('', methods=['GET'])
def get_teams():
    """获取团队列表的API端点，支持分页和条件查询"""
    try:
        # 获取查询参数
        current_page = int(request.args.get('current_page', request.args.get('currentPage', 1)))
        page_size = int(request.args.get('size', 10))
        team_name = request.args.get('name', '')
        
        # 调用服务函数获取分页和筛选后的团队数据
        current_user_id = getattr(g, 'current_user_id', None)
        user_role = getattr(g, 'current_user_role', None)
        teams, total = get_teams_with_pagination(current_page, page_size, team_name, current_user_id, user_role)
        
        # 返回符合前端期望格式的数据
        return jsonify({
            "code": 0,
            "data": {
                "list": teams,
                "total": total
            },
            "message": "获取团队列表成功"
        })
    except Exception as e:
        # 错误处理
        return jsonify({
            "code": 500,
            "message": f"获取团队列表失败: {str(e)}"
        }), 500

@teams_bp.route('/<string:team_id>', methods=['GET'])
def get_team(team_id):
    """获取单个团队详情的API端点"""
    try:
        team = get_team_by_id(team_id)
        if team:
            return jsonify({
                "code": 0,
                "data": team,
                "message": "获取团队详情成功"
            })
        else:
            return jsonify({
                "code": 404,
                "message": f"团队 {team_id} 不存在"
            }), 404
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取团队详情失败: {str(e)}"
        }), 500

@teams_bp.route('', methods=['POST'])
def create_team_route():
    """创建团队的API端点"""
    try:
        data = request.json
        if not data:
            return jsonify({
                "code": 400,
                "message": "请求数据不能为空"
            }), 400
        
        # 获取当前用户信息
        current_user_id = getattr(g, 'current_user_id', None)
        if not current_user_id:
            return jsonify({"code": 401, "message": "未授权访问"}), 401
        
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return jsonify({
                "code": 400,
                "message": "团队名称不能为空"
            }), 400
        
        team_id = create_team(name=name, owner_id=current_user_id, description=description, created_by=current_user_id)
        
        if team_id:
            return jsonify({
                "code": 0,
                "data": {"id": team_id},
                "message": "团队创建成功"
            })
        else:
            return jsonify({
                "code": 500,
                "message": "创建团队失败"
            }), 500
            
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"创建团队失败: {str(e)}"
        }), 500

@teams_bp.route('/<string:team_id>', methods=['DELETE'])
def delete_team_route(team_id):
    """删除团队的API端点"""
    try:
        success = delete_team(team_id)
        if success:
            return jsonify({
                "code": 0,
                "message": f"团队 {team_id} 删除成功"
            })
        else:
            return jsonify({
                "code": 404,
                "message": f"团队 {team_id} 不存在或删除失败"
            }), 404
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"删除团队失败: {str(e)}"
        }), 500

@teams_bp.route('/<string:team_id>/members', methods=['GET'])
def get_team_members_route(team_id):
    """获取团队成员的API端点"""
    try:
        print(f"正在查询团队 {team_id} 的成员")
        members = get_team_members(team_id)
        print(f"查询结果: 找到 {len(members)} 个成员")
        
        return jsonify({
            "code": 0,
            "data": members,
            "message": "获取团队成员成功"
        })
    except Exception as e:
        print(f"获取团队成员异常: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取团队成员失败: {str(e)}"
        }), 500

@teams_bp.route('/<string:team_id>/members/<string:user_id>', methods=['DELETE'])
def remove_team_member_route(team_id, user_id):
    """移除团队成员的API端点"""
    try:
        success = remove_team_member(team_id, user_id)
        if success:
            return jsonify({
                "code": 0,
                "message": "移除团队成员成功"
            })
        else:
            return jsonify({
                "code": 400,
                "message": "移除团队成员失败"
            }), 400
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"移除团队成员失败: {str(e)}"
        }), 500


@teams_bp.route('/<string:team_id>/roles', methods=['GET'])
def get_team_roles_route(team_id):
    """获取团队角色列表"""
    try:
        roles = permission_service.get_team_roles(team_id)
        
        # 序列化角色数据
        serialized_roles = []
        for role in roles:
            serialized_role = {
                "id": role.id,
                "team_id": role.team_id,
                "role_code": role.role_code,
                "resource_type": role.resource_type.value if role.resource_type else None,
                "resource_id": role.resource_id,
                "tenant_id": role.tenant_id,
                "granted_by": role.granted_by,
                "granted_at": role.granted_at,
                "expires_at": role.expires_at,
                "is_active": role.is_active
            }
            serialized_roles.append(serialized_role)
        
        return jsonify({
            "code": 0,
            "data": serialized_roles,
            "message": "获取团队角色成功"
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取团队角色失败: {str(e)}"
        }), 500


@teams_bp.route('/<string:team_id>/roles', methods=['POST'])
def grant_team_role_route(team_id):
    """为团队分配角色"""
    try:
        data = request.get_json()
        role_code = data.get('role_code')
        resource_type = data.get('resource_type')
        resource_id = data.get('resource_id')
        tenant_id = data.get('tenant_id')
        granted_by = data.get('granted_by')
        expires_at = data.get('expires_at')
        
        if not all([role_code, resource_type, granted_by]):
            return jsonify({
                "code": 400,
                "message": "缺少必要参数: role_code, resource_type, granted_by"
            }), 400
        
        success = permission_service.grant_team_role(
            team_id=team_id,
            role_code=role_code,
            resource_type=ResourceType(resource_type),
            resource_id=resource_id,
            tenant_id=tenant_id,
            granted_by=granted_by
        )
        
        if success:
            return jsonify({
                "code": 0,
                "message": "团队角色分配成功"
            })
        else:
            return jsonify({
                "code": 400,
                "message": "团队角色分配失败"
            }), 400
            
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"团队角色分配失败: {str(e)}"
        }), 500


@teams_bp.route('/<string:team_id>/roles', methods=['DELETE'])
def revoke_team_role_route(team_id):
    """撤销团队角色"""
    try:
        data = request.get_json()
        role_code = data.get('role_code')
        resource_type = data.get('resource_type')
        resource_id = data.get('resource_id')
        tenant_id = data.get('tenant_id')
        
        if not all([role_code, resource_type]):
            return jsonify({
                "code": 400,
                "message": "缺少必要参数: role_code, resource_type"
            }), 400
        
        success = permission_service.revoke_team_role(
            team_id=team_id,
            role_code=role_code,
            resource_type=ResourceType(resource_type),
            resource_id=resource_id,
            tenant_id=tenant_id
        )
        
        if success:
            return jsonify({
                "code": 0,
                "message": "团队角色撤销成功"
            })
        else:
            return jsonify({
                "code": 400,
                "message": "团队角色撤销失败"
            }), 400
            
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"团队角色撤销失败: {str(e)}"
        }), 500

