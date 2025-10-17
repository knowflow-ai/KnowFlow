from flask import jsonify, request, g
from services.users.service import get_users_with_pagination, delete_user, create_user, update_user, reset_user_password, get_assignable_users_with_pagination
from services.rbac.permission_service import permission_service
from models.rbac_models import ResourceType, PermissionType, RoleType
from .. import users_bp

@users_bp.route('', methods=['GET'])
def get_users():
    """获取用户的API端点,支持分页和条件查询"""
    try:
        # 获取查询参数
        current_page = int(request.args.get('current_page', request.args.get('currentPage', 1)))
        page_size = int(request.args.get('size', 10))
        username = request.args.get('username', '')
        email = request.args.get('email', '')
        
        # 调用服务函数获取分页和筛选后的用户数据
        current_user_id = getattr(g, 'current_user_id', None)
        user_role = getattr(g, 'current_user_role', None)
        users, total = get_users_with_pagination(current_page, page_size, username, email, current_user_id, user_role)
        
        # 返回符合前端期望格式的数据
        return jsonify({
            "code": 0,  # 成功状态码
            "data": {
                "list": users,
                "total": total
            },
            "message": "获取用户列表成功"
        })
    except Exception as e:
        # 错误处理
        return jsonify({
            "code": 500,
            "message": f"获取用户列表失败: {str(e)}"
        }), 500

@users_bp.route('/assignable', methods=['GET'])
def get_assignable_users():
    """获取可分配权限的用户列表（排除超级管理员）"""
    try:
        # 获取查询参数
        current_page = int(request.args.get('current_page', request.args.get('currentPage', 1)))
        page_size = int(request.args.get('size', 10))
        username = request.args.get('username', '')
        email = request.args.get('email', '')
        
        # 调用服务函数获取可分配权限的用户数据
        current_user_id = getattr(g, 'current_user_id', None)
        user_role = getattr(g, 'current_user_role', None)
        users, total = get_assignable_users_with_pagination(current_page, page_size, username, email, current_user_id, user_role)
        
        # 返回符合前端期望格式的数据
        return jsonify({
            "code": 0,  # 成功状态码
            "data": {
                "list": users,
                "total": total
            },
            "message": "获取可分配权限用户列表成功"
        })
    except Exception as e:
        # 错误处理
        return jsonify({
            "code": 500,
            "message": f"获取可分配权限用户列表失败: {str(e)}"
        }), 500

@users_bp.route('/<string:user_id>', methods=['DELETE'])
def delete_user_route(user_id):
    """删除用户的API端点"""
    delete_user(user_id)
    return jsonify({
        "code": 0,
        "message": f"用户 {user_id} 删除成功"
    })

@users_bp.route('', methods=['POST'])
def create_user_route():
    """创建用户的API端点"""
    data = request.json
    # 获取当前用户信息
    current_user_id = getattr(g, 'current_user_id', None)
    if not current_user_id:
        return jsonify({"code": 401, "message": "未授权访问"}), 401
    
    # 创建用户
    try:
        success = create_user(user_data=data, created_by=current_user_id)
        if success:
            return jsonify({
                "code": 0,
                "message": "用户创建成功"
            })
        else:
            return jsonify({
                "code": 400,
                "message": "用户创建失败"
            }), 400
    except ValueError as e:
        # 处理业务逻辑错误（如邮箱重复、参数验证失败等）
        return jsonify({
            "code": 400,
            "message": str(e)
        }), 400
    except Exception as e:
        # 处理系统错误
        return jsonify({
            "code": 500,
            "message": f"用户创建失败: {str(e)}"
        }), 500

@users_bp.route('/<string:user_id>', methods=['PUT'])
def update_user_route(user_id):
    """更新用户的API端点"""
    data = request.json
    success = update_user(user_id=user_id, user_data=data)
    if success:
        return jsonify({
            "code": 0,
            "message": f"用户更新成功"
        })
    else:
        return jsonify({
            "code": 500,
            "message": "用户更新失败"
        }), 500

@users_bp.route('/me', methods=['GET'])
def get_current_user():
    """获取当前登录用户信息"""
    try:
        # 从Flask g对象中获取用户信息
        if not hasattr(g, 'current_user_id') or not g.current_user_id:
            return jsonify({
                "code": 401,
                "message": "用户未登录"
            }), 401
        
        # 根据角色返回相应的roles数组    
        roles = []
        if g.current_user_role == 'super_admin':
            roles = ["admin", "super_admin"]  # 超级管理员包含admin权限
        elif g.current_user_role == 'admin':
            roles = ["admin"]
        else:
            roles = ["user"]
        
        return jsonify({
            "code": 0,
            "data": {
                "id": g.current_user_id,
                "username": g.current_user_name or "用户",
                "email": g.current_user_email or "",
                "roles": roles,
                "role": g.current_user_role
            },
            "message": "获取用户信息成功"
        })
        
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取用户信息失败: {str(e)}"
        }), 500

@users_bp.route('/<string:user_id>/reset-password', methods=['PUT'])
def reset_password_route(user_id):
    """
    重置用户密码的API端点
    Args:
        user_id (str): 需要重置密码的用户ID
    Returns:
        Response: JSON响应
    """
    try:
        data = request.json
        new_password = data.get('password')

        # 校验密码是否存在
        if not new_password:
            return jsonify({"code": 400, "message": "缺少新密码参数 'password'"}), 400

        # 调用 service 函数重置密码
        success = reset_user_password(user_id=user_id, new_password=new_password)

        if success:
            return jsonify({
                "code": 0,
                "message": f"用户密码重置成功"
            })
        else:
            # service 层可能因为用户不存在或其他原因返回 False
            return jsonify({"code": 404, "message": f"用户未找到或密码重置失败"}), 404
    except Exception as e:
        # 统一处理异常
        return jsonify({
            "code": 500,
            "message": f"用户密码重置失败: {str(e)}"
        }), 500
