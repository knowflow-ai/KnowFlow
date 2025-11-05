"""
评测指标管理器
管理和配置各种评测指标
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MetricConfig:
    """指标配置"""
    name: str
    display_name: str
    description: str
    type: str  # 'llm_based', 'traditional', 'custom'
    requires_reference: bool
    requires_contexts: bool
    default_enabled: bool
    parameters: Optional[Dict] = None


class MetricsManager:
    """
    评测指标管理器
    负责管理所有可用的评测指标及其配置
    """

    def __init__(self):
        """初始化指标管理器"""
        self.metrics_registry = self._initialize_metrics_registry()
        self.custom_metrics = {}
        logger.info("MetricsManager initialized")

    def _initialize_metrics_registry(self) -> Dict[str, MetricConfig]:
        """初始化内置指标注册表"""
        return {
            'faithfulness': MetricConfig(
                name='faithfulness',
                display_name='忠实度',
                description='评估回答是否完全基于提供的上下文内容，不包含幻觉信息',
                type='llm_based',
                requires_reference=False,
                requires_contexts=True,
                default_enabled=True
            ),
            'answer_correctness': MetricConfig(
                name='answer_correctness',
                display_name='答案正确性',
                description='评估生成的答案与参考答案的匹配程度',
                type='llm_based',
                requires_reference=True,
                requires_contexts=False,
                default_enabled=True
            ),
            'context_precision': MetricConfig(
                name='context_precision',
                display_name='上下文精准度',
                description='评估检索到的上下文与问题的相关性',
                type='llm_based',
                requires_reference=False,
                requires_contexts=True,
                default_enabled=True
            ),
            'context_recall': MetricConfig(
                name='context_recall',
                display_name='上下文召回率',
                description='评估是否检索到了回答问题所需的所有相关信息',
                type='llm_based',
                requires_reference=True,
                requires_contexts=True,
                default_enabled=True
            ),
            'answer_relevancy': MetricConfig(
                name='answer_relevancy',
                display_name='答案相关性',
                description='评估生成的答案与原始问题的相关程度',
                type='llm_based',
                requires_reference=False,
                requires_contexts=False,
                default_enabled=True
            )
        }

    def get_metric(self, name: str) -> Optional[MetricConfig]:
        """
        获取指标配置

        Args:
            name: 指标名称

        Returns:
            指标配置对象
        """
        return self.metrics_registry.get(name) or self.custom_metrics.get(name)

    def list_metrics(self, filter_type: Optional[str] = None) -> List[MetricConfig]:
        """
        列出所有可用指标

        Args:
            filter_type: 过滤指标类型 ('llm_based', 'traditional', 'custom')

        Returns:
            指标配置列表
        """
        all_metrics = list(self.metrics_registry.values()) + list(self.custom_metrics.values())

        if filter_type:
            return [m for m in all_metrics if m.type == filter_type]
        return all_metrics

    def get_default_metrics(self) -> List[str]:
        """
        获取默认启用的指标

        Returns:
            默认指标名称列表
        """
        return [m.name for m in self.metrics_registry.values() if m.default_enabled]

    def validate_metrics_for_dataset(
        self,
        metric_names: List[str],
        has_reference: bool,
        has_contexts: bool
    ) -> Dict[str, Any]:
        """
        验证指标是否适用于给定的数据集

        Args:
            metric_names: 要验证的指标名称列表
            has_reference: 数据集是否包含参考答案
            has_contexts: 数据集是否包含上下文

        Returns:
            验证结果
        """
        valid_metrics = []
        invalid_metrics = []
        warnings = []

        for metric_name in metric_names:
            metric = self.get_metric(metric_name)

            if not metric:
                invalid_metrics.append({
                    'name': metric_name,
                    'reason': '指标不存在'
                })
                continue

            if metric.requires_reference and not has_reference:
                invalid_metrics.append({
                    'name': metric_name,
                    'reason': '该指标需要参考答案，但数据集中没有提供'
                })
            elif metric.requires_contexts and not has_contexts:
                invalid_metrics.append({
                    'name': metric_name,
                    'reason': '该指标需要上下文信息，但数据集中没有提供'
                })
            else:
                valid_metrics.append(metric_name)

                # 添加警告信息
                if metric.type == 'llm_based':
                    warnings.append(f"{metric.display_name} 需要调用 LLM，会产生费用")

        return {
            'valid': valid_metrics,
            'invalid': invalid_metrics,
            'warnings': warnings,
            'is_valid': len(invalid_metrics) == 0
        }

    def register_custom_metric(self, config: MetricConfig) -> bool:
        """
        注册自定义指标

        Args:
            config: 指标配置

        Returns:
            是否注册成功
        """
        if config.name in self.metrics_registry or config.name in self.custom_metrics:
            logger.warning(f"Metric {config.name} already exists")
            return False

        self.custom_metrics[config.name] = config
        logger.info(f"Custom metric {config.name} registered successfully")
        return True

    def get_metric_groups(self) -> Dict[str, List[MetricConfig]]:
        """
        按组获取指标

        Returns:
            分组的指标配置
        """
        groups = {
            '核心指标': [],
            '性能指标': [],
            '自定义指标': []
        }

        for metric in self.metrics_registry.values():
            if metric.default_enabled:
                groups['核心指标'].append(metric)
            elif metric.type == 'traditional':
                groups['性能指标'].append(metric)

        groups['自定义指标'] = list(self.custom_metrics.values())

        # 移除空组
        return {k: v for k, v in groups.items() if v}

    def get_metrics_statistics(self, evaluation_results: List[Dict]) -> Dict[str, Any]:
        """
        计算评测结果的统计信息

        Args:
            evaluation_results: 评测结果列表

        Returns:
            统计信息
        """
        if not evaluation_results:
            return {}

        statistics = {}

        # 收集所有指标
        all_metrics = set()
        for result in evaluation_results:
            all_metrics.update(result.get('overall_scores', {}).keys())

        # 计算每个指标的统计信息
        for metric_name in all_metrics:
            metric_scores = []
            for result in evaluation_results:
                if metric_name in result.get('overall_scores', {}):
                    score = result['overall_scores'][metric_name].get('mean')
                    if score is not None:
                        metric_scores.append(score)

            if metric_scores:
                import numpy as np
                statistics[metric_name] = {
                    'count': len(metric_scores),
                    'mean': float(np.mean(metric_scores)),
                    'std': float(np.std(metric_scores)),
                    'min': float(np.min(metric_scores)),
                    'max': float(np.max(metric_scores)),
                    'median': float(np.median(metric_scores))
                }

        return statistics

    def export_metrics_config(self) -> Dict:
        """
        导出所有指标配置

        Returns:
            指标配置字典
        """
        return {
            'builtin_metrics': {
                name: {
                    'display_name': config.display_name,
                    'description': config.description,
                    'type': config.type,
                    'requires_reference': config.requires_reference,
                    'requires_contexts': config.requires_contexts,
                    'default_enabled': config.default_enabled,
                    'parameters': config.parameters
                }
                for name, config in self.metrics_registry.items()
            },
            'custom_metrics': {
                name: {
                    'display_name': config.display_name,
                    'description': config.description,
                    'type': config.type,
                    'requires_reference': config.requires_reference,
                    'requires_contexts': config.requires_contexts,
                    'default_enabled': config.default_enabled,
                    'parameters': config.parameters
                }
                for name, config in self.custom_metrics.items()
            }
        }