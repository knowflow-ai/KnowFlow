#!/usr/bin/env python3
"""
KnowFlow 完整 API 测试运行器
整合 RAGFlow 和 KnowFlow Server 的所有 API 测试
"""

import sys
import subprocess
import json
import os
from datetime import datetime

def run_test_script(script_path, script_name):
    """运行单个测试脚本"""
    print(f"\n{'='*80}")
    print(f"运行 {script_name}")
    print(f"{'='*80}\n")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"⏱️  测试超时 (10分钟)")
        return False
    except Exception as e:
        print(f"❌ 运行测试时出错: {e}")
        return False

def load_test_results(result_file):
    """加载测试结果"""
    if os.path.exists(result_file):
        with open(result_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def merge_test_results(ragflow_results, knowflow_results):
    """合并测试结果"""
    return {
        "timestamp": datetime.now().isoformat(),
        "ragflow_apis": {
            "results": ragflow_results,
            "summary": get_summary(ragflow_results)
        },
        "knowflow_server_apis": {
            "results": knowflow_results,
            "summary": get_summary(knowflow_results)
        },
        "overall_summary": get_overall_summary(ragflow_results, knowflow_results)
    }

def get_summary(results):
    """生成测试摘要"""
    total = len(results)
    success = sum(1 for r in results if r.get("status") == "SUCCESS")
    failed = sum(1 for r in results if r.get("status") in ["FAILED", "ERROR"])
    skipped = sum(1 for r in results if r.get("status") == "SKIP")

    # 按分类统计
    categories = {}
    for r in results:
        cat = r.get("category", "Unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
        categories[cat]["total"] += 1
        if r.get("status") == "SUCCESS":
            categories[cat]["success"] += 1
        elif r.get("status") in ["FAILED", "ERROR"]:
            categories[cat]["failed"] += 1
        elif r.get("status") == "SKIP":
            categories[cat]["skipped"] += 1

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "success_rate": round(success / total * 100, 2) if total > 0 else 0,
        "effective_success_rate": round(success / (total - skipped) * 100, 2) if (total - skipped) > 0 else 0,
        "by_category": categories
    }

def get_overall_summary(ragflow_results, knowflow_results):
    """生成总体摘要"""
    all_results = ragflow_results + knowflow_results
    summary = get_summary(all_results)
    summary["ragflow_count"] = len(ragflow_results)
    summary["knowflow_count"] = len(knowflow_results)
    return summary

def print_final_summary(merged_results):
    """打印最终摘要"""
    overall = merged_results["overall_summary"]
    ragflow = merged_results["ragflow_apis"]["summary"]
    knowflow = merged_results["knowflow_server_apis"]["summary"]

    print("\n" + "="*80)
    print("📊 完整测试总结")
    print("="*80)

    print(f"\n🔷 RAGFlow APIs:")
    print(f"   总计: {ragflow['total']} 个")
    print(f"   成功: {ragflow['success']} ✅")
    print(f"   失败: {ragflow['failed']} ❌")
    print(f"   跳过: {ragflow['skipped']} ⚠️")
    print(f"   成功率: {ragflow['success_rate']}% (有效: {ragflow['effective_success_rate']}%)")

    print(f"\n🔷 KnowFlow Server APIs:")
    print(f"   总计: {knowflow['total']} 个")
    print(f"   成功: {knowflow['success']} ✅")
    print(f"   失败: {knowflow['failed']} ❌")
    print(f"   跳过: {knowflow['skipped']} ⚠️")
    print(f"   成功率: {knowflow['success_rate']}% (有效: {knowflow['effective_success_rate']}%)")

    print(f"\n🔷 总体:")
    print(f"   总计: {overall['total']} 个API")
    print(f"   成功: {overall['success']} ✅")
    print(f"   失败: {overall['failed']} ❌")
    print(f"   跳过: {overall['skipped']} ⚠️")
    print(f"   总体成功率: {overall['success_rate']}%")
    print(f"   有效成功率: {overall['effective_success_rate']}%")

    print("\n📋 按分类统计 (RAGFlow):")
    for cat, stats in sorted(ragflow['by_category'].items()):
        rate = round(stats['success'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0
        print(f"   {cat}: {stats['success']}/{stats['total']} ({rate}%)")

    print("\n📋 按分类统计 (KnowFlow Server):")
    for cat, stats in sorted(knowflow['by_category'].items()):
        rate = round(stats['success'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0
        print(f"   {cat}: {stats['success']}/{stats['total']} ({rate}%)")

def main():
    """主函数"""
    print("🚀 KnowFlow 完整 API 测试")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    # 测试脚本路径
    ragflow_script = os.path.join(scripts_dir, "test_ragflow_complete_api.py")
    knowflow_script = os.path.join(scripts_dir, "test_knowflow_server_api.py")

    # 结果文件路径
    ragflow_results_file = os.path.join(scripts_dir, "ragflow_api_test_results.json")
    knowflow_results_file = os.path.join(scripts_dir, "knowflow_server_api_test_results.json")
    merged_results_file = os.path.join(scripts_dir, "all_apis_test_results.json")

    # 运行测试
    ragflow_success = run_test_script(ragflow_script, "RAGFlow API 测试")
    knowflow_success = run_test_script(knowflow_script, "KnowFlow Server API 测试")

    # 加载测试结果
    ragflow_results = load_test_results(ragflow_results_file)
    knowflow_results = load_test_results(knowflow_results_file)

    # 合并结果
    merged_results = merge_test_results(ragflow_results, knowflow_results)

    # 保存合并结果
    with open(merged_results_file, 'w', encoding='utf-8') as f:
        json.dump(merged_results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 合并的测试结果已保存到: {merged_results_file}")

    # 打印最终摘要
    print_final_summary(merged_results)

    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回状态
    if ragflow_success and knowflow_success:
        print("\n✅ 所有测试完成")
        return 0
    else:
        print("\n⚠️  部分测试未完全通过")
        return 1

if __name__ == "__main__":
    sys.exit(main())
