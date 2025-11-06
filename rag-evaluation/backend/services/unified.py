"""
统一的服务管理器
整合所有数据访问和业务逻辑，避免重复代码
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from models.database import get_db_manager, DatabaseManager
from config import Config
from services.dataset_manager import DatasetManager as FileDatasetManager
from services.metrics_manager import MetricsManager

# 设置日志
logger = logging.getLogger(__name__)


class ConfigService:
    """统一的配置管理服务"""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._config = Config()

    def get_api_configs(self) -> List[Dict[str, Any]]:
        """获取所有 API 配置"""
        configs = self.db.get_api_configs()
        # 隐藏 API Key 的一部分显示
        for config in configs:
            if config['api_key']:
                config['api_key'] = self._mask_api_key(config['api_key'])
        return configs

    def _mask_api_key(self, api_key: str) -> str:
        """遮蔽 API Key 的敏感部分"""
        if len(api_key) <= 8:
            return '*' * len(api_key)
        return api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]

    def create_api_config(self, config_data: Dict[str, Any]) -> str:
        """创建 API 配置"""
        return self.db.create_api_config(config_data)

    def get_default_api_config(self) -> Optional[Dict[str, Any]]:
        """获取默认 API 配置（返回驼峰命名）"""
        config = self.db.get_default_api_config()
        if not config:
            return None

        # 转换为驼峰命名
        return {
            'id': config.get('id'),
            'name': config.get('name'),
            'provider': config.get('provider'),
            'apiKey': config.get('api_key'),  # 返回完整 key 用于内部使用
            'endpoint': config.get('endpoint'),
            'model': config.get('model'),
            'embeddingModel': config.get('embedding_model'),
            'temperature': config.get('temperature', 0),
            'maxTokens': config.get('max_tokens', 2000),
        }

    def update_api_config(self, config_id: str, config_data: Dict[str, Any]) -> bool:
        """更新 API 配置"""
        return self.db.update_api_config(config_id, config_data)

    def delete_api_config(self, config_id: str) -> bool:
        """删除 API 配置"""
        return self.db.delete_api_config(config_id)

    def set_default_config(self, config_id: str) -> bool:
        """设置默认配置"""
        return self.db.set_default_config(config_id)


class DatasetService:
    """统一的数据集管理服务"""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.file_manager = FileDatasetManager()

    def get_datasets(self, offset: int = 0, limit: int = 10) -> Dict[str, Any]:
        """获取数据集列表"""
        return self.db.get_datasets(offset, limit)

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """获取数据集详情"""
        return self.db.get_dataset(dataset_id)

    def create_dataset(self, file, name: str, description: str = "") -> str:
        """创建数据集"""
        # 使用文件管理器处理文件上传
        dataset_id = self.file_manager.create_dataset(file, name, description)

        # 同步到数据库
        file_info = self.file_manager.get_dataset_info(dataset_id)
        if file_info:
            self.db.create_dataset_record({
                'id': dataset_id,
                'name': name,
                'description': description,
                'file_name': file_info['file_name'],
                'file_type': file_info['file_type'],
                'num_samples': file_info['num_samples'],
                'has_reference': file_info['has_reference'],
                'has_contexts': file_info['has_contexts'],
                'created_at': datetime.now().isoformat(),
                'created_by': 'system'  # TODO: 从认证信息获取
            })

        return dataset_id

    def delete_dataset(self, dataset_id: str) -> bool:
        """删除数据集"""
        # 从文件系统删除
        success = self.file_manager.delete_dataset(dataset_id)

        # 从数据库删除
        if success:
            success = self.db.delete_dataset(dataset_id)

        return success

    def batch_delete_datasets(self, dataset_ids: List[str]) -> Dict[str, Any]:
        """批量删除数据集"""
        deleted_count = 0
        failed_count = 0
        failed_ids = []

        for dataset_id in dataset_ids:
            if self.delete_dataset(dataset_id):
                deleted_count += 1
            else:
                failed_count += 1
                failed_ids.append(dataset_id)

        return {
            'message': f'删除完成：成功 {deleted_count} 个，失败 {failed_count} 个',
            'deleted_count': deleted_count,
            'total_count': len(dataset_ids),
            'failed_count': failed_count,
            'failed_ids': failed_ids
        }


class TaskService:
    """统一的任务管理服务"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_tasks(self, offset: int = 0, limit: int = 10, status: Optional[str] = None) -> Dict[str, Any]:
        """获取任务列表"""
        return self.db.get_tasks(offset, limit, status)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        return self.db.get_task(task_id)

    def create_task(self, task_data: Dict[str, Any]) -> str:
        """创建任务"""
        return self.db.create_task(task_data)

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """更新任务"""
        return self.db.update_task(task_id, updates)

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        return self.db.delete_task(task_id)

    def batch_delete_tasks(self, task_ids: List[str]) -> Dict[str, Any]:
        """批量删除任务（跳过运行中的任务）"""
        deleted_count = 0
        failed_count = 0
        running_count = 0
        failed_ids = []
        running_tasks = []

        for task_id in task_ids:
            task = self.get_task(task_id)
            if not task:
                failed_count += 1
                failed_ids.append(task_id)
                continue

            if task.get('status') == 'running':
                running_count += 1
                running_tasks.append(task.get('name', task_id))
                continue

            if self.delete_task(task_id):
                deleted_count += 1
            else:
                failed_count += 1
                failed_ids.append(task_id)

        return {
            'message': f'删除完成：成功 {deleted_count} 个，失败 {failed_count} 个，跳过运行中 {running_count} 个',
            'deleted_count': deleted_count,
            'total_count': len(task_ids),
            'failed_count': failed_count,
            'failed_ids': failed_ids,
            'running_count': running_count,
            'running_tasks': running_tasks
        }

    def get_task_statistics(self) -> Dict[str, Any]:
        """获取任务统计数据"""
        return self.db.get_task_statistics()


class ReportService:
    """统一的报告管理服务"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_reports(self, kb_id: Optional[str] = None, start_date: Optional[str] = None,
                   end_date: Optional[str] = None, offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """获取报告列表"""
        return self.db.get_evaluation_reports(kb_id, start_date, end_date, offset, limit)

    def get_report(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取报告详情"""
        return self.db.get_evaluation_report(task_id)

    def delete_report(self, task_id: str) -> bool:
        """删除报告"""
        return self.db.delete_evaluation_report(task_id)

    def batch_delete_reports(self, task_ids: List[str]) -> Dict[str, Any]:
        """批量删除报告"""
        deleted_count = 0
        failed_count = 0
        failed_ids = []

        for task_id in task_ids:
            if self.delete_report(task_id):
                deleted_count += 1
            else:
                failed_count += 1
                failed_ids.append(task_id)

        return {
            'message': f'删除完成：成功 {deleted_count} 个，失败 {failed_count} 个',
            'deleted_count': deleted_count,
            'total_count': len(task_ids),
            'failed_count': failed_count,
            'failed_ids': failed_ids
        }

    def get_report_statistics(self) -> Dict[str, Any]:
        """获取报告统计数据"""
        return self.db.get_report_statistics()


class EvaluationService:
    """统一的评测服务"""

    def __init__(self):
        self.db = get_db_manager()
        self.config = ConfigService(self.db)
        self.dataset = DatasetService(self.db)
        self.task = TaskService(self.db)
        self.report = ReportService(self.db)
        self.metrics = MetricsManager()

        # 从配置中获取默认设置
        self.api_config = self.config.get_default_api_config()
        if self.api_config:
            logger.info(f"✅ 从数据库加载配置: provider={self.api_config.get('provider')}, "
                       f"model={self.api_config.get('model')}, "
                       f"embeddingModel={self.api_config.get('embeddingModel')}")
        else:
            logger.warning("⚠️ 未找到默认API配置")
            self.api_config = {}


class ServiceManager:
    """服务管理器 - 统一管理所有服务"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.db = get_db_manager()
        self.config = ConfigService(self.db)
        self.dataset = DatasetService(self.db)
        self.task = TaskService(self.db)
        self.report = ReportService(self.db)
        self.evaluation = EvaluationService()

        self._initialized = True
        logger.info("🎯 ServiceManager 初始化完成")

    def get_statistics(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        task_stats = self.task.get_task_statistics()
        dataset_stats = self.dataset.get_datasets()
        report_stats = self.report.get_report_statistics()

        # 计算健康度分数
        health_score = self._calculate_health_score(task_stats, report_stats)

        return {
            'health_score': health_score,
            'total_evaluations': task_stats.get('total_count', 0),
            'active_datasets': dataset_stats.get('total', 0),
            'avg_processing_time': task_stats.get('avg_processing_time', 0),
            'task_status_counts': task_stats.get('status_counts', {}),
            'total_tasks': task_stats.get('total_count', 0),
            'running_tasks': task_stats.get('running_count', 0),
            'completed_tasks': task_stats.get('total_completed', 0),
            'failed_tasks': task_stats.get('failed_count', 0),
            'metric_scores': report_stats.get('metric_averages', []),
        }

    def _calculate_health_score(self, task_stats: Dict, report_stats: Dict) -> int:
        """计算系统健康度分数 - 仅基于报告质量指标"""
        # 根据报告质量调整分数
        metric_scores = report_stats.get('metric_averages', [])
        if metric_scores:
            # 计算所有指标的平均分数，并转换为0-100分制
            avg_score = sum(m.get('score', 0) for m in metric_scores) / len(metric_scores)
            score = int(avg_score * 100)  # 直接使用平均指标分数，转换为百分制
        else:
            # 如果没有报告数据，返回0分
            score = 0

        return max(0, min(100, score))


# 全局服务管理器实例
service_manager = ServiceManager()

# 便捷的工厂函数
def get_service_manager() -> ServiceManager:
    """获取服务管理器实例"""
    return service_manager

def get_config_service() -> ConfigService:
    """获取配置服务实例"""
    return service_manager.config

def get_dataset_service() -> DatasetService:
    """获取数据集服务实例"""
    return service_manager.dataset

def get_task_service() -> TaskService:
    """获取任务服务实例"""
    return service_manager.task

def get_report_service() -> ReportService:
    """获取报告服务实例"""
    return service_manager.report

def get_evaluation_service() -> EvaluationService:
    """获取评测服务实例"""
    return service_manager.evaluation