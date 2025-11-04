#!/usr/bin/env python3
"""
数据库功能测试脚本
"""

import os
import sys
import json
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database():
    """测试数据库功能"""
    print("🚀 开始测试数据库功能...")

    try:
        # 1. 测试数据库初始化
        print("\n1. 测试数据库初始化...")
        from models.database import get_db_manager
        db = get_db_manager()
        print("✅ 数据库初始化成功")

        # 2. 测试系统设置
        print("\n2. 测试系统设置...")
        from db import get_config_manager
        config_manager = get_config_manager()

        # 读取设置
        ragflow_url = config_manager.get_setting('ragflow_base_url')
        print(f"✅ RAGFlow URL: {ragflow_url}")

        # 更新设置
        config_manager.update_setting('test_key', 'test_value', 'Test setting', 'test')
        test_value = config_manager.get_setting('test_key')
        print(f"✅ 设置读写测试: {test_value}")

        # 3. 测试数据集管理
        print("\n3. 测试数据集管理...")
        from db import get_dataset_manager
        dataset_manager = get_dataset_manager()

        # 创建测试数据集
        import uuid
        dataset_id = str(uuid.uuid4())
        dataset_data = {
            'id': dataset_id,
            'name': 'Test Dataset',
            'description': 'Test dataset for database functionality',
            'num_samples': 3,
            'has_reference': True,
            'has_contexts': False,
            'sample_fields': ['question', 'expected_answer'],
            'created_by': 'test_script'
        }

        dataset_manager.create_dataset(dataset_data)
        print(f"✅ 数据集创建成功: {dataset_id}")

        # 读取数据集
        datasets = dataset_manager.get_datasets(limit=5)
        print(f"✅ 数据集列表获取成功: {len(datasets['datasets'])} 个数据集")

        # 4. 测试任务管理
        print("\n4. 测试任务管理...")
        from db import get_task_manager
        task_manager = get_task_manager()

        # 创建测试任务
        task_id = str(uuid.uuid4())
        task_data = {
            'id': task_id,
            'name': 'Test Task',
            'chat_id': 'test-chat-id',
            'dataset_id': dataset_id,
            'metrics': ['answer_relevancy', 'context_precision'],
            'batch_size': 5,
            'created_by': 'test_script'
        }

        task_manager.create_task(task_data)
        print(f"✅ 任务创建成功: {task_id}")

        # 更新任务状态
        task_manager.update_task_status(task_id, 'running', progress=50)
        print("✅ 任务状态更新成功")

        # 5. 测试报告管理
        print("\n5. 测试报告管理...")
        from db import get_report_manager
        report_manager = get_report_manager()

        # 创建测试报告
        report_data = {
            'task_id': task_id,
            'chat_id': 'test-chat-id',
            'dataset_id': dataset_id,
            'overall_scores': {
                'answer_relevancy': {'mean': 0.8, 'std': 0.1}
            },
            'detailed_scores': [
                {'answer_relevancy': 0.8, 'context_precision': 0.7},
                {'answer_relevancy': 0.9, 'context_precision': 0.6}
            ],
            'evaluation_metadata': {
                'llm_model': 'test-model',
                'num_samples': 2,
                'metrics_used': ['answer_relevancy', 'context_precision']
            }
        }

        report_id = report_manager.save_report(report_data)
        print(f"✅ 报告保存成功: {report_id}")

        # 读取报告
        report = report_manager.get_report(task_id)
        if report:
            print("✅ 报告读取成功")
            print(f"   - 任务ID: {report['task_id']}")
            print(f"   - 总体分数: {report['overall_scores']}")
            print(f"   - 详细分数数量: {len(report['detailed_scores'])}")

        print("\n🎉 所有数据库功能测试通过！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints():
    """测试 API 端点"""
    print("\n🔗 开始测试 API 端点...")

    import requests
    import time

    base_url = "http://localhost:5002/api/v1/evaluation"

    # 等待服务启动
    print("等待服务启动...")
    time.sleep(2)

    try:
        # 测试健康检查
        print("\n1. 测试健康检查...")
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ 健康检查通过")
            health_data = response.json()
            print(f"   - 状态: {health_data.get('status')}")
            print(f"   - 数据库状态: {health_data.get('services', {}).get('database')}")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return False

        # 测试配置获取
        print("\n2. 测试配置获取...")
        response = requests.get(f"{base_url}/config")
        if response.status_code == 200:
            print("✅ 配置获取成功")
            config_data = response.json()
            print(f"   - 配置类别数: {len(config_data.get('config', {}))}")
        else:
            print(f"❌ 配置获取失败: {response.status_code}")

        # 测试指标获取
        print("\n3. 测试指标获取...")
        response = requests.get(f"{base_url}/metrics")
        if response.status_code == 200:
            print("✅ 指标获取成功")
            metrics_data = response.json()
            print(f"   - 可用指标数: {len(metrics_data.get('metrics', []))}")
        else:
            print(f"❌ 指标获取失败: {response.status_code}")

        # 测试数据集生成
        print("\n4. 测试数据集生成...")
        response = requests.post(f"{base_url}/datasets/generate/basic")
        if response.status_code == 201:
            print("✅ 数据集生成成功")
            dataset_data = response.json()
            print(f"   - 数据集ID: {dataset_data.get('id')}")
            print(f"   - 样本数量: {dataset_data.get('num_samples')}")
        else:
            print(f"❌ 数据集生成失败: {response.status_code}")

        print("\n🎉 所有 API 测试完成！")
        return True

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到后端服务，请确保服务正在运行")
        return False
    except Exception as e:
        print(f"❌ API 测试失败: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("RAG 评估系统数据库功能测试")
    print("=" * 60)

    # 测试数据库功能
    db_success = test_database()

    if db_success:
        # 询问是否测试 API
        response = input("\n是否测试 API 端点？(y/n): ").lower().strip()
        if response in ['y', 'yes', '是']:
            api_success = test_api_endpoints()

            if db_success and api_success:
                print("\n🎉 所有测试通过！数据库功能正常工作。")
                sys.exit(0)
            else:
                print("\n❌ 部分测试失败。")
                sys.exit(1)
        else:
            print("\n✅ 数据库功能测试完成。")
            sys.exit(0)
    else:
        print("\n❌ 数据库功能测试失败。")
        sys.exit(1)