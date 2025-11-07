"""
RAG 评估系统数据库模型
使用 SQLite 作为轻量级数据库
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_path: str = None):
        # 使用绝对路径，确保数据持久化
        if db_path is None:
            # 使用 backend/ 目录下的 evaluation.db，避免因工作目录不同创建多个数据库
            base_dir = os.path.dirname(os.path.abspath(__file__))  # models/ 目录
            backend_dir = os.path.dirname(base_dir)  # backend/ 目录
            db_path = os.path.join(backend_dir, "evaluation.db")
        elif not os.path.isabs(db_path):
            # 如果是相对路径，也基于 backend/ 目录
            base_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(base_dir)
            db_path = os.path.join(backend_dir, db_path)

        self.db_path = db_path
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
        return conn

    def init_database(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 1. API 配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL UNIQUE,
                provider VARCHAR(50) NOT NULL,
                api_key VARCHAR(500) NOT NULL,
                endpoint VARCHAR(500),
                model VARCHAR(100),
                embedding_model VARCHAR(100),
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 4000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_default BOOLEAN DEFAULT 0
            )
        ''')

        # 2. 系统设置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key VARCHAR(100) NOT NULL UNIQUE,
                value TEXT,
                description TEXT,
                category VARCHAR(50) DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 3. 数据集表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS datasets (
                id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                file_name VARCHAR(200),
                file_type VARCHAR(10),
                file_size INTEGER,
                storage_path VARCHAR(500),
                num_samples INTEGER DEFAULT 0,
                has_reference BOOLEAN DEFAULT 0,
                has_contexts BOOLEAN DEFAULT 0,
                sample_fields TEXT,  -- JSON 格式存储字段信息
                status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed
                progress INTEGER DEFAULT 0,
                error_message TEXT,
                created_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 4. 评测任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_tasks (
                id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(200),
                chat_id VARCHAR(50) NOT NULL,
                dataset_id VARCHAR(50) NOT NULL,
                llm_model VARCHAR(100),
                embedding_model VARCHAR(100),
                metrics TEXT,  -- JSON 格式存储指标列表
                status VARCHAR(20) DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                total_samples INTEGER DEFAULT 0,
                processed_samples INTEGER DEFAULT 0,
                batch_size INTEGER DEFAULT 10,
                error_message TEXT,
                created_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
            )
        ''')

        # 5. 评测报告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id VARCHAR(50) NOT NULL UNIQUE,
                chat_id VARCHAR(50) NOT NULL,
                dataset_id VARCHAR(50) NOT NULL,
                overall_scores TEXT,  -- JSON 格式存储总体分数
                detailed_scores TEXT,  -- JSON 格式存储详细分数
                evaluation_metadata TEXT,  -- JSON 格式存储元数据
                report_file_path VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES evaluation_tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
            )
        ''')

        # 6. 评测日志表 (可选，用于调试)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id VARCHAR(50),
                level VARCHAR(10),  -- INFO, ERROR, DEBUG
                message TEXT,
                details TEXT,  -- JSON 格式存储详细信息
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES evaluation_tasks(id) ON DELETE CASCADE
            )
        ''')

        # 创建索引提高查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_datasets_name ON datasets(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON evaluation_tasks(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON evaluation_tasks(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_task_id ON evaluation_reports(task_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_settings_category ON system_settings(category)')

        # 插入默认系统设置
        self.insert_default_settings(cursor)

        # 插入默认API配置（如果不存在）
        self.insert_default_api_config(cursor)

        conn.commit()
        conn.close()

    def insert_default_settings(self, cursor):
        """插入默认系统设置"""
        default_settings = [
            ('ragflow_base_url', 'http://localhost:9380', 'RAGFlow 服务地址', 'ragflow'),
            ('default_llm_provider', 'siliconflow', '默认 LLM 提供商', 'llm'),
            ('default_llm_model', 'Qwen/Qwen2.5-32B-Instruct', '默认 LLM 模型', 'llm'),
            ('default_embedding_model', 'BAAI/bge-m3', '默认 Embedding 模型', 'llm'),
            ('evaluation_timeout', '300', '评测超时时间(秒)', 'evaluation'),
            ('evaluation_max_workers', '2', '评测最大并发数', 'evaluation'),
            ('evaluation_max_retries', '2', '评测最大重试次数', 'evaluation'),
            ('max_upload_size', '104857600', '最大上传文件大小(字节)', 'system'),
        ]

        for key, value, description, category in default_settings:
            cursor.execute('''
                INSERT OR IGNORE INTO system_settings (key, value, description, category)
                VALUES (?, ?, ?, ?)
            ''', (key, value, description, category))

    def insert_default_api_config(self, cursor):
        """插入默认API配置（如果不存在）"""
        # 检查是否已有API配置
        cursor.execute('SELECT COUNT(*) as count FROM api_configs')
        count = cursor.fetchone()['count']

        if count == 0:
            # 从环境变量获取默认配置
            api_key = os.getenv('SILICONFLOW_API_KEY', 'sk-your-api-key-here')
            endpoint = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
            provider = os.getenv('DEFAULT_LLM_PROVIDER', 'siliconflow')
            model = os.getenv('DEFAULT_LLM_MODEL', 'Qwen/Qwen2.5-32B-Instruct')
            embedding_model = os.getenv('DEFAULT_EMBEDDING_MODEL', 'BAAI/bge-m3')

            cursor.execute('''
                INSERT INTO api_configs (
                    name, provider, api_key, endpoint, model, embedding_model,
                    temperature, max_tokens, is_default
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'Default API Config',
                provider,
                api_key,
                endpoint,
                model,
                embedding_model,
                0.7,
                4000,
                True  # 设为默认配置
            ))

    # API 配置相关操作
    def create_api_config(self, config_data: Dict[str, Any]) -> str:
        """创建 API 配置"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO api_configs (name, provider, api_key, endpoint, model, embedding_model, temperature, max_tokens, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            config_data['name'],
            config_data['provider'],
            config_data['api_key'],
            config_data.get('endpoint'),
            config_data.get('model'),
            config_data.get('embedding_model'),
            config_data.get('temperature', 0.7),
            config_data.get('max_tokens', 4000),
            config_data.get('is_default', False)
        ))

        config_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return str(config_id)

    def get_api_configs(self) -> List[Dict[str, Any]]:
        """获取所有 API 配置"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM api_configs ORDER BY is_default DESC, created_at DESC')
        configs = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return configs

    def get_default_api_config(self) -> Optional[Dict[str, Any]]:
        """获取默认 API 配置"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM api_configs WHERE is_default = 1 LIMIT 1')
        row = cursor.fetchone()

        conn.close()
        return dict(row) if row else None

    def update_api_config(self, config_id: int, config_data: Dict[str, Any]) -> bool:
        """更新 API 配置"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 动态构建 UPDATE 语句，只更新传入的字段
        update_fields = []
        update_values = []

        field_mapping = {
            'name': 'name',
            'provider': 'provider',
            'api_key': 'api_key',
            'endpoint': 'endpoint',
            'model': 'model',
            'embedding_model': 'embedding_model',
            'temperature': 'temperature',
            'max_tokens': 'max_tokens'
        }

        for key, db_field in field_mapping.items():
            if key in config_data:
                update_fields.append(f'{db_field} = ?')
                update_values.append(config_data[key])

        if not update_fields:
            conn.close()
            return False

        update_fields.append('updated_at = CURRENT_TIMESTAMP')
        update_values.append(config_id)

        sql = f"UPDATE api_configs SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(sql, tuple(update_values))

        # 如果设置为默认配置，先将其他配置设为非默认
        if config_data.get('is_default', False):
            cursor.execute('UPDATE api_configs SET is_default = 0 WHERE id != ?', (config_id,))
            cursor.execute('UPDATE api_configs SET is_default = 1 WHERE id = ?', (config_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def delete_api_config(self, config_id: int) -> bool:
        """删除 API 配置"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM api_configs WHERE id = ?', (config_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    # 系统设置相关操作
    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取系统设置"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT value FROM system_settings WHERE key = ?', (key,))
        row = cursor.fetchone()

        conn.close()
        return row['value'] if row else default

    def update_setting(self, key: str, value: str, description: str = None, category: str = 'general'):
        """更新系统设置"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO system_settings (key, value, description, category, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (key, value, description, category))

        conn.commit()
        conn.close()

    # 数据集相关操作
    def create_dataset(self, dataset_data: Dict[str, Any]) -> str:
        """创建数据集"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO datasets (
                id, name, description, file_name, file_type, file_size,
                storage_path, num_samples, has_reference, has_contexts,
                sample_fields, status, progress, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            dataset_data['id'],
            dataset_data['name'],
            dataset_data.get('description'),
            dataset_data.get('file_name'),
            dataset_data.get('file_type'),
            dataset_data.get('file_size'),
            dataset_data.get('storage_path'),
            dataset_data.get('num_samples', 0),
            dataset_data.get('has_reference', False),
            dataset_data.get('has_contexts', False),
            json.dumps(dataset_data.get('sample_fields', [])),
            dataset_data.get('status', 'pending'),
            dataset_data.get('progress', 0),
            dataset_data.get('created_by', 'system')
        ))

        conn.commit()
        conn.close()
        return dataset_data['id']

    def update_dataset_status(self, dataset_id: str, status: str, progress: int = None, 
                             error_message: str = None, num_samples: int = None,
                             has_reference: bool = None, has_contexts: bool = None):
        """更新数据集状态"""
        conn = self.get_connection()
        cursor = conn.cursor()

        update_fields = ['status = ?', 'updated_at = CURRENT_TIMESTAMP']
        update_values = [status]

        if progress is not None:
            update_fields.append('progress = ?')
            update_values.append(progress)

        if error_message is not None:
            update_fields.append('error_message = ?')
            update_values.append(error_message)
            
        if num_samples is not None:
            update_fields.append('num_samples = ?')
            update_values.append(num_samples)
            
        if has_reference is not None:
            update_fields.append('has_reference = ?')
            update_values.append(has_reference)
            
        if has_contexts is not None:
            update_fields.append('has_contexts = ?')
            update_values.append(has_contexts)

        update_values.append(dataset_id)

        cursor.execute(f'''
            UPDATE datasets
            SET {', '.join(update_fields)}
            WHERE id = ?
        ''', update_values)

        conn.commit()
        conn.close()

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """获取单个数据集"""
        conn = self.get_connection()
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

    def get_datasets(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """获取数据集列表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) as total FROM datasets')
        total = cursor.fetchone()['total']

        cursor.execute('''
            SELECT * FROM datasets
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))

        datasets = []
        for row in cursor.fetchall():
            dataset = dict(row)
            if dataset['sample_fields']:
                dataset['sample_fields'] = json.loads(dataset['sample_fields'])
            datasets.append(dataset)

        conn.close()
        return {
            'datasets': datasets,
            'total': total,
            'limit': limit,
            'offset': offset
        }

    # 评测任务相关操作
    def create_evaluation_task(self, task_data: Dict[str, Any]) -> str:
        """创建评测任务"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO evaluation_tasks (
                id, name, chat_id, dataset_id, llm_model, embedding_model,
                metrics, batch_size, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_data['id'],
            task_data.get('name'),
            task_data['chat_id'],
            task_data['dataset_id'],
            task_data.get('llm_model'),
            task_data.get('embedding_model'),
            json.dumps(task_data.get('metrics', [])),
            task_data.get('batch_size', 10),
            task_data.get('created_by', 'anonymous')
        ))

        conn.commit()
        conn.close()
        return task_data['id']

    def update_task_status(self, task_id: str, status: str, progress: int = None,
                          error_message: str = None, processed_samples: int = None,
                          total_samples: int = None):
        """更新任务状态"""
        conn = self.get_connection()
        cursor = conn.cursor()

        update_fields = ['status = ?']
        update_values = [status]

        if progress is not None:
            update_fields.append('progress = ?')
            update_values.append(progress)

        if error_message is not None:
            update_fields.append('error_message = ?')
            update_values.append(error_message)

        if processed_samples is not None:
            update_fields.append('processed_samples = ?')
            update_values.append(processed_samples)

        if total_samples is not None:
            update_fields.append('total_samples = ?')
            update_values.append(total_samples)

        if status == 'running' and progress == 0:
            update_fields.append('started_at = CURRENT_TIMESTAMP')
        elif status in ['completed', 'failed']:
            update_fields.append('completed_at = CURRENT_TIMESTAMP')

        update_values.append(task_id)

        cursor.execute(f'''
            UPDATE evaluation_tasks
            SET {', '.join(update_fields)}
            WHERE id = ?
        ''', update_values)

        conn.commit()
        conn.close()

    # 评测报告相关操作
    def save_evaluation_report(self, report_data: Dict[str, Any]) -> str:
        """保存评测报告"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 生成报告文件
        report_file_path = self._generate_report_file(report_data)

        cursor.execute('''
            INSERT OR REPLACE INTO evaluation_reports (
                task_id, chat_id, dataset_id, overall_scores, detailed_scores,
                evaluation_metadata, report_file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            report_data['task_id'],
            report_data['chat_id'],
            report_data['dataset_id'],
            json.dumps(report_data.get('overall_scores', {})),
            json.dumps(report_data.get('detailed_scores', [])),
            json.dumps(report_data.get('evaluation_metadata', {})),
            report_file_path
        ))

        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return str(report_id)

    def get_evaluation_report(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取评测报告"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM evaluation_reports
            WHERE task_id = ?
        ''', (task_id,))

        row = cursor.fetchone()
        if row:
            report = dict(row)
            # 解析 JSON 字段
            for field in ['overall_scores', 'detailed_scores', 'evaluation_metadata']:
                if report[field]:
                    report[field] = json.loads(report[field])
            conn.close()
            return report

        conn.close()
        return None

    def _generate_report_file(self, report_data: Dict[str, Any]) -> str:
        """生成评测报告文件"""
        # 创建报告目录
        reports_dir = Path("tmp/evaluation/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_id = report_data.get('task_id', 'unknown')[:8]  # 取前8位避免文件名过长
        filename = f"evaluation_report_{task_id}_{timestamp}.json"
        file_path = reports_dir / filename

        # 准备报告数据
        report_content = {
            "task_info": {
                "task_id": report_data.get('task_id'),
                "chat_id": report_data.get('chat_id'),
                "dataset_id": report_data.get('dataset_id'),
                "created_at": datetime.now().isoformat(),
                "status": "completed"
            },
            "overall_scores": report_data.get('overall_scores', {}),
            "detailed_scores": report_data.get('detailed_scores', []),
            "evaluation_metadata": report_data.get('evaluation_metadata', {}),
            "summary": {
                "total_questions": len(report_data.get('detailed_scores', [])),
                "success_rate": report_data.get('overall_scores', {}).get('success_rate', 0),
                "average_score": report_data.get('overall_scores', {}).get('average_score', 0)
            }
        }

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_content, f, ensure_ascii=False, indent=2)

        # 返回相对路径
        return str(file_path)


# 全局数据库实例
db_manager = None

def get_db_manager() -> DatabaseManager:
    """获取数据库管理器实例"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager