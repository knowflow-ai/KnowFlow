#!/usr/bin/env python3
"""
初始化统计数据表结构
"""

import sqlite3
import os
import json
from datetime import datetime

def init_database():
    """初始化数据库表结构"""
    db_path = os.path.join(os.path.dirname(__file__), 'evaluation.db')

    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 创建 evaluation_reports 表（如果不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_reports (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                report_data TEXT,
                overall_scores TEXT,
                detailed_scores TEXT,
                evaluation_metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES evaluation_tasks (id)
            )
        ''')

        # 检查并添加必要字段
        # 检查 evaluation_tasks 表是否有必要字段
        cursor.execute('PRAGMA table_info(evaluation_tasks)')
        columns = [row[1] for row in cursor.fetchall()]

        required_columns = ['id', 'name', 'status', 'progress', 'chat_id', 'dataset_id',
                          'metrics', 'created_at', 'completed_at', 'started_at', 'error_message']

        for col in required_columns:
            if col not in columns:
                if col in ['progress', 'created_at', 'completed_at', 'started_at', 'error_message']:
                    cursor.execute(f'ALTER TABLE evaluation_tasks ADD COLUMN {col} {get_column_type(col)}')
                else:
                    cursor.execute(f'ALTER TABLE evaluation_tasks ADD COLUMN {col} TEXT')

        # 检查 datasets 表
        cursor.execute('PRAGMA table_info(datasets)')
        dataset_columns = [row[1] for row in cursor.fetchall()]

        required_dataset_columns = ['id', 'name', 'file_type', 'file_size', 'num_samples',
                                  'has_reference', 'has_contexts', 'created_at']

        for col in required_dataset_columns:
            if col not in dataset_columns:
                if col in ['file_size', 'num_samples']:
                    cursor.execute(f'ALTER TABLE datasets ADD COLUMN {col} INTEGER')
                elif col in ['has_reference', 'has_contexts']:
                    cursor.execute(f'ALTER TABLE datasets ADD COLUMN {col} INTEGER DEFAULT 0')
                else:
                    cursor.execute(f'ALTER TABLE datasets ADD COLUMN {col} TEXT')

        # 提交更改
        conn.commit()
        print("✅ 数据库表结构初始化成功")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_column_type(column_name):
    """获取字段类型"""
    if column_name in ['progress', 'file_size', 'num_samples']:
        return 'INTEGER DEFAULT 0'
    elif column_name in ['has_reference', 'has_contexts']:
        return 'INTEGER DEFAULT 0'
    elif column_name in ['created_at', 'completed_at', 'started_at']:
        return 'TIMESTAMP'
    else:
        return 'TEXT'

if __name__ == '__main__':
    init_database()