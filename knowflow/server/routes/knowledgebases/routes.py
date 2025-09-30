import traceback
from flask import Blueprint, request, jsonify, g
from services.knowledgebases.service import KnowledgebaseService
from services.rbac.permission_service import permission_service
from services.rbac.permission_decorator import require_permission
from models.rbac_models import ResourceType, PermissionType, RoleType
from utils import success_response, error_response
from .. import knowledgebase_bp

@knowledgebase_bp.route('', methods=['GET'])
def get_knowledgebase_list():
    """获取知识库列表"""
    try:
        params = {
            'page': int(request.args.get('current_page', 1)),
            'size': int(request.args.get('size', 10)),
            'name': request.args.get('name', ''),
            'current_user_id': getattr(g, 'current_user_id', None),
            'user_role': getattr(g, 'current_user_role', None)
        }
        result = KnowledgebaseService.get_knowledgebase_list(**params)
        return success_response(result)
    except ValueError as e:
        return error_response("参数类型错误", code=400)
    except Exception as e:
        return error_response(str(e))

@knowledgebase_bp.route('/<string:kb_id>', methods=['GET'])
def get_knowledgebase_detail(kb_id):
    """获取知识库详情"""
    try:
        knowledgebase = KnowledgebaseService.get_knowledgebase_detail(
            kb_id=kb_id
        )
        if not knowledgebase:
            return error_response('知识库不存在', code=404)
        return success_response(knowledgebase)
    except Exception as e:
        return error_response(str(e))

@knowledgebase_bp.route('', methods=['POST'])
def create_knowledgebase():
    """创建知识库"""
    try:
        data = request.json
        if not data.get('name'):
            return error_response('知识库名称不能为空', code=400)
        
        # 获取当前用户信息
        current_user_id = getattr(g, 'current_user_id', None)
        if not current_user_id:
            return error_response("未授权访问", code=401)
            
        # 添加创建者信息
        data['creator_id'] = current_user_id
        kb = KnowledgebaseService.create_knowledgebase(**data)
        return success_response(kb, "创建成功", code=0)
    except Exception as e:
        return error_response(str(e))

@knowledgebase_bp.route('/<string:kb_id>', methods=['PUT'])
def update_knowledgebase(kb_id):
    """更新知识库"""
    try:
        data = request.json
        kb = KnowledgebaseService.update_knowledgebase(
            kb_id=kb_id,
            **data
        )
        if not kb:
            return error_response('知识库不存在', code=404)
        return success_response(kb)
    except Exception as e:
        return error_response(str(e))

@knowledgebase_bp.route('/<string:kb_id>', methods=['DELETE'])
def delete_knowledgebase(kb_id):
    """删除知识库"""
    try:
        result = KnowledgebaseService.delete_knowledgebase(
            kb_id=kb_id
        )
        if not result:
            return error_response('知识库不存在', code=404)
        return success_response(message='删除成功')
    except Exception as e:
        return error_response(str(e))

@knowledgebase_bp.route('/batch', methods=['DELETE'])
# @require_permission('admin')  # 移除权限检查，管理界面由超级管理员操作
def batch_delete_knowledgebase():
    """批量删除知识库"""
    try:
        data = request.json or {}
        # 同时兼容前端不同命名风格：camelCase、snake_case，以及历史字段 ids
        kb_ids = data.get('kbIds') or data.get('kb_ids') or data.get('ids')
        if not kb_ids or not isinstance(kb_ids, list) or len(kb_ids) == 0:
            return error_response('请选择要删除的知识库', code=400)
            
        result = KnowledgebaseService.batch_delete_knowledgebase(
            kb_ids=kb_ids
        )
        return success_response(message=f'成功删除 {result} 个知识库')
    except Exception as e:
        return error_response(str(e))

# 权限管理相关接口
@knowledgebase_bp.route('/<string:kb_id>/permissions', methods=['GET'])
def get_knowledgebase_permissions(kb_id):
    """获取知识库权限列表"""
    try:
        # 获取知识库的所有用户权限
        permissions = KnowledgebaseService.get_knowledgebase_permissions(kb_id)
        return success_response(data=permissions)
    except Exception as e:
        return error_response(f"获取权限列表失败: {str(e)}", code=500)

@knowledgebase_bp.route('/<string:kb_id>/permissions/users', methods=['POST'])
def grant_user_permission(kb_id):
    """为用户授予知识库权限"""
    try:
        data = request.json
        if not data:
            return error_response('请求数据不能为空', code=400)
        
        user_id = data.get('user_id')
        permission_level = data.get('permission_level')  # 'admin', 'write', 'read'
        
        if not user_id or not permission_level:
            return error_response('用户ID和权限级别不能为空', code=400)
        
        # 验证权限级别
        if permission_level not in ['admin', 'write', 'read']:
            return error_response('无效的权限级别', code=400)
        
        # 映射权限级别到角色代码
        role_mapping = {
            'admin': 'admin',
            'write': 'editor', 
            'read': 'viewer'
        }
        role_code = role_mapping[permission_level]
        
        # 授予角色
        success = permission_service.grant_role_to_user(
            user_id=user_id,
            role_code=role_code,
            granted_by='current_user',  # TODO: 从token获取当前用户
            tenant_id='default',
            resource_type=ResourceType.KNOWLEDGEBASE,
            resource_id=kb_id
        )
        
        if success:
            return success_response(
                data={'message': f'成功为用户授予{permission_level}权限'},
                message='权限授予成功'
            )
        else:
            return error_response('权限授予失败', code=500)
            
    except Exception as e:
        return error_response(f"授予权限失败: {str(e)}", code=500)

@knowledgebase_bp.route('/<string:kb_id>/permissions/users/<string:user_id>', methods=['DELETE'])
def revoke_user_permission(kb_id, user_id):
    """撤销用户的知识库权限"""
    try:
        # 直接撤销用户在该知识库的所有相关权限
        kb_roles = ['admin', 'editor', 'viewer']
        revoked_count = 0
        
        for role_code in kb_roles:
            success = permission_service.revoke_role_from_user(
                user_id=user_id,
                role_code=role_code,
                tenant_id='default',
                resource_id=kb_id
            )
            if success:
                revoked_count += 1
        
        if revoked_count > 0:
            return success_response(
                data={'message': f'成功撤销{revoked_count}个权限'},
                message='权限撤销成功'
            )
        else:
            return success_response(
                data={'message': '未找到相关权限'},
                message='无权限可撤销'
            )
            
    except Exception as e:
        return error_response(f"撤销权限失败: {str(e)}", code=500)

@knowledgebase_bp.route('/<string:kb_id>/permissions/teams', methods=['POST'])
def grant_team_permission(kb_id):
    """为团队授予知识库权限"""
    try:
        data = request.json
        if not data:
            return error_response('请求数据不能为空', code=400)
        
        team_id = data.get('team_id')
        permission_level = data.get('permission_level')  # 'admin', 'write', 'read'
        
        if not team_id or not permission_level:
            return error_response('团队ID和权限级别不能为空', code=400)
        
        # 验证权限级别
        if permission_level not in ['admin', 'write', 'read']:
            return error_response('无效的权限级别', code=400)
        
        # TODO: 实现团队权限授予逻辑
        # 这里需要根据团队成员为每个成员授予相应权限
        success = KnowledgebaseService.grant_team_permission(
            kb_id=kb_id,
            team_id=team_id,
            permission_level=permission_level
        )
        
        if success:
            return success_response(
                data={'message': f'成功为团队授予{permission_level}权限'},
                message='团队权限授予成功'
            )
        else:
            return error_response('团队权限授予失败', code=500)
            
    except Exception as e:
        return error_response(f"授予团队权限失败: {str(e)}", code=500)

@knowledgebase_bp.route('/<string:kb_id>/permissions/teams/<string:team_id>', methods=['DELETE'])
def revoke_team_permission(kb_id, team_id):
    """撤销团队的知识库权限"""
    try:
        success = KnowledgebaseService.revoke_team_permission(
            kb_id=kb_id,
            team_id=team_id
        )
        
        if success:
            return success_response(
                data={'message': '成功撤销团队权限'},
                message='团队权限撤销成功'
            )
        else:
            return error_response('团队权限撤销失败', code=500)
            
    except Exception as e:
        return error_response(f"撤销团队权限失败: {str(e)}", code=500)

@knowledgebase_bp.route('/<string:kb_id>/permissions/check', methods=['POST'])
def check_knowledgebase_permission(kb_id):
    """检查用户对知识库的权限"""
    try:
        data = request.json
        if not data:
            return error_response('请求数据不能为空', code=400)
        
        user_id = data.get('user_id')
        permission_type = data.get('permission_type', 'read')
        
        if not user_id:
            return error_response('用户ID不能为空', code=400)
        
        # 解析权限类型
        try:
            perm_type = PermissionType(permission_type)
        except ValueError:
            return error_response('无效的权限类型', code=400)
        
        # 执行权限检查
        permission_check = permission_service.check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGEBASE,
            resource_id=kb_id,
            permission_type=perm_type,
            tenant_id='default'
        )
        
        return success_response(data={
            'has_permission': permission_check.has_permission,
            'user_id': permission_check.user_id,
            'resource_id': permission_check.resource_id,
            'permission_type': permission_check.permission_type.value,
            'granted_roles': permission_check.granted_roles,
            'reason': permission_check.reason
        })
        
    except Exception as e:
        return error_response(f"权限检查失败: {str(e)}", code=500)

@knowledgebase_bp.route('/<string:kb_id>/documents', methods=['GET'])
def get_knowledgebase_documents(kb_id):
    """获取知识库下的文档列表"""
    try:
        params = {
            'kb_id': kb_id,
            'page': int(request.args.get('current_page', 1)),
            'size': int(request.args.get('size', 10)),
            'name': request.args.get('name', '')
        }
        result = KnowledgebaseService.get_knowledgebase_documents(**params)
        return success_response(result)
    except ValueError as e:
        return error_response("参数类型错误", code=400)
    except Exception as e:
        return error_response(str(e))

@knowledgebase_bp.route('/<string:kb_id>/documents', methods=['POST'])
def add_documents_to_knowledgebase(kb_id):
    """添加文档到知识库"""
    try:
        print(f"[DEBUG] 接收到添加文档请求，kb_id: {kb_id}")
        data = request.json
        if not data:
            print("[ERROR] 请求数据为空")
            return error_response('请求数据不能为空', code=400)
            
        file_ids = data.get('file_ids', [])
        print(f"[DEBUG] 接收到的file_ids: {file_ids}, 类型: {type(file_ids)}")
        
        try:
            result = KnowledgebaseService.add_documents_to_knowledgebase(
                kb_id=kb_id,
                file_ids=file_ids
            )
            print(f"[DEBUG] 服务层处理成功，结果: {result}")
            return success_response(
                data=result,
                message="添加成功",
                code=0
            )
        except Exception as service_error:
            print(f"[ERROR] 服务层错误详情: {str(service_error)}")
            
            traceback.print_exc()
            return error_response(str(service_error), code=500)
            
    except Exception as e:
        print(f"[ERROR] 路由层错误详情: {str(e)}")
        traceback.print_exc()
        return error_response(str(e), code=500)

@knowledgebase_bp.route('/documents/<string:doc_id>', methods=['DELETE', 'OPTIONS'])
def delete_document(doc_id):
    """删除文档"""
    # 处理 OPTIONS 预检请求
    if request.method == 'OPTIONS':
        response = success_response({})
        # 添加 CORS 相关头
        response.headers.add('Access-Control-Allow-Methods', 'DELETE')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        return response
        
    try:
        KnowledgebaseService.delete_document(doc_id)
        return success_response(message="删除成功")
    except Exception as e:
        return error_response(str(e))

@knowledgebase_bp.route('/documents/<doc_id>/parse', methods=['POST'])
def parse_document(doc_id):
    """开始解析文档"""
    # 处理 OPTIONS 预检请求
    if request.method == 'OPTIONS':
        response = success_response({})
        # 添加 CORS 相关头
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        return response

    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT kb_id FROM document WHERE id = %s", (doc_id,))
    doc_result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not doc_result:
        return error_response('文档不存在', code=404)

    kb_id = doc_result['kb_id']

    # 检查用户是否有知识库的写权限
    current_user_id = getattr(g, 'current_user_id', None)
    if current_user_id:
        # 使用 RBAC 权限检查
        from services.rbac.permission_service import permission_service
        from models.rbac_models import ResourceType, PermissionType

        permission_check = permission_service.check_permission(
            user_id=current_user_id,
            resource_type=ResourceType.KNOWLEDGEBASE,
            resource_id=kb_id,
            permission_type=PermissionType.WRITE,
            tenant_id='default'
        )

        if not permission_check.has_permission:
            return error_response('权限不足，请联系管理员添加知识库写权限', code=109)

    # 检查用户对知识库的写权限
    try:
        # 立即更新文档状态为"正在解析"，确保UI及时响应
        from services.knowledgebases.document_parser import _update_document_progress
        _update_document_progress(doc_id, run="1", progress=0.0, message="开始解析文档...")
        
        # 异步执行解析，避免阻塞API响应
        result = KnowledgebaseService.async_parse_document(doc_id)
        return success_response(data=result)
    except Exception as e:
        return error_response(str(e), code=500)

@knowledgebase_bp.route('/documents/<doc_id>/parse/progress', methods=['GET'])
def get_parse_progress(doc_id):
    """获取文档解析进度"""
    # 处理 OPTIONS 预检请求
    if request.method == 'OPTIONS':
        response = success_response({})
        # 添加 CORS 相关头
        response.headers.add('Access-Control-Allow-Methods', 'GET')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        return response
        
    try:
        result = KnowledgebaseService.get_document_parse_progress(doc_id)
        if isinstance(result, dict) and 'error' in result:
            return error_response(result['error'], code=404)
        return success_response(data=result)
    except Exception as e:
        print(f"获取解析进度失败: {str(e)}")
        return error_response("解析进行中，请稍后重试", code=202)

@knowledgebase_bp.route('/documents/<doc_id>/parse/cancel', methods=['POST'])
def cancel_parse_document(doc_id):
    """取消文档解析"""
    # 处理 OPTIONS 预检请求
    if request.method == 'OPTIONS':
        response = success_response({})
        # 添加 CORS 相关头
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        return response
        
    try:
        result = KnowledgebaseService.cancel_document_parse(doc_id)
        return success_response(data=result, message="取消解析成功")
    except Exception as e:
        print(f"取消解析失败: {str(e)}")
        return error_response(f"取消解析失败: {str(e)}", code=500)

# 获取系统 Embedding 配置路由
@knowledgebase_bp.route('/system_embedding_config', methods=['GET'])
def get_system_embedding_config_route():
    """获取系统级 Embedding 配置的API端点"""
    try:
        config_data = KnowledgebaseService.get_system_embedding_config()
        return success_response(data=config_data)
    except Exception as e:
        print(f"获取系统 Embedding 配置失败: {str(e)}")
        return error_response(message=f"获取配置失败: {str(e)}", code=500) # 返回通用错误信息

# 设置系统 Embedding 配置路由
@knowledgebase_bp.route('/system_embedding_config', methods=['POST'])
def set_system_embedding_config_route():
    """设置系统级 Embedding 配置的API端点"""
    try:
        data = request.json
        if not data:
            return error_response('请求数据不能为空', code=400)

        llm_name = data.get('llm_name', '').strip()
        api_base = data.get('api_base', '').strip()
        api_key = data.get('api_key', '').strip() # 允许空

        if not llm_name or not api_base:
            return error_response('模型名称和 API 地址不能为空', code=400)

        # 调用服务层进行处理（包括连接测试和数据库操作）
        success, message = KnowledgebaseService.set_system_embedding_config(
            llm_name=llm_name,
            api_base=api_base,
            api_key=api_key
        )

        if success:
            return success_response(message=message)
        else:
            # 如果服务层返回失败（例如连接测试失败或数据库错误），将消息返回给前端
            return error_response(message=message, code=400) # 使用 400 表示操作失败

    except Exception as e:
        # 捕获路由层或未预料的服务层异常
        print(f"设置系统 Embedding 配置失败: {str(e)}")
        return error_response(message=f"设置配置时发生内部错误: {str(e)}", code=500)

# 启动顺序批量解析路由
@knowledgebase_bp.route('/<string:kb_id>/batch_parse_sequential/start', methods=['POST'])
def start_sequential_batch_parse_route(kb_id):
    """异步启动知识库的顺序批量解析任务"""
    if request.method == 'OPTIONS':
        response = success_response({})
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        return response

    try:
        result = KnowledgebaseService.start_sequential_batch_parse_async(kb_id)
        if result.get("success"):
            return success_response(data={"message": result.get("message")})
        else:
            # 如果任务已在运行或启动失败，返回错误信息
            return error_response(result.get("message", "启动失败"), code=409 if "已在运行中" in result.get("message", "") else 500)
    except Exception as e:
        print(f"启动顺序批量解析路由处理失败 (KB ID: {kb_id}): {str(e)}")
        traceback.print_exc()
        return error_response(f"启动顺序批量解析失败: {str(e)}", code=500)

# 获取顺序批量解析进度路由
@knowledgebase_bp.route('/<string:kb_id>/batch_parse_sequential/progress', methods=['GET'])
def get_sequential_batch_parse_progress_route(kb_id):
    """获取知识库的顺序批量解析任务进度"""
    if request.method == 'OPTIONS':
        response = success_response({})
        response.headers.add('Access-Control-Allow-Methods', 'GET')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        return response

    try:
        result = KnowledgebaseService.get_sequential_batch_parse_progress(kb_id)
        # 直接返回从 service 获取的状态信息
        return success_response(data=result)
    except Exception as e:
        print(f"获取顺序批量解析进度路由处理失败 (KB ID: {kb_id}): {str(e)}")
        traceback.print_exc()
        return error_response(f"获取进度失败: {str(e)}", code=500)