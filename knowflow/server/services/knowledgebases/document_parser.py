"""
文档解析模块 - 仅保留数据库连接工具函数

注意：此模块中的 perform_parse() 等解析函数已废弃。
现在所有文档解析都通过 RAGFlow 的统一 API (document_run) 和 TaskQueue 系统进行。

保留的函数：
- _get_db_connection(): 数据库连接工具函数（被多个模块使用）
"""

import mysql.connector
from database import DB_CONFIG


def _get_db_connection():
    """创建数据库连接"""
    return mysql.connector.connect(**DB_CONFIG)
