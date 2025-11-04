#!/usr/bin/env python3
"""
数据库初始化脚本
在启动应用前运行，确保数据库结构正确
"""

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("🔧 初始化 RAG 评估系统数据库...")

    try:
        # 导入并初始化数据库
        from models.database import get_db_manager
        db = get_db_manager()

        print("✅ 数据库初始化完成")

        # 显示数据库信息
        import sqlite3
        conn = sqlite3.connect('evaluation.db')
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"\n📊 数据库表列表:")
        for table in tables:
            print(f"   - {table[0]}")

        conn.close()

        print("\n🎉 数据库已准备就绪！")
        return True

    except Exception as e:
        print(f"❌ 数据库初始化失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)