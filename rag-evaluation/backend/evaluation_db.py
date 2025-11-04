"""
使用数据库的评测系统 API 路由
"""

import os
import asyncio
import logging
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import uuid
from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np

# 导入数据库管理器
from db import get_config_manager, get_dataset_manager, get_task_manager, get_report_manager

# 导入服务模块
try:
    from services.evaluation_service import EvaluationService
    from services.metrics_manager import MetricsManager
except ImportError as e:
    print(f"Import error: {e}")
    EvaluationService = None
    MetricsManager = None

logger = logging.getLogger(__name__)

# 创建蓝图
evaluation_bp = Blueprint('evaluation_db', __name__, url_prefix='/api/v1/evaluation')

# 初始化服务
evaluation_service = None
config_manager = None
dataset_manager = None
task_manager = None
report_manager = None
metrics_manager = None


class NaNSafeJSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 NaN 和 Infinity 值"""
    def encode(self, o):
        if isinstance(o, float):
            if np.isnan(o) or np.isinf(o):
                return 'null'
        return super().encode(o)

    def iterencode(self, o, _one_shot=False):
        """重写 iterencode 以处理嵌套的 NaN 值"""
        for chunk in super().iterencode(o, _one_shot):
            # 替换 JSON 中的 NaN 字符串为 null
            chunk = chunk.replace('NaN', 'null')
            chunk = chunk.replace('Infinity', 'null')
            chunk = chunk.replace('-Infinity', 'null')
            yield chunk


def init_services():
    """初始化所有服务"""
    global config_manager, dataset_manager, task_manager, report_manager, metrics_manager, evaluation_service

    if not config_manager:
        config_manager = get_config_manager()
        logger.info("ConfigManager initialized")

    if not dataset_manager:
        dataset_manager = get_dataset_manager()
        logger.info("DatasetManager initialized")

    if not task_manager:
        task_manager = get_task_manager()
        logger.info("TaskManager initialized")

    if not report_manager:
        report_manager = get_report_manager()
        logger.info("ReportManager initialized")

    if not metrics_manager and MetricsManager:
        metrics_manager = MetricsManager()
        logger.info("MetricsManager initialized")

    # 初始化评测服务
    if not evaluation_service:
        try:
            init_evaluation_service()
            logger.info("EvaluationService initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize EvaluationService: {e}")
            evaluation_service = None


def init_evaluation_service(force_reload=False):
    """初始化评测服务"""
    global evaluation_service

    if not evaluation_service or force_reload:
        try:
            # 使用统一配置服务
            from config import get_config_service
            config_service = get_config_service()

            api_config = config_service.get_api_config()
            ragflow_url = config_service.get_ragflow_url()
            llm_model = config_service.get_llm_model()

            evaluation_service = EvaluationService(
                llm_model=llm_model,
                ragflow_url=ragflow_url,
                api_config=api_config
            )
            logger.info(f"EvaluationService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize EvaluationService: {str(e)}")
            evaluation_service = None


# ==================== 配置管理 API ====================

@evaluation_bp.route('/config', methods=['GET'])
@cross_origin()
def get_config():
    """获取系统配置"""
    try:
        init_services()

        # 获取所有系统设置
        settings = config_manager.get_settings()

        # 按 category 分组
        config_by_category = {}
        for setting in settings:
            category = setting['category']
            if category not in config_by_category:
                config_by_category[category] = []
            config_by_category[category].append({
                'key': setting['key'],
                'value': setting['value'],
                'description': setting['description']
            })

        # 获取默认API配置
        api_configs = config_manager.get_api_configs()
        default_api = None
        if api_configs:
            default_api = next((config for config in api_configs if config.get('is_default')), api_configs[0])

        # 统一转换为驼峰命名
        def to_camel_case(config):
            if not config:
                return None
            return {
                'id': config.get('id'),
                'name': config.get('name'),
                'provider': config.get('provider'),
                'apiKey': config.get('api_key'),
                'endpoint': config.get('endpoint'),
                'model': config.get('model'),
                'embeddingModel': config.get('embedding_model'),
                'temperature': config.get('temperature'),
                'maxTokens': config.get('max_tokens'),
                'isDefault': config.get('is_default'),
                'createdAt': config.get('created_at'),
                'updatedAt': config.get('updated_at')
            }

        # 转换所有配置
        api_configs_camel = [to_camel_case(c) for c in api_configs]
        default_api_camel = to_camel_case(default_api)

        return jsonify({
            'config': config_by_category,
            'api_configs': api_configs_camel,
            'api': default_api_camel
        })

    except Exception as e:
        logger.error(f"Failed to get config: {str(e)}")
        return jsonify({'error': 'Failed to get configuration'}), 500


@evaluation_bp.route('/config', methods=['PUT'])
@cross_origin()
def update_config():
    """更新系统配置"""
    try:
        init_services()
        data = request.get_json()

        # 批量更新设置
        if 'settings' in data:
            config_manager.update_settings_batch(data['settings'])

        # 更新 API 配置
        if 'api_config' in data:
            api_config = data['api_config']

            # 前端字段名转换：驼峰 -> 下划线
            field_mapping = {
                'apiKey': 'api_key',
                'embeddingModel': 'embedding_model',
                'maxTokens': 'max_tokens'
            }

            # 转换字段名
            normalized_config = {}
            for key, value in api_config.items():
                db_key = field_mapping.get(key, key)
                normalized_config[db_key] = value

            default_config = config_manager.get_default_api_config()

            if default_config:
                config_manager.update_api_config(default_config['id'], normalized_config)
            else:
                config_manager.create_api_config(normalized_config)

        # 更新通知配置
        if 'notification' in data:
            config_manager.update_setting('notification_enabled', data['notification'].get('enabled', False))
            if 'webhook_url' in data['notification']:
                config_manager.update_setting('notification_webhook_url', data['notification']['webhook_url'])

        return jsonify({'message': 'Configuration updated successfully'})

    except Exception as e:
        logger.error(f"Failed to update config: {str(e)}")
        return jsonify({'error': str(e)}), 500


@evaluation_bp.route('/api-configs', methods=['GET'])
@cross_origin()
def get_api_configs():
    """获取 API 配置列表"""
    try:
        init_services()
        configs = config_manager.get_api_configs()
        return jsonify({'configs': configs})

    except Exception as e:
        logger.error(f"Failed to get API configs: {str(e)}")
        return jsonify({'error': 'Failed to get API configurations'}), 500


@evaluation_bp.route('/api-configs', methods=['POST'])
@cross_origin()
def create_api_config():
    """创建 API 配置"""
    try:
        init_services()

        data = request.get_json()

        # 验证必填字段
        required_fields = ['name', 'provider', 'api_key']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # 如果设置为默认，先取消其他默认配置
        if data.get('is_default', False):
            # 这里需要在数据库层面实现，暂时跳过
            pass

        config_id = config_manager.create_api_config(data)

        return jsonify({
            'message': 'API configuration created successfully',
            'config_id': config_id
        }), 201

    except Exception as e:
        logger.error(f"Failed to create API config: {str(e)}")
        return jsonify({'error': 'Failed to create API configuration'}), 500


@evaluation_bp.route('/api-configs/<int:config_id>', methods=['PUT'])
@cross_origin()
def update_api_config(config_id):
    """更新 API 配置"""
    try:
        init_services()

        data = request.get_json()

        # 验证必填字段
        required_fields = ['name', 'provider', 'api_key']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # 更新配置
        success = config_manager.update_api_config(config_id, data)

        if success:
            return jsonify({'message': 'API configuration updated successfully'})
        else:
            return jsonify({'error': 'API configuration not found'}), 404

    except Exception as e:
        logger.error(f"Failed to update API config: {str(e)}")
        return jsonify({'error': 'Failed to update API configuration'}), 500


@evaluation_bp.route('/api-configs/<int:config_id>', methods=['DELETE'])
@cross_origin()
def delete_api_config(config_id):
    """删除 API 配置"""
    try:
        init_services()

        success = config_manager.delete_api_config(config_id)

        if success:
            return jsonify({'message': 'API configuration deleted successfully'})
        else:
            return jsonify({'error': 'API configuration not found'}), 404

    except Exception as e:
        logger.error(f"Failed to delete API config: {str(e)}")
        return jsonify({'error': 'Failed to delete API configuration'}), 500


# ==================== 数据集管理 API ====================

@evaluation_bp.route('/datasets', methods=['GET'])
@cross_origin()
def list_datasets():
    """获取数据集列表"""
    try:
        init_services()

        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))

        result = dataset_manager.get_datasets(limit, offset)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to list datasets: {str(e)}")
        return jsonify({'error': 'Failed to list datasets'}), 500


@evaluation_bp.route('/datasets', methods=['POST'])
@cross_origin()
def upload_dataset():
    """上传评测数据集"""
    try:
        init_services()

        # 检查文件
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # 获取表单数据
        dataset_name = request.form.get('name', file.filename)
        description = request.form.get('description', '')

        # 读取文件内容
        file_content = file.read()
        file_size = len(file_content)

        # 解析文件内容（这里需要实现文件解析逻辑）
        try:
            # 假设是 JSON 文件
            samples = json.loads(file_content.decode('utf-8'))
            num_samples = len(samples)

            # 检查样本结构
            has_reference = any('expected_answer' in sample for sample in samples)
            has_contexts = any('contexts' in sample for sample in samples)
            sample_fields = list(samples[0].keys()) if samples else []

        except json.JSONDecodeError:
            # 如果不是 JSON，可以尝试 CSV
            try:
                df = pd.read_csv(pd.io.common.StringIO(file_content.decode('utf-8')))
                samples = df.to_dict('records')
                num_samples = len(samples)
                has_reference = 'expected_answer' in df.columns
                has_contexts = 'contexts' in df.columns
                sample_fields = list(df.columns)
            except Exception as e:
                return jsonify({'error': f'Unsupported file format: {str(e)}'}), 400

        # 创建数据集记录
        dataset_id = str(uuid.uuid4())
        file_type = Path(file.filename).suffix.lower()

        # 保存文件到磁盘
        storage_path = Path('tmp/datasets')
        storage_path.mkdir(parents=True, exist_ok=True)

        file_path = storage_path / f"{dataset_id}{file_type}"
        with open(file_path, 'wb') as f:
            f.write(file_content)

        dataset_data = {
            'id': dataset_id,
            'name': dataset_name,
            'description': description,
            'file_name': secure_filename(file.filename),
            'file_type': file_type,
            'file_size': file_size,
            'storage_path': str(file_path),
            'num_samples': num_samples,
            'has_reference': has_reference,
            'has_contexts': has_contexts,
            'sample_fields': sample_fields,
            'created_by': request.headers.get('X-User-Id', 'anonymous')
        }

        dataset_manager.create_dataset(dataset_data)

        return jsonify({
            'id': dataset_id,
            'name': dataset_name,
            'description': description,
            'file_name': secure_filename(file.filename),
            'file_type': file_type,
            'num_samples': num_samples,
            'has_reference': has_reference,
            'has_contexts': has_contexts,
            'sample_fields': sample_fields,
            'created_at': datetime.now().isoformat()
        }), 201

    except Exception as e:
        logger.error(f"Failed to upload dataset: {str(e)}")
        return jsonify({'error': 'Failed to upload dataset'}), 500


@evaluation_bp.route('/datasets/<dataset_id>', methods=['GET'])
@cross_origin()
def get_dataset(dataset_id: str):
    """获取数据集详情"""
    try:
        init_services()

        dataset = dataset_manager.get_dataset(dataset_id)
        if not dataset:
            return jsonify({'error': 'Dataset not found'}), 404

        return jsonify(dataset)

    except Exception as e:
        logger.error(f"Failed to get dataset: {str(e)}")
        return jsonify({'error': 'Failed to get dataset'}), 500


@evaluation_bp.route('/datasets/<dataset_id>/samples', methods=['GET'])
@cross_origin()
def get_dataset_samples(dataset_id: str):
    """获取数据集样本"""
    try:
        init_services()

        dataset = dataset_manager.get_dataset(dataset_id)
        if not dataset:
            return jsonify({'error': 'Dataset not found'}), 404

        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))

        # 使用统一的数据集样本获取方法
        samples = dataset_manager.get_dataset_samples(dataset_id, offset, limit)

        # 获取总数（需要获取全部样本来计算总数）
        all_samples = dataset_manager.get_dataset_samples(dataset_id, 0, None)
        total = len(all_samples)

        return jsonify({
            'samples': samples,
            'total': total,
            'limit': limit,
            'offset': offset
        })

    except FileNotFoundError as e:
        logger.error(f"Dataset samples not found: {str(e)}")
        return jsonify({'error': 'Dataset file not found'}), 404
    except Exception as e:
        logger.error(f"Failed to get dataset samples: {str(e)}")
        return jsonify({'error': 'Failed to get dataset samples'}), 500


@evaluation_bp.route('/datasets/generate/<dataset_type>', methods=['POST'])
@cross_origin()
def generate_sample_dataset(dataset_type: str):
    """生成示例数据集"""
    try:
        init_services()

        # 生成示例数据
        if dataset_type == 'basic':
            samples = [
                {
                    'question': '什么是人工智能？',
                    'expected_answer': '人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。'
                },
                {
                    'question': '什么是机器学习？',
                    'expected_answer': '机器学习是人工智能的一个子集，使计算机能够在没有明确编程的情况下学习和改进。'
                },
                {
                    'question': '什么是深度学习？',
                    'expected_answer': '深度学习是机器学习的一个子集，使用具有多个隐藏层的神经网络来学习数据的复杂模式。'
                }
            ]
        elif dataset_type == 'with_contexts':
            samples = [
                {
                    'question': '什么是人工智能？',
                    'expected_answer': '人工智能是计算机科学的一个分支。',
                    'contexts': ['人工智能是指由机器模拟人类智能行为的技术。', 'AI系统可以学习、推理和解决问题。'],
                    'reference_contexts': ['人工智能的定义包括感知、学习、推理等功能。']
                },
                {
                    'question': '机器学习有哪些类型？',
                    'expected_answer': '机器学习包括监督学习、无监督学习和强化学习。',
                    'contexts': ['监督学习使用标记数据训练。', '无监督学习从未标记数据中发现模式。', '强化学习通过奖励和惩罚来学习。']
                }
            ]
        else:
            return jsonify({'error': 'Unknown dataset type'}), 400

        # 创建数据集
        dataset_id = str(uuid.uuid4())
        dataset_name = f"Sample Dataset - {dataset_type}"

        # 保存文件
        storage_path = Path('tmp/datasets')
        storage_path.mkdir(parents=True, exist_ok=True)

        file_path = storage_path / f"{dataset_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(samples, f, ensure_ascii=False, indent=2)

        dataset_data = {
            'id': dataset_id,
            'name': dataset_name,
            'description': f'Auto-generated sample dataset of type: {dataset_type}',
            'file_name': 'sample.json',
            'file_type': '.json',
            'file_size': os.path.getsize(file_path),
            'storage_path': str(file_path),
            'num_samples': len(samples),
            'has_reference': any('expected_answer' in sample for sample in samples),
            'has_contexts': any('contexts' in sample for sample in samples),
            'sample_fields': list(samples[0].keys()) if samples else [],
            'created_by': 'system'
        }

        dataset_manager.create_dataset(dataset_data)

        return jsonify({
            'id': dataset_id,
            'name': dataset_name,
            'description': dataset_data['description'],
            'file_name': 'sample.json',
            'file_type': '.json',
            'num_samples': len(samples),
            'has_reference': dataset_data['has_reference'],
            'has_contexts': dataset_data['has_contexts'],
            'sample_fields': dataset_data['sample_fields'],
            'created_at': datetime.now().isoformat()
        }), 201

    except Exception as e:
        logger.error(f"Failed to generate sample dataset: {str(e)}")
        return jsonify({'error': 'Failed to generate sample dataset'}), 500


# ==================== 任务管理 API ====================

@evaluation_bp.route('/tasks', methods=['POST'])
@cross_origin()
def create_evaluation_task():
    """创建评测任务"""
    logger.info("🚀 收到创建评测任务请求")
    try:
        init_services()

        data = request.get_json()
        logger.info(f"📝 任务创建参数: {json.dumps(data, ensure_ascii=False)}")

        # 验证必填字段
        required_fields = ['chat_id', 'dataset_id', 'metrics']
        for field in required_fields:
            if field not in data:
                logger.warning(f"⚠️  缺少必填字段: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400

        logger.info(f"✅ 参数验证通过")

        # 创建任务
        task_id = str(uuid.uuid4())
        task_data = {
            'id': task_id,
            'name': data.get('name', f'Evaluation Task {datetime.now().strftime("%Y-%m-%d %H:%M")}'),
            'chat_id': data['chat_id'],
            'dataset_id': data['dataset_id'],
            'metrics': data['metrics'],
            'batch_size': data.get('batch_size', 10),
            'llm_model': data.get('llm_model'),
            'embedding_model': data.get('embedding_model'),
            'created_by': request.headers.get('X-User-Id', 'anonymous')
        }

        task_manager.create_task(task_data)

        # 异步执行评测任务
        if evaluation_service:
            import threading
            thread = threading.Thread(target=run_evaluation_task, args=(task_id,))
            thread.daemon = True
            thread.start()
        else:
            # 如果没有评测服务，设置为失败状态
            task_manager.update_task_status(task_id, 'failed', error_message='Evaluation service not available')

        return jsonify({
            'id': task_id,
            'name': task_data['name'],
            'chat_id': data['chat_id'],
            'dataset_id': data['dataset_id'],
            'metrics': data['metrics'],
            'batch_size': data['batch_size'],
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }), 201

    except Exception as e:
        logger.error(f"Failed to create evaluation task: {str(e)}")
        return jsonify({'error': 'Failed to create evaluation task'}), 500


def run_evaluation_task(task_id: str):
    """执行评测任务（后台任务）"""
    try:
        # 获取任务信息
        task = task_manager.get_task(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        # 获取数据集样本
        samples = dataset_manager.get_dataset_samples(task['dataset_id'])
        if not samples:
            task_manager.update_task_status(task_id, 'failed', error_message='No samples found in dataset')
            return

        # 更新任务状态为运行中，并设置总样本数
        task_manager.update_task_status(
            task_id,
            'running',
            total_samples=len(samples),
            processed_samples=0,
            progress=0
        )

        logger.info(f"🚀 开始 RAGAS 评测: {task_id}")
        logger.info(f"📊 Chat ID: {task['chat_id']}")
        logger.info(f"📊 Dataset ID: {task['dataset_id']}")
        logger.info(f"📊 评测指标: {task['metrics']}")
        logger.info(f"📊 样本数量: {len(samples)}")

        # 执行真正的 RAGAS 评测
        import asyncio
        from datetime import datetime

        # 定义进度回调函数 - 接收绝对进度值 (0-99)
        def progress_callback(progress: int):
            """更新任务进度 (接收绝对进度值 0-99)"""
            # 计算已处理样本数（估算值，用于显示）
            processed_samples = int((progress / 100) * len(samples))

            task_manager.update_task_status(
                task_id,
                'running',
                processed_samples=processed_samples,
                progress=progress
            )
            logger.info(f"📊 评测进度: {progress}% (约 {processed_samples}/{len(samples)} 样本)")

        # 在事件循环中运行异步评测
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 执行异步评测，传入进度回调
            evaluation_result = loop.run_until_complete(
                _run_rag_evaluation(task_id, task, samples, progress_callback)
            )
        finally:
            loop.close()

        # 保存评测报告
        try:
            # 准备报告数据
            report_data = {
                'task_id': task_id,
                'chat_id': task['chat_id'],
                'dataset_id': task['dataset_id'],
                'overall_scores': evaluation_result.get('overall_scores', {}),
                'detailed_scores': evaluation_result.get('detailed_scores', []),
                'evaluation_metadata': {
                    'metrics': task['metrics'],
                    'total_samples': len(samples),
                    'success_count': evaluation_result.get('success_count', 0),
                    'evaluation_time': evaluation_result.get('evaluation_time', 0)
                }
            }

            # 保存报告
            report_id = report_manager.save_report(report_data)
            logger.info(f"✅ 评测报告已保存: {report_id}")

        except Exception as e:
            logger.error(f"❌ 保存评测报告失败: {str(e)}")
            # 不影响任务状态，继续执行

        # 更新任务状态为完成
        task_manager.update_task_status(
            task_id,
            'completed',
            progress=100,
            processed_samples=len(samples)
        )

        logger.info(f"✅ RAGAS 评测任务完成: {task_id}")

    except Exception as e:
        logger.error(f"❌ 评测任务失败 {task_id}: {str(e)}")
        import traceback
        logger.error(f"🔍 详细错误信息: {traceback.format_exc()}")
        task_manager.update_task_status(task_id, 'failed', error_message=str(e))


async def _run_rag_evaluation(task_id: str, task: dict, samples: list, progress_callback=None) -> dict:
    """运行 RAGAS 评测"""
    try:
        # 确保评测服务已初始化
        from services.evaluation_service import evaluation_service

        if not evaluation_service:
            raise Exception("Evaluation service not available")

        # 执行评测，传入进度回调
        result = await evaluation_service.evaluate_knowledge_base(
            chat_id=task['chat_id'],
            dataset_id=task['dataset_id'],
            selected_metrics=task['metrics'],
            dataset_samples=samples,
            batch_size=task.get('batch_size', 10),
            progress_callback=progress_callback
        )

        logger.info(f"✅ RAGAS 评测成功完成")

        # 返回结果供后续处理
        return result

    except Exception as e:
        logger.error(f"❌ RAGAS 评测失败: {str(e)}")
        import traceback
        logger.error(f"🔍 详细错误信息: {traceback.format_exc()}")
        raise


@evaluation_bp.route('/tasks', methods=['GET'])
@cross_origin()
def list_tasks():
    """获取任务列表"""
    logger.info("📋 收到获取任务列表请求")
    try:
        init_services()

        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        status = request.args.get('status')

        logger.info(f"🔍 查询任务参数: limit={limit}, offset={offset}, status={status}")

        result = task_manager.get_tasks(limit, offset, status)
        task_count = len(result.get('tasks', []))

        logger.info(f"✅ 成功获取任务列表: 共 {task_count} 个任务 (总数: {result.get('total', 0)})")
        if task_count > 0:
            for task in result['tasks'][:3]:  # 只显示前3个任务详情
                logger.info(f"  - 任务 {task['id'][:8]}: {task['name']} | 状态: {task['status']} | 进度: {task.get('progress', 0)}%")

        return jsonify(result)

    except Exception as e:
        logger.error(f"❌ 获取任务列表失败: {str(e)}")
        import traceback
        logger.error(f"📋 详细错误信息: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to list tasks'}), 500


@evaluation_bp.route('/tasks/<task_id>', methods=['GET'])
@cross_origin()
def get_task_status(task_id: str):
    """获取任务状态"""
    try:
        init_services()

        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        return jsonify(task)

    except Exception as e:
        logger.error(f"Failed to get task status: {str(e)}")
        return jsonify({'error': 'Failed to get task status'}), 500


# ==================== 报告管理 API ====================

@evaluation_bp.route('/reports/<task_id>', methods=['GET'])
@cross_origin()
def get_evaluation_report(task_id: str):
    """获取评测报告"""
    try:
        init_services()

        report = report_manager.get_report(task_id)
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        return jsonify(report)

    except Exception as e:
        logger.error(f"Failed to get evaluation report: {str(e)}")
        return jsonify({'error': 'Failed to get evaluation report'}), 500


@evaluation_bp.route('/reports', methods=['GET'])
@cross_origin()
def list_reports():
    """获取报告列表"""
    try:
        init_services()

        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))

        result = report_manager.get_reports(limit, offset)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to list reports: {str(e)}")
        return jsonify({'error': 'Failed to list reports'}), 500


# ==================== 知识库适配器 API (为前端兼容) ====================

@evaluation_bp.route('/knowledgebases', methods=['GET'])
@cross_origin()
def list_knowledge_bases():
    """获取知识库列表 (适配前端接口，实际返回 RAGFlow 的对话助手列表)"""
    try:
        init_services()

        # 从 RAGFlow 获取对话助手列表
        import requests
        ragflow_api_key = os.getenv('RAGFLOW_API_KEY')
        ragflow_base_url = os.getenv('RAGFLOW_BASE_URL', 'http://localhost:9380')

        if not ragflow_api_key:
            return jsonify({
                'code': 1,
                'message': 'RAGFlow API key not configured'
            }), 500

        headers = {
            'Authorization': f'Bearer {ragflow_api_key}',
            'Content-Type': 'application/json'
        }

        # 请求 RAGFlow 的对话助手列表
        response = requests.get(
            f"{ragflow_base_url}/api/v1/chats",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            ragflow_data = response.json()

            if ragflow_data.get('code') == 0 and ragflow_data.get('data'):
                # 转换为前端期望的格式
                knowledge_bases = []
                for chat in ragflow_data['data']:
                    knowledge_bases.append({
                        'id': chat['id'],
                        'name': chat['name'],
                        'description': chat.get('description', 'RAGFlow 对话助手'),
                        'doc_num': len(chat.get('datasets', [])),
                        'llm': chat.get('llm', {}),
                        'created_at': chat.get('create_date'),
                        'status': chat.get('status')
                    })

                return jsonify({
                    'code': 0,
                    'data': {
                        'knowledgebases': knowledge_bases,
                        'total': len(knowledge_bases)
                    }
                })
            else:
                return jsonify({
                    'code': ragflow_data.get('code', -1),
                    'message': ragflow_data.get('message', 'Failed to fetch RAGFlow data')
                }), 400
        else:
            return jsonify({
                'code': response.status_code,
                'message': f'RAGFlow API request failed: {response.status_code}'
            }), response.status_code

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch RAGFlow chats: {str(e)}")
        return jsonify({
            'code': 500,
            'message': 'Failed to connect to RAGFlow'
        }), 500
    except Exception as e:
        logger.error(f"Failed to list knowledge bases: {str(e)}")
        return jsonify({
            'code': 500,
            'message': 'Failed to list knowledge bases'
        }), 500


@evaluation_bp.route('/knowledgebases/<kb_id>', methods=['GET'])
@cross_origin()
def get_knowledge_base(kb_id: str):
    """获取知识库详情 (适配前端接口)"""
    try:
        init_services()

        # 从 RAGFlow 获取对话助手详情
        import requests
        ragflow_api_key = os.getenv('RAGFLOW_API_KEY')
        ragflow_base_url = os.getenv('RAGFLOW_BASE_URL', 'http://localhost:9380')

        if not ragflow_api_key:
            return jsonify({
                'code': 1,
                'message': 'RAGFlow API key not configured'
            }), 500

        headers = {
            'Authorization': f'Bearer {ragflow_api_key}',
            'Content-Type': 'application/json'
        }

        response = requests.get(
            f"{ragflow_base_url}/api/v1/chats/{kb_id}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            chat_data = response.json()

            if chat_data.get('code') == 0 and chat_data.get('data'):
                chat = chat_data['data']
                # 转换为前端期望的格式
                knowledge_base = {
                    'id': chat['id'],
                    'name': chat['name'],
                    'description': chat.get('description', 'RAGFlow 对话助手'),
                    'doc_num': len(chat.get('datasets', [])),
                    'datasets': chat.get('datasets', []),
                    'llm': chat.get('llm', {}),
                    'prompt': chat.get('prompt', {}),
                    'created_at': chat.get('create_date'),
                    'updated_at': chat.get('update_date'),
                    'status': chat.get('status')
                }

                return jsonify({
                    'code': 0,
                    'data': knowledge_base
                })
            else:
                return jsonify({
                    'code': chat_data.get('code', -1),
                    'message': chat_data.get('message', 'Chat not found')
                }), 404
        else:
            return jsonify({
                'code': response.status_code,
                'message': f'RAGFlow API request failed: {response.status_code}'
            }), response.status_code

    except Exception as e:
        logger.error(f"Failed to get knowledge base: {str(e)}")
        return jsonify({
            'code': 500,
            'message': 'Failed to get knowledge base'
        }), 500


# ==================== 指标管理 API ====================

@evaluation_bp.route('/metrics', methods=['GET'])
@cross_origin()
def list_metrics():
    """获取可用评测指标"""
    try:
        init_services()

        # 直接返回基本指标列表，避免依赖 MetricsManager 的导入问题
        metrics = [
            {
                'name': 'faithfulness',
                'display_name': '忠实度',
                'description': '评估回答是否基于提供的上下文信息，不包含幻觉信息',
                'type': 'llm_based',
                'requires_contexts': True,
                'requires_reference': False,
                'default_enabled': True
            },
            {
                'name': 'answer_correctness',
                'display_name': '答案正确性',
                'description': '评估生成的答案与参考答案的匹配程度',
                'type': 'llm_based',
                'requires_contexts': False,
                'requires_reference': True,
                'default_enabled': True
            },
            {
                'name': 'context_precision',
                'display_name': '上下文精确度',
                'description': '评估检索到的上下文与问题的相关性',
                'type': 'llm_based',
                'requires_contexts': True,
                'requires_reference': False,
                'default_enabled': True
            },
            {
                'name': 'context_recall',
                'display_name': '上下文召回率',
                'description': '评估是否检索到回答问题所需的所有相关信息',
                'type': 'llm_based',
                'requires_contexts': True,
                'requires_reference': True,
                'default_enabled': True
            },
            {
                'name': 'answer_relevancy',
                'display_name': '答案相关性',
                'description': '评估生成的答案与原始问题的相关程度',
                'type': 'llm_based',
                'requires_contexts': False,
                'requires_reference': False,
                'default_enabled': True
            },
            {
                'name': 'answer_similarity',
                'display_name': '答案相似度',
                'description': '使用向量相似度评估答案的语义相似性',
                'type': 'traditional',
                'requires_contexts': False,
                'requires_reference': True,
                'default_enabled': False
            },
            {
                'name': 'response_time',
                'display_name': '响应时间',
                'description': '评估系统的响应速度（毫秒）',
                'type': 'traditional',
                'requires_contexts': False,
                'requires_reference': False,
                'default_enabled': False
            },
            {
                'name': 'token_usage',
                'display_name': 'Token 使用量',
                'description': '评估查询消耗的 Token 数量',
                'type': 'traditional',
                'requires_contexts': False,
                'requires_reference': False,
                'default_enabled': False
            }
        ]

        logger.info(f"Returning {len(metrics)} available metrics")
        return jsonify({'metrics': metrics})

    except Exception as e:
        logger.error(f"Failed to list metrics: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to list metrics'}), 500


# ==================== 系统状态 API ====================

@evaluation_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """健康检查"""
    try:
        init_services()

        # 检查数据库连接
        db_status = 'healthy'
        try:
            # 简单的数据库查询测试
            config_manager.get_setting('test_key')
        except Exception:
            db_status = 'unhealthy'

        # 检查评测服务
        evaluation_status = 'available' if evaluation_service else 'unavailable'

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'database': db_status,
                'evaluation_service': evaluation_status,
                'metrics_manager': 'available' if metrics_manager else 'unavailable'
            },
            'version': '1.0.0'
        })

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# ==================== 任务操作 API ====================

@evaluation_bp.route('/tasks/<task_id>/start', methods=['POST'])
@cross_origin()
def start_task(task_id):
    """开始任务"""
    try:
        init_services()

        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task['status'] not in ['pending', 'failed']:
            return jsonify({'error': 'Task cannot be started in current state'}), 400

        # 重置任务状态
        task_manager.update_task_status(task_id, 'pending')

        # 如果有评测服务，启动后台任务
        if evaluation_service:
            import threading
            thread = threading.Thread(target=run_evaluation_task, args=(task_id,))
            thread.daemon = True
            thread.start()
            logger.info(f"Task {task_id} started successfully")
            return jsonify({'message': 'Task started'})
        else:
            return jsonify({'error': 'Evaluation service not available'}), 503

    except Exception as e:
        logger.error(f"Failed to start task {task_id}: {str(e)}")
        return jsonify({'error': 'Failed to start task'}), 500

@evaluation_bp.route('/tasks/<task_id>/pause', methods=['POST'])
@cross_origin()
def pause_task(task_id):
    """暂停任务"""
    try:
        init_services()

        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task['status'] != 'running':
            return jsonify({'error': 'Task is not running'}), 400

        task_manager.update_task_status(task_id, 'paused')
        logger.info(f"Task {task_id} paused")
        return jsonify({'message': 'Task paused'})

    except Exception as e:
        logger.error(f"Failed to pause task {task_id}: {str(e)}")
        return jsonify({'error': 'Failed to pause task'}), 500

@evaluation_bp.route('/tasks/<task_id>/cancel', methods=['POST'])
@cross_origin()
def cancel_task(task_id):
    """取消任务"""
    try:
        init_services()

        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task['status'] in ['completed']:
            return jsonify({'error': 'Cannot cancel completed task'}), 400

        task_manager.update_task_status(task_id, 'cancelled')
        logger.info(f"Task {task_id} cancelled")
        return jsonify({'message': 'Task cancelled'})

    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {str(e)}")
        return jsonify({'error': 'Failed to cancel task'}), 500

@evaluation_bp.route('/tasks/<task_id>/retry', methods=['POST'])
@cross_origin()
def retry_task(task_id):
    """重试任务"""
    try:
        init_services()

        task = task_manager.get_task(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task['status'] not in ['failed', 'cancelled']:
            return jsonify({'error': 'Task can only be retried from failed or cancelled state'}), 400

        # 重置任务状态
        task_manager.update_task_status(task_id, 'pending', error_message=None)

        # 如果有评测服务，启动后台任务
        if evaluation_service:
            import threading
            thread = threading.Thread(target=run_evaluation_task, args=(task_id,))
            thread.daemon = True
            thread.start()
            logger.info(f"Task {task_id} retry started")
            return jsonify({'message': 'Task retry started'})
        else:
            return jsonify({'error': 'Evaluation service not available'}), 503

    except Exception as e:
        logger.error(f"Failed to retry task {task_id}: {str(e)}")
        return jsonify({'error': 'Failed to retry task'}), 500

@evaluation_bp.route('/tasks/<task_id>', methods=['DELETE'])
@cross_origin()
def delete_task(task_id):
    """删除任务"""
    logger.info(f"🗑️  收到删除任务请求: {task_id}")
    try:
        init_services()

        task = task_manager.get_task(task_id)
        if not task:
            logger.warning(f"⚠️  删除任务失败: 任务不存在 {task_id}")
            return jsonify({'error': 'Task not found'}), 404

        logger.info(f"📋 找到任务: {task['name']} | 状态: {task['status']}")

        if task['status'] == 'running':
            logger.warning(f"⚠️  无法删除运行中的任务: {task_id}")
            return jsonify({'error': 'Cannot delete running task'}), 400

        # 删除任务和相关报告
        logger.info(f"🗑️  开始删除任务: {task_id}")
        task_manager.delete_task(task_id)
        logger.info(f"✅ 任务删除成功: {task_id} - {task['name']}")
        return jsonify({'message': 'Task deleted'})

    except Exception as e:
        logger.error(f"❌ 删除任务失败 {task_id}: {str(e)}")
        import traceback
        logger.error(f"🗑️  详细错误信息: {traceback.format_exc()}")
        return jsonify({'error': 'Failed to delete task'}), 500


@evaluation_bp.route('/test-connection', methods=['POST'])
@cross_origin()
def test_api_connection():
    """
    测试API连接

    Request Body:
        {
            "provider": "openai",
            "api_key": "sk-...",
            "endpoint": "https://api.openai.com/v1",
            "model": "gpt-4"
        }

    Returns:
        测试结果
    """
    logger.info("🔗 收到API连接测试请求")

    try:
        data = request.get_json()
        logger.info(f"📝 连接配置: {json.dumps(data, ensure_ascii=False)}")

        provider = data.get('provider', 'openai')
        api_key = data.get('apiKey') or data.get('api_key')
        endpoint = data.get('endpoint')
        model = data.get('model', 'gpt-4')

        if not api_key:
            logger.warning("⚠️ API Key 不能为空")
            return jsonify({
                'success': False,
                'message': 'API Key 不能为空'
            }), 400

        # 根据 provider 设置默认 endpoint
        provider_endpoints = {
            'siliconflow': 'https://api.siliconflow.cn/v1',
            'deepseek': 'https://api.deepseek.com/v1',
            'zhipu': 'https://open.bigmodel.cn/api/paas/v4',
            'openai': None  # OpenAI 使用默认 endpoint
        }

        # 如果没有提供 endpoint，使用默认值
        if not endpoint and provider in provider_endpoints:
            endpoint = provider_endpoints[provider]

        logger.info(f"🚀 开始测试连接: {provider} - {model} - {endpoint}")

        # 测试连接
        from langchain_openai import ChatOpenAI
        import asyncio

        try:
            # 构造 LLM 配置
            llm_config = {
                'model': model,
                'api_key': api_key,
                'timeout': 10
            }

            if endpoint:
                llm_config['base_url'] = endpoint

            # 创建 LLM 实例并测试
            llm = ChatOpenAI(**llm_config)

            # 发送一个简单的测试消息
            try:
                # 尝试使用异步方式
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                response = loop.run_until_complete(llm.ainvoke("Hello"))
                loop.close()
            except:
                # 如果异步失败，使用同步方式
                response = llm.invoke("Hello")

            logger.info(f"✅ 连接测试成功: {provider}")
            return jsonify({
                'success': True,
                'message': '连接测试成功',
                'details': {
                    'provider': provider,
                    'model': model,
                    'response_length': len(str(response.content)) if hasattr(response, 'content') else 0
                }
            }), 200

        except Exception as test_error:
            logger.error(f"❌ 连接测试失败: {str(test_error)}")
            return jsonify({
                'success': False,
                'message': f'连接测试失败: {str(test_error)}'
            }), 200

    except Exception as e:
        logger.error(f"❌ 测试连接异常: {str(e)}")
        import traceback
        logger.error(f"🔗 详细错误信息: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'测试失败: {str(e)}'
        }), 500