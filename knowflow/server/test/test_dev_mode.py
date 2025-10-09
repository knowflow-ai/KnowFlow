#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试开发模式（dev模式）功能
验证 dev_mode 和临时文件清理的行为
"""

import os
import sys
from pathlib import Path

# 添加必要的路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'knowledgebases', 'mineru_parse'))

try:
    from utils import is_dev_mode, should_cleanup_temp_files
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)


def test_dev_mode_configuration():
    """测试开发模式配置"""

    print("🔧 测试开发模式和临时文件清理")

    # 测试不同的配置
    test_cases = [
        # (DEV, 期望的dev模式, 期望的清理行为)
        ('false', False, True),   # 生产模式 → 清理临时文件
        ('true', True, False),    # 开发模式 → 保留临时文件
        ('1', True, False),       # 开发模式 → 保留临时文件
        ('0', False, True),       # 生产模式 → 清理临时文件
        (None, False, True),      # 默认生产模式 → 清理临时文件
    ]

    for dev_val, expected_dev, expected_cleanup in test_cases:
        print(f"\n{'='*60}")
        print(f"🧪 测试配置: DEV={dev_val}")
        print(f"{'='*60}")

        # 备份原始环境变量
        original_dev = os.environ.get('DEV')

        try:
            # 设置测试环境变量
            if dev_val is not None:
                os.environ['DEV'] = dev_val
            else:
                os.environ.pop('DEV', None)

            # 测试函数结果
            actual_dev = is_dev_mode()
            actual_cleanup = should_cleanup_temp_files()

            print(f"📝 实际结果:")
            print(f"  • 开发模式: {actual_dev} (期望: {expected_dev})")
            print(f"  • 清理临时文件: {actual_cleanup} (期望: {expected_cleanup})")

            # 验证结果
            dev_correct = actual_dev == expected_dev
            cleanup_correct = actual_cleanup == expected_cleanup

            if dev_correct and cleanup_correct:
                print("✅ 测试通过")
            else:
                print("❌ 测试失败")
                if not dev_correct:
                    print(f"   开发模式不匹配: 实际{actual_dev} != 期望{expected_dev}")
                if not cleanup_correct:
                    print(f"   清理行为不匹配: 实际{actual_cleanup} != 期望{expected_cleanup}")

        except Exception as e:
            print(f"❌ 测试异常: {e}")

        finally:
            # 恢复原始环境变量
            if original_dev is not None:
                os.environ['DEV'] = original_dev
            else:
                os.environ.pop('DEV', None)


def test_dev_mode_logic():
    """测试开发模式的逻辑说明"""
    print(f"\n{'='*60}")
    print("📋 开发模式逻辑说明")
    print(f"{'='*60}")

    logic_explanation = """
开发模式配置逻辑：

1. 开发模式检查 (is_dev_mode):
   - DEV=true/1/yes/on → 启用开发模式
   - 其他值或未设置 → 关闭开发模式

2. 临时文件清理 (should_cleanup_temp_files):
   ⚠️ 已优化：清理行为完全由 dev_mode 决定
   - 开发模式 (dev_mode=True):  不清理临时文件（保留用于调试）
   - 生产模式 (dev_mode=False): 清理临时文件（节省磁盘空间）

3. 文档解析行为：
   - 开发模式：跳过MinerU，使用现有markdown文件
   - 生产模式：执行完整的MinerU处理流程

推荐配置：
• 开发环境：DEV=true (自动保留临时文件，快速测试)
• 生产环境：DEV=false 或不设置 (完整处理，自动清理临时文件)
"""

    print(logic_explanation)


def show_env_file_examples():
    """显示.env文件配置示例"""
    print(f"\n{'='*60}")
    print("📝 .env 文件配置示例")
    print(f"{'='*60}")

    examples = {
        "开发环境": """
# 开发环境配置
DEV=true  # 开发模式，自动保留临时文件
CHUNK_METHOD=smart
""",
        "生产环境": """
# 生产环境配置
DEV=false  # 或者不设置此变量，生产模式，自动清理临时文件
CHUNK_METHOD=advanced
""",
    }

    for env_name, config in examples.items():
        print(f"\n🔸 {env_name}:")
        print(config)


if __name__ == "__main__":
    test_dev_mode_configuration()
    test_dev_mode_logic()
    show_env_file_examples()
    print("\n✅ 开发模式测试完成！")
