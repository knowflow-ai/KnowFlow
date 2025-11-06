"""
共享的评测工具模块
消除重复代码，提供统一的工具函数
"""

import logging
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class ResponseFormatter:
    """统一的响应格式化器"""

    @staticmethod
    def success(data: Any = None, message: str = "操作成功", status_code: int = 200) -> tuple:
        """统一成功响应格式"""
        response = {'success': True, 'message': message}
        if data is not None:
            response['data'] = data
        return response, status_code

    @staticmethod
    def error(message: str, details: Any = None, status_code: int = 500) -> tuple:
        """统一错误响应格式"""
        error_response = {
            'success': False,
            'error': message
        }
        if details is not None and os.getenv('FLASK_ENV') == 'development':
            error_response['details'] = str(details)
        return error_response, status_code

    @staticmethod
    def validation_error(message: str) -> tuple:
        """参数验证错误"""
        return ResponseFormatter.error(message, status_code=400)

    @staticmethod
    def not_found_error(message: str = "资源不存在") -> tuple:
        """404错误"""
        return ResponseFormatter.error(message, status_code=404)

class ConfigValidator:
    """统一的配置验证器"""

    REQUIRED_FIELDS = {
        'api_config': ['provider', 'apiKey', 'model'],
        'dataset': ['name'],
        'task': ['chat_id', 'dataset_id', 'metrics'],
        'evaluation': ['question', 'answer']
    }

    @classmethod
    def validate(cls, data: Dict[str, Any], validation_type: str) -> Optional[str]:
        """
        验证配置数据

        Args:
            data: 要验证的数据
            validation_type: 验证类型 ('api_config', 'dataset', 'task', 'evaluation')

        Returns:
            如果验证失败，返回错误信息；否则返回None
        """
        if not isinstance(data, dict):
            return "数据格式错误，必须是字典类型"

        required_fields = cls.REQUIRED_FIELDS.get(validation_type, [])
        for field in required_fields:
            if field not in data or not data[field]:
                return f"缺少必需字段: {field}"

        # 特定类型的额外验证
        if validation_type == 'api_config':
            return cls._validate_api_config(data)
        elif validation_type == 'task':
            return cls._validate_task_config(data)

        return None

    @classmethod
    def _validate_api_config(cls, config: Dict[str, Any]) -> Optional[str]:
        """验证API配置"""
        provider = config.get('provider', '').lower()

        if provider == 'siliconflow' and not config.get('apiKey'):
            return "SiliconFlow需要API Key"

        if provider in ['deepseek', 'zhipu'] and not config.get('apiKey'):
            return f"{provider.title()}需要API Key"

        return None

    @classmethod
    def _validate_task_config(cls, task: Dict[str, Any]) -> Optional[str]:
        """验证任务配置"""
        metrics = task.get('metrics', [])
        if not isinstance(metrics, list) or not metrics:
            return "metrics字段必须是非空数组"

        valid_metrics = [
            'faithfulness', 'answer_correctness', 'context_precision',
            'context_recall', 'answer_relevancy'
        ]

        for metric in metrics:
            if metric not in valid_metrics:
                return f"不支持的评测指标: {metric}"

        return None

class FileManager:
    """统一的文件管理工具"""

    @staticmethod
    def ensure_directory(path: str) -> None:
        """确保目录存在"""
        Path(path).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_file_size(file_path: str) -> int:
        """获取文件大小（字节）"""
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0

    @staticmethod
    def get_file_extension(filename: str) -> str:
        """获取文件扩展名"""
        return Path(filename).suffix.lower()

    @staticmethod
    def is_allowed_file(filename: str, allowed_extensions: List[str]) -> bool:
        """检查文件扩展名是否允许"""
        ext = FileManager.get_file_extension(filename)
        return ext in allowed_extensions

    @staticmethod
    def secure_filename(filename: str) -> str:
        """安全化文件名"""
        # 简单的安全化处理，实际部署时可以使用werkzeug.utils.secure_filename
        import re
        filename = re.sub(r'[^\w\s.-]', '', filename.strip())
        return filename[:100]  # 限制长度

class DateTimeUtils:
    """统一的日期时间工具"""

    @staticmethod
    def now_iso() -> str:
        """获取当前ISO格式时间"""
        return datetime.now().isoformat()

    @staticmethod
    def parse_iso(date_str: str) -> Optional[datetime]:
        """解析ISO格式时间"""
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes}分钟"
        else:
            hours = int(seconds // 3600)
            return f"{hours}小时"

class MetricsCalculator:
    """统一的指标计算工具"""

    @staticmethod
    def calculate_average(scores: List[float]) -> float:
        """计算平均值"""
        return sum(scores) / len(scores) if scores else 0.0

    @staticmethod
    def calculate_weighted_average(scores: List[Dict[str, float]], weight_key: str = 'weight') -> float:
        """计算加权平均值"""
        if not scores:
            return 0.0

        weighted_sum = sum(score.get('score', 0) * score.get(weight_key, 1) for score in scores)
        total_weight = sum(score.get(weight_key, 1) for score in scores)

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    @staticmethod
    def normalize_score(score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """标准化分数到指定范围"""
        return max(min_val, min(max_val, score))

class ErrorLogger:
    """统一的错误日志记录器"""

    @staticmethod
    def log_error(error: Exception, context: str = "操作失败") -> None:
        """记录错误日志"""
        logger.error(f"{context}: {type(error).__name__}: {str(error)}")

    @staticmethod
    def log_warning(message: str, context: str = "警告") -> None:
        """记录警告日志"""
        logger.warning(f"{context}: {message}")

    @staticmethod
    def log_info(message: str, context: str = "信息") -> None:
        """记录信息日志"""
        logger.info(f"{context}: {message}")

class APIClientValidator:
    """统一的API客户端验证"""

    SUPPORTED_PROVIDERS = ['siliconflow', 'deepseek', 'zhipu', 'openai']

    PROVIDER_ENDPOINTS = {
        'siliconflow': 'https://api.siliconflow.cn/v1',
        'deepseek': 'https://api.deepseek.com/v1',
        'zhipu': 'https://open.bigmodel.cn/api/paas/v4',
        'openai': None  # 使用默认endpoint
    }

    @classmethod
    def validate_provider(cls, provider: str) -> Optional[str]:
        """验证LLM提供商"""
        if provider.lower() not in cls.SUPPORTED_PROVIDERS:
            return f"不支持的LLM提供商: {provider}，支持的提供商: {', '.join(cls.SUPPORTED_PROVIDERS)}"
        return None

    @classmethod
    def get_default_endpoint(cls, provider: str) -> Optional[str]:
        """获取提供商的默认endpoint"""
        return cls.PROVIDER_ENDPOINTS.get(provider.lower())

class BatchOperationHelper:
    """批量操作辅助工具"""

    @staticmethod
    def process_batch(items: List[str], operation_func, success_message: str = "操作完成") -> Dict[str, Any]:
        """
        处理批量操作

        Args:
            items: 要处理的项目列表
            operation_func: 操作函数，接受单个项目参数，返回(bool, optional_info)
            success_message: 成功消息模板

        Returns:
            操作结果统计
        """
        success_count = 0
        failed_count = 0
        failed_items = []
        running_count = 0
        running_items = []

        for item in items:
            try:
                success, info = operation_func(item)
                if success:
                    success_count += 1
                elif info == 'running':
                    running_count += 1
                    running_items.append(item)
                else:
                    failed_count += 1
                    failed_items.append(item)
            except Exception as e:
                failed_count += 1
                failed_items.append(item)
                ErrorLogger.log_error(e, f"批量操作项目 {item} 失败")

        return {
            'message': f"{success_message}：成功 {success_count} 个，失败 {failed_count} 个，跳过运行中 {running_count} 个",
            'success_count': success_count,
            'failed_count': failed_count,
            'running_count': running_count,
            'total_count': len(items),
            'failed_items': failed_items,
            'running_items': running_items
        }

# 导出所有工具类
__all__ = [
    'ResponseFormatter',
    'ConfigValidator',
    'FileManager',
    'DateTimeUtils',
    'MetricsCalculator',
    'ErrorLogger',
    'APIClientValidator',
    'BatchOperationHelper'
]