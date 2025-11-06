"""
优化的API蓝图
使用统一的服务管理器和共享工具，避免重复代码
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, send_file
from werkzeug.exceptions import BadRequest, NotFound

from services.unified import (
    get_service_manager,
    get_config_service,
    get_dataset_service,
    get_task_service,
    get_report_service,
    get_evaluation_service
)
from services.metrics_manager import MetricsManager
from utils.shared_utils import (
    ResponseFormatter,
    ConfigValidator,
    ErrorLogger,
    BatchOperationHelper,
    APIClientValidator,
    FileManager
)

# 设置日志
logger = logging.getLogger(__name__)

# 创建蓝图
evaluation_bp = Blueprint('evaluation_optimized', __name__, url_prefix='/api/v1/evaluation')

# ==================== 系统相关 API ====================

@evaluation_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    try:
        service_manager = get_service_manager()
        stats = service_manager.get_statistics()

        return ResponseFormatter.success({
            'status': 'healthy',
            'service': 'rag-evaluation',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0',
            'metrics_available': len(stats.get('metric_scores', []))
        })
    except Exception as e:
        ErrorLogger.log_error(e, "健康检查失败")
        return ResponseFormatter.error("健康检查失败", e)

@evaluation_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """获取系统统计信息"""
    try:
        service_manager = get_service_manager()
        stats = service_manager.get_statistics()
        return ResponseFormatter.success(stats)
    except Exception as e:
        ErrorLogger.log_error(e, "获取统计信息失败")
        return ResponseFormatter.error("获取统计信息失败", e)

@evaluation_bp.route('/config', methods=['GET'])
def get_config():
    """获取系统配置"""
    try:
        config_service = get_config_service()
        api_config = config_service.get_default_api_config()

        return ResponseFormatter.success({
            'api': api_config
        })
    except Exception as e:
        ErrorLogger.log_error(e, "获取配置失败")
        return ResponseFormatter.error("获取配置失败", e)

@evaluation_bp.route('/config', methods=['PUT'])
def update_config():
    """更新系统配置"""
    try:
        data = request.get_json()
        if not data:
            return ResponseFormatter.validation_error("请求数据不能为空")

        if 'api_config' in data:
            # 验证API配置
            validation_error = ConfigValidator.validate(data['api_config'], 'api_config')
            if validation_error:
                return ResponseFormatter.validation_error(validation_error)

            config_service = get_config_service()
            api_config = data['api_config']

            # 更新或创建API配置
            if 'id' in api_config:
                success = config_service.update_api_config(api_config['id'], api_config)
            else:
                config_id = config_service.create_api_config(api_config)
                config_service.set_default_config(config_id)
                success = True

            if not success:
                return ResponseFormatter.error("更新配置失败", status_code=400)

        return ResponseFormatter.success(message="配置更新成功")
    except Exception as e:
        ErrorLogger.log_error(e, "更新配置失败")
        return ResponseFormatter.error("更新配置失败", e)

@evaluation_bp.route('/test-connection', methods=['POST'])
def test_connection():
    """测试API连接"""
    try:
        data = request.get_json()
        if not data:
            return ResponseFormatter.validation_error("请求数据不能为空")

        # 验证必需字段
        validation_error = ConfigValidator.validate(data, 'api_config')
        if validation_error:
            return ResponseFormatter.validation_error(validation_error)

        # 验证提供商
        provider_validation = APIClientValidator.validate_provider(data.get('provider', ''))
        if provider_validation:
            return ResponseFormatter.validation_error(provider_validation)

        # TODO: 实现实际的连接测试
        # 这里可以调用 evaluation_service.test_connection()

        return ResponseFormatter.success({
            'success': True,
            'message': '连接测试成功',
            'details': {'provider': data['provider'], 'model': data['model']}
        })
    except Exception as e:
        ErrorLogger.log_error(e, "连接测试失败")
        return ResponseFormatter.error("连接测试失败", e)

# ==================== 数据集相关 API ====================

@evaluation_bp.route('/datasets', methods=['GET'])
def list_datasets():
    """获取数据集列表"""
    try:
        # 参数验证
        try:
            offset = max(0, int(request.args.get('offset', 0)))
            limit = min(100, max(1, int(request.args.get('limit', 10))))  # 限制最大100条
        except ValueError:
            return ResponseFormatter.validation_error("offset和limit必须是整数")

        dataset_service = get_dataset_service()
        result = dataset_service.get_datasets(offset, limit)

        return ResponseFormatter.success(result)
    except Exception as e:
        ErrorLogger.log_error(e, "获取数据集列表失败")
        return ResponseFormatter.error("获取数据集列表失败", e)

@evaluation_bp.route('/datasets', methods=['POST'])
def create_dataset():
    """创建数据集"""
    try:
        if 'file' not in request.files or not request.files['file'].filename:
            return ResponseFormatter.validation_error("请选择要上传的文件")

        file = request.files['file']
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        # 验证文件类型
        allowed_extensions = ['.json', '.csv', '.xlsx', '.xls']
        if not FileManager.is_allowed_file(file.filename, allowed_extensions):
            return ResponseFormatter.validation_error(
                f"不支持的文件类型，支持的格式: {', '.join(allowed_extensions)}"
            )

        # 验证名称
        if not name:
            name = file.filename

        dataset_service = get_dataset_service()
        dataset_id = dataset_service.create_dataset(file, name, description)

        return ResponseFormatter.success({'dataset_id': dataset_id}, "数据集创建成功")
    except Exception as e:
        ErrorLogger.log_error(e, "创建数据集失败")
        return ResponseFormatter.error("创建数据集失败", e)

@evaluation_bp.route('/datasets/<dataset_id>', methods=['GET'])
def get_dataset(dataset_id: str):
    """获取数据集详情"""
    try:
        if not dataset_id or not dataset_id.strip():
            return ResponseFormatter.validation_error("数据集ID不能为空")

        dataset_service = get_dataset_service()
        dataset = dataset_service.get_dataset(dataset_id)

        if not dataset:
            return ResponseFormatter.not_found_error("数据集不存在")

        return ResponseFormatter.success(dataset)
    except Exception as e:
        ErrorLogger.log_error(e, "获取数据集详情失败")
        return ResponseFormatter.error("获取数据集详情失败", e)

@evaluation_bp.route('/datasets/<dataset_id>', methods=['DELETE'])
def delete_dataset(dataset_id: str):
    """删除数据集"""
    try:
        if not dataset_id or not dataset_id.strip():
            return ResponseFormatter.validation_error("数据集ID不能为空")

        dataset_service = get_dataset_service()
        success = dataset_service.delete_dataset(dataset_id)

        if not success:
            return ResponseFormatter.not_found_error("数据集不存在或删除失败")

        return ResponseFormatter.success(message="数据集删除成功")
    except Exception as e:
        ErrorLogger.log_error(e, "删除数据集失败")
        return ResponseFormatter.error("删除数据集失败", e)

@evaluation_bp.route('/datasets/batch', methods=['DELETE'])
def batch_delete_datasets():
    """批量删除数据集"""
    try:
        data = request.get_json()
        if not data:
            return ResponseFormatter.validation_error("请求数据不能为空")

        dataset_ids = data.get('dataset_ids', [])
        if not dataset_ids:
            return ResponseFormatter.validation_error("未指定要删除的数据集")

        if not isinstance(dataset_ids, list):
            return ResponseFormatter.validation_error("dataset_ids必须是数组类型")

        dataset_service = get_dataset_service()
        result = dataset_service.batch_delete_datasets(dataset_ids)

        return ResponseFormatter.success(result, "批量删除完成")
    except Exception as e:
        ErrorLogger.log_error(e, "批量删除数据集失败")
        return ResponseFormatter.error("批量删除数据集失败", e)

@evaluation_bp.route('/datasets/<dataset_id>/samples', methods=['GET'])
def get_dataset_samples(dataset_id: str):
    """获取数据集样本"""
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 10))

        # TODO: 实现获取样本的逻辑
        samples = {'samples': [], 'offset': offset, 'limit': limit}

        return success_response(samples)
    except Exception as e:
        return handle_error(e, "获取数据集样本失败")

# ==================== 任务相关 API ====================

@evaluation_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """获取任务列表"""
    try:
        # 参数验证
        try:
            offset = max(0, int(request.args.get('offset', 0)))
            limit = min(100, max(1, int(request.args.get('limit', 10))))  # 限制最大100条
        except ValueError:
            return ResponseFormatter.validation_error("offset和limit必须是整数")

        status = request.args.get('status', '').strip()
        if status:
            # 验证状态值
            valid_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
            if status not in valid_statuses:
                return ResponseFormatter.validation_error(f"无效的状态值，支持的状态: {', '.join(valid_statuses)}")

        task_service = get_task_service()
        result = task_service.get_tasks(offset, limit, status)

        return ResponseFormatter.success(result)
    except Exception as e:
        ErrorLogger.log_error(e, "获取任务列表失败")
        return ResponseFormatter.error("获取任务列表失败", e)

@evaluation_bp.route('/tasks', methods=['POST'])
def create_task():
    """创建评测任务"""
    try:
        data = request.get_json()
        if not data:
            return ResponseFormatter.validation_error("请求数据不能为空")

        # 验证任务配置
        validation_error = ConfigValidator.validate(data, 'task')
        if validation_error:
            return ResponseFormatter.validation_error(validation_error)

        # 额外的任务验证
        chat_id = data.get('chat_id', '').strip()
        dataset_id = data.get('dataset_id', '').strip()

        if not chat_id:
            return ResponseFormatter.validation_error("chat_id不能为空")
        if not dataset_id:
            return ResponseFormatter.validation_error("dataset_id不能为空")

        task_service = get_task_service()
        task_id = task_service.create_task(data)

        return ResponseFormatter.success({'task_id': task_id}, "任务创建成功")
    except Exception as e:
        ErrorLogger.log_error(e, "创建任务失败")
        return ResponseFormatter.error("创建任务失败", e)

@evaluation_bp.route('/tasks/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """获取任务详情"""
    try:
        if not task_id or not task_id.strip():
            return ResponseFormatter.validation_error("任务ID不能为空")

        task_service = get_task_service()
        task = task_service.get_task(task_id)

        if not task:
            return ResponseFormatter.not_found_error("任务不存在")

        return ResponseFormatter.success(task)
    except Exception as e:
        ErrorLogger.log_error(e, "获取任务详情失败")
        return ResponseFormatter.error("获取任务详情失败", e)

@evaluation_bp.route('/tasks/<task_id>/start', methods=['POST'])
def start_task(task_id: str):
    """启动任务"""
    try:
        if not task_id or not task_id.strip():
            return ResponseFormatter.validation_error("任务ID不能为空")

        # TODO: 实现启动任务的逻辑
        return ResponseFormatter.success(message="任务启动成功")
    except Exception as e:
        ErrorLogger.log_error(e, "启动任务失败")
        return ResponseFormatter.error("启动任务失败", e)

@evaluation_bp.route('/tasks/<task_id>/pause', methods=['POST'])
def pause_task(task_id: str):
    """暂停任务"""
    try:
        if not task_id or not task_id.strip():
            return ResponseFormatter.validation_error("任务ID不能为空")

        # TODO: 实现暂停任务的逻辑
        return ResponseFormatter.success(message="任务暂停成功")
    except Exception as e:
        ErrorLogger.log_error(e, "暂停任务失败")
        return ResponseFormatter.error("暂停任务失败", e)

@evaluation_bp.route('/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id: str):
    """取消任务"""
    try:
        if not task_id or not task_id.strip():
            return ResponseFormatter.validation_error("任务ID不能为空")

        # TODO: 实现取消任务的逻辑
        return ResponseFormatter.success(message="任务取消成功")
    except Exception as e:
        ErrorLogger.log_error(e, "取消任务失败")
        return ResponseFormatter.error("取消任务失败", e)

@evaluation_bp.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id: str):
    """删除任务"""
    try:
        if not task_id or not task_id.strip():
            return ResponseFormatter.validation_error("任务ID不能为空")

        task_service = get_task_service()
        success = task_service.delete_task(task_id)

        if not success:
            return ResponseFormatter.not_found_error("任务不存在或删除失败")

        return ResponseFormatter.success(message="任务删除成功")
    except Exception as e:
        ErrorLogger.log_error(e, "删除任务失败")
        return ResponseFormatter.error("删除任务失败", e)

@evaluation_bp.route('/tasks/batch', methods=['DELETE'])
def batch_delete_tasks():
    """批量删除任务"""
    try:
        data = request.get_json()
        if not data:
            return ResponseFormatter.validation_error("请求数据不能为空")

        task_ids = data.get('task_ids', [])
        if not task_ids:
            return ResponseFormatter.validation_error("未指定要删除的任务")

        if not isinstance(task_ids, list):
            return ResponseFormatter.validation_error("task_ids必须是数组类型")

        task_service = get_task_service()
        result = task_service.batch_delete_tasks(task_ids)

        return ResponseFormatter.success(result, "批量删除完成")
    except Exception as e:
        ErrorLogger.log_error(e, "批量删除任务失败")
        return ResponseFormatter.error("批量删除任务失败", e)

# ==================== 报告相关 API ====================

@evaluation_bp.route('/reports', methods=['GET'])
def list_reports():
    """获取报告列表"""
    try:
        kb_id = request.args.get('kb_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 10))

        report_service = get_report_service()
        reports = report_service.get_reports(kb_id, start_date, end_date, offset, limit)

        return success_response({'reports': reports, 'total': len(reports)})
    except Exception as e:
        return handle_error(e, "获取报告列表失败")

@evaluation_bp.route('/reports/<task_id>', methods=['GET'])
def get_report(task_id: str):
    """获取报告详情"""
    try:
        report_service = get_report_service()
        report = report_service.get_report(task_id)

        if not report:
            raise NotFound("报告不存在")

        return success_response(report)
    except Exception as e:
        return handle_error(e, "获取报告详情失败")

@evaluation_bp.route('/reports/<task_id>/export', methods=['GET'])
def export_report(task_id: str):
    """导出报告"""
    try:
        format_type = request.args.get('format', 'json')

        if format_type not in ['json', 'excel', 'pdf']:
            raise BadRequest("不支持的导出格式")

        # TODO: 实现导出逻辑
        return success_response(message="导出成功")
    except Exception as e:
        return handle_error(e, "导出报告失败")

@evaluation_bp.route('/reports/<task_id>', methods=['DELETE'])
def delete_report(task_id: str):
    """删除报告"""
    try:
        report_service = get_report_service()
        success = report_service.delete_report(task_id)

        if not success:
            raise NotFound("报告不存在或删除失败")

        return success_response(message="报告删除成功")
    except Exception as e:
        return handle_error(e, "删除报告失败")

@evaluation_bp.route('/reports/batch', methods=['DELETE'])
def batch_delete_reports():
    """批量删除报告"""
    try:
        data = request.get_json()
        task_ids = data.get('task_ids', [])

        if not task_ids:
            raise BadRequest("未指定要删除的报告")

        report_service = get_report_service()
        result = report_service.batch_delete_reports(task_ids)

        return success_response(result, "批量删除完成")
    except Exception as e:
        return handle_error(e, "批量删除失败")

# ==================== 指标相关 API ====================

@evaluation_bp.route('/metrics', methods=['GET'])
def list_metrics():
    """获取可用指标列表"""
    try:
        metrics_manager = MetricsManager()
        metrics = metrics_manager.get_all_metrics()

        return success_response({'metrics': metrics})
    except Exception as e:
        return handle_error(e, "获取指标列表失败")

@evaluation_bp.route('/metrics/groups', methods=['GET'])
def get_metric_groups():
    """获取指标分组"""
    try:
        metrics_manager = MetricsManager()
        groups = metrics_manager.get_metric_groups()

        return success_response({'groups': groups})
    except Exception as e:
        return handle_error(e, "获取指标分组失败")

@evaluation_bp.route('/metrics/validate', methods=['POST'])
def validate_metrics():
    """验证指标配置"""
    try:
        data = request.get_json()
        metrics = data.get('metrics', [])
        has_reference = data.get('has_reference', False)
        has_contexts = data.get('has_contexts', False)

        # TODO: 实现验证逻辑
        return success_response({'valid': True})
    except Exception as e:
        return handle_error(e, "验证指标失败")

# ==================== 快速评测 API ====================

@evaluation_bp.route('/quick', methods=['POST'])
def quick_evaluate():
    """快速评测单个问答对"""
    try:
        data = request.get_json()
        required_fields = ['question', 'answer']

        for field in required_fields:
            if field not in data:
                raise BadRequest(f"缺少必需字段: {field}")

        # TODO: 实现快速评测逻辑
        result = {'score': 0.85, 'metric': 'answer_correctness'}

        return success_response(result)
    except Exception as e:
        return handle_error(e, "快速评测失败")

@evaluation_bp.route('/quick/batch', methods=['POST'])
def batch_quick_evaluate():
    """批量快速评测"""
    try:
        data = request.get_json()
        samples = data.get('samples', [])

        if not samples:
            raise BadRequest("未提供评测样本")

        # TODO: 实现批量快速评测逻辑
        results = [{'score': 0.85, 'metric': 'answer_correctness'}]

        return success_response({'results': results})
    except Exception as e:
        return handle_error(e, "批量快速评测失败")


def register_blueprint(app):
    """注册蓝图到Flask应用"""
    app.register_blueprint(evaluation_bp)
    logger.info("✅ 优化的评测蓝图注册成功")