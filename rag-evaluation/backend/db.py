"""
简化的数据库操作模块
提供基本的 CRUD 操作接口
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.database import get_db_manager, DatabaseManager


class ConfigManager:
    """配置管理器 - API 配置和系统设置"""

    def __init__(self):
        self.db = get_db_manager()

    # API 配置管理
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
            'temperature': config.get('temperature'),
            'maxTokens': config.get('max_tokens'),
            'isDefault': config.get('is_default'),
            'createdAt': config.get('created_at'),
            'updatedAt': config.get('updated_at')
        }

    def update_api_config(self, config_id: int, config_data: Dict[str, Any]) -> bool:
        """更新 API 配置"""
        return self.db.update_api_config(config_id, config_data)

    # 系统设置管理
    def get_settings(self, category: str = None) -> List[Dict[str, Any]]:
        """获取系统设置"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        if category:
            cursor.execute('''
                SELECT * FROM system_settings WHERE category = ? ORDER BY key
            ''', (category,))
        else:
            cursor.execute('SELECT * FROM system_settings ORDER BY category, key')

        settings = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return settings

    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取单个设置"""
        return self.db.get_setting(key, default)

    def update_setting(self, key: str, value: Any, description: str = None, category: str = 'general'):
        """更新设置"""
        return self.db.update_setting(key, str(value), description, category)

    def update_settings_batch(self, settings: Dict[str, Any]):
        """批量更新设置"""
        for key, value in settings.items():
            self.update_setting(key, value)


class DatasetManager:
    """数据集管理器"""

    def __init__(self):
        self.db = get_db_manager()

    def create_dataset(self, dataset_data: Dict[str, Any]) -> str:
        """创建数据集"""
        return self.db.create_dataset(dataset_data)

    def get_datasets(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """获取数据集列表"""
        return self.db.get_datasets(limit, offset)

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """获取单个数据集"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM datasets WHERE id = ?', (dataset_id,))
        row = cursor.fetchone()

        if row:
            dataset = dict(row)
            if dataset['sample_fields']:
                dataset['sample_fields'] = json.loads(dataset['sample_fields'])
            conn.close()
            return dataset

        conn.close()
        return None

    def get_dataset_samples(self, dataset_id: str, offset: int = 0, limit: Optional[int] = None) -> List[Dict]:
        """获取数据集样本"""
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            raise FileNotFoundError(f"Dataset not found: {dataset_id}")

        # 使用扁平文件结构: tmp/datasets/{dataset_id}.json
        storage_base = os.path.join(os.getcwd(), "tmp", "datasets")
        dataset_file = os.path.join(storage_base, f"{dataset_id}.json")

        if not os.path.exists(dataset_file):
            raise FileNotFoundError(f"Dataset samples not found: {dataset_file}")

        with open(dataset_file, 'r', encoding='utf-8') as f:
            samples = json.load(f)

        # 应用分页
        if limit:
            samples = samples[offset:offset + limit]
        else:
            samples = samples[offset:]

        return samples

    
    def delete_dataset(self, dataset_id: str) -> bool:
        """删除数据集"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM datasets WHERE id = ?', (dataset_id,))
        affected_rows = cursor.rowcount

        conn.commit()
        conn.close()
        return affected_rows > 0


class TaskManager:
    """评测任务管理器"""

    def __init__(self):
        self.db = get_db_manager()

    def create_task(self, task_data: Dict[str, Any]) -> str:
        """创建评测任务"""
        return self.db.create_evaluation_task(task_data)

    def get_tasks(self, limit: int = 20, offset: int = 0, status: str = None) -> Dict[str, Any]:
        """获取任务列表"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # 构建查询条件
        where_clause = ""
        params = []
        if status:
            where_clause = "WHERE status = ?"
            params.append(status)

        # 获取总数
        cursor.execute(f'SELECT COUNT(*) as total FROM evaluation_tasks {where_clause}', params)
        total = cursor.fetchone()['total']

        # 获取任务列表
        params.extend([limit, offset])
        cursor.execute(f'''
            SELECT * FROM evaluation_tasks
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', params)

        tasks = []
        for row in cursor.fetchall():
            task = dict(row)
            # 解析 JSON 字段
            if task['metrics']:
                task['metrics'] = json.loads(task['metrics'])
            tasks.append(task)

        conn.close()
        return {
            'tasks': tasks,
            'total': total,
            'limit': limit,
            'offset': offset
        }

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取单个任务"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM evaluation_tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()

        if row:
            task = dict(row)
            if task['metrics']:
                task['metrics'] = json.loads(task['metrics'])
            conn.close()
            return task

        conn.close()
        return None

    def update_task_status(self, task_id: str, status: str, **kwargs):
        """更新任务状态"""
        self.db.update_task_status(task_id, status, **kwargs)

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM evaluation_tasks WHERE id = ?', (task_id,))
        affected_rows = cursor.rowcount

        conn.commit()
        conn.close()
        return affected_rows > 0


class ReportManager:
    """评测报告管理器"""

    def __init__(self):
        self.db = get_db_manager()

    def save_report(self, report_data: Dict[str, Any]) -> str:
        """保存评测报告"""
        return self.db.save_evaluation_report(report_data)

    def get_report(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取评测报告"""
        return self.db.get_evaluation_report(task_id)

    def get_reports(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """获取报告列表"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) as total FROM evaluation_reports')
        total = cursor.fetchone()['total']

        cursor.execute('''
            SELECT r.*, t.name as task_name, d.name as dataset_name
            FROM evaluation_reports r
            JOIN evaluation_tasks t ON r.task_id = t.id
            JOIN datasets d ON r.dataset_id = d.id
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))

        reports = []
        for row in cursor.fetchall():
            report = dict(row)
            # 解析 JSON 字段
            for field in ['overall_scores', 'detailed_scores', 'evaluation_metadata']:
                if report[field]:
                    try:
                        report[field] = json.loads(report[field])
                    except json.JSONDecodeError:
                        report[field] = {}
            reports.append(report)

        conn.close()
        return {
            'reports': reports,
            'total': total,
            'limit': limit,
            'offset': offset
        }


# 全局管理器实例
config_manager = None
dataset_manager = None
task_manager = None
report_manager = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    global config_manager
    if config_manager is None:
        config_manager = ConfigManager()
    return config_manager


def get_dataset_manager() -> DatasetManager:
    """获取数据集管理器实例"""
    global dataset_manager
    if dataset_manager is None:
        dataset_manager = DatasetManager()
    return dataset_manager


def get_task_manager() -> TaskManager:
    """获取任务管理器实例"""
    global task_manager
    if task_manager is None:
        task_manager = TaskManager()
    return task_manager


def get_report_manager() -> ReportManager:
    """获取报告管理器实例"""
    global report_manager
    if report_manager is None:
        report_manager = ReportManager()
    return report_manager