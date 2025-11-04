"""
评测数据集管理器
负责管理评测数据集的上传、解析、存储和检索
"""

import os
import json
import logging
import pandas as pd
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid
from pathlib import Path
import aiofiles
import chardet

logger = logging.getLogger(__name__)


class DatasetManager:
    """
    评测数据集管理器
    支持多种格式的数据集上传和管理
    """

    def __init__(self, storage_path: str = "/data/evaluation/datasets"):
        """
        初始化数据集管理器

        Args:
            storage_path: 数据集存储路径
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"DatasetManager initialized with storage path: {storage_path}")

    async def upload_dataset(
        self,
        file_content: bytes,
        file_name: str,
        dataset_name: str,
        description: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        上传评测数据集

        Args:
            file_content: 文件内容
            file_name: 文件名
            dataset_name: 数据集名称
            description: 数据集描述
            user_id: 用户 ID

        Returns:
            数据集信息
        """
        try:
            # 生成数据集 ID
            dataset_id = str(uuid.uuid4())

            # 确定文件类型
            file_extension = Path(file_name).suffix.lower()

            # 创建数据集目录
            dataset_dir = self.storage_path / dataset_id
            dataset_dir.mkdir(exist_ok=True)

            # 保存原始文件
            original_file_path = dataset_dir / f"original{file_extension}"
            async with aiofiles.open(original_file_path, 'wb') as f:
                await f.write(file_content)

            # 解析数据集
            samples = await self._parse_dataset(file_content, file_extension)

            # 保存解析后的数据
            processed_file_path = dataset_dir / "processed.json"
            async with aiofiles.open(processed_file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(samples, ensure_ascii=False, indent=2))

            # 创建数据集元数据
            metadata = {
                'id': dataset_id,
                'name': dataset_name,
                'description': description,
                'file_name': file_name,
                'file_type': file_extension,
                'num_samples': len(samples),
                'has_reference': any('expected_answer' in s or 'reference' in s for s in samples),
                'has_contexts': any('contexts' in s or 'reference_contexts' in s for s in samples),
                'created_at': datetime.now().isoformat(),
                'created_by': user_id,
                'storage_path': str(dataset_dir),
                'sample_fields': list(samples[0].keys()) if samples else []
            }

            # 保存元数据
            metadata_file = dataset_dir / "metadata.json"
            async with aiofiles.open(metadata_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(metadata, ensure_ascii=False, indent=2))

            logger.info(f"Dataset {dataset_id} uploaded successfully with {len(samples)} samples")
            return metadata

        except Exception as e:
            logger.error(f"Failed to upload dataset: {str(e)}")
            raise

    async def _parse_dataset(self, file_content: bytes, file_extension: str) -> List[Dict]:
        """
        解析不同格式的数据集文件

        Args:
            file_content: 文件内容
            file_extension: 文件扩展名

        Returns:
            解析后的样本列表
        """
        samples = []

        if file_extension in ['.csv']:
            samples = self._parse_csv(file_content)
        elif file_extension in ['.json', '.jsonl']:
            samples = self._parse_json(file_content)
        elif file_extension in ['.xlsx', '.xls']:
            samples = self._parse_excel(file_content)
        elif file_extension in ['.txt']:
            samples = self._parse_text(file_content)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

        # 验证和标准化字段
        samples = self._standardize_samples(samples)

        return samples

    def _parse_csv(self, file_content: bytes) -> List[Dict]:
        """解析 CSV 文件"""
        # 检测编码
        encoding = chardet.detect(file_content)['encoding'] or 'utf-8'

        # 读取 CSV
        import io
        df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)

        # 转换为字典列表
        samples = df.to_dict('records')

        return samples

    def _parse_json(self, file_content: bytes) -> List[Dict]:
        """解析 JSON/JSONL 文件"""
        content = file_content.decode('utf-8')
        samples = []

        # 尝试解析为 JSON 数组
        try:
            samples = json.loads(content)
            if not isinstance(samples, list):
                samples = [samples]
        except json.JSONDecodeError:
            # 尝试解析为 JSONL
            for line in content.strip().split('\n'):
                if line.strip():
                    samples.append(json.loads(line))

        return samples

    def _parse_excel(self, file_content: bytes) -> List[Dict]:
        """解析 Excel 文件"""
        import io
        df = pd.read_excel(io.BytesIO(file_content))
        samples = df.to_dict('records')
        return samples

    def _parse_text(self, file_content: bytes) -> List[Dict]:
        """解析纯文本文件（每行一个问题）"""
        content = file_content.decode('utf-8')
        samples = []

        for line in content.strip().split('\n'):
            if line.strip():
                samples.append({'question': line.strip()})

        return samples

    def _standardize_samples(self, samples: List[Dict]) -> List[Dict]:
        """
        标准化样本字段名

        Args:
            samples: 原始样本列表

        Returns:
            标准化后的样本列表
        """
        field_mappings = {
            'query': 'question',
            'prompt': 'question',
            'input': 'question',
            'answer': 'expected_answer',
            'reference': 'expected_answer',
            'ground_truth': 'expected_answer',
            'context': 'contexts',
            'documents': 'contexts',
            'reference_context': 'reference_contexts',
            'golden_contexts': 'reference_contexts'
        }

        standardized = []

        for sample in samples:
            new_sample = {}

            for key, value in sample.items():
                # 标准化字段名
                standardized_key = field_mappings.get(key.lower(), key)
                new_sample[standardized_key] = value

            # 确保必要字段存在
            if 'question' not in new_sample:
                logger.warning(f"Sample missing 'question' field: {new_sample}")
                continue

            # 处理上下文字段
            if 'contexts' in new_sample and isinstance(new_sample['contexts'], str):
                new_sample['contexts'] = [new_sample['contexts']]

            if 'reference_contexts' in new_sample and isinstance(new_sample['reference_contexts'], str):
                new_sample['reference_contexts'] = [new_sample['reference_contexts']]

            standardized.append(new_sample)

        return standardized

    async def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """
        获取数据集信息

        Args:
            dataset_id: 数据集 ID

        Returns:
            数据集信息
        """
        dataset_dir = self.storage_path / dataset_id

        if not dataset_dir.exists():
            raise FileNotFoundError(f"Dataset {dataset_id} not found")

        # 读取元数据
        metadata_file = dataset_dir / "metadata.json"
        async with aiofiles.open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.loads(await f.read())

        return metadata

    async def get_dataset_samples(
        self,
        dataset_id: str,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        获取数据集样本

        Args:
            dataset_id: 数据集 ID
            offset: 偏移量
            limit: 限制数量

        Returns:
            样本列表
        """
        dataset_dir = self.storage_path / dataset_id
        processed_file = dataset_dir / "processed.json"

        if not processed_file.exists():
            raise FileNotFoundError(f"Dataset samples not found for {dataset_id}")

        async with aiofiles.open(processed_file, 'r', encoding='utf-8') as f:
            samples = json.loads(await f.read())

        # 应用分页
        if limit:
            samples = samples[offset:offset + limit]
        else:
            samples = samples[offset:]

        return samples

    async def list_datasets(
        self,
        user_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        列出数据集

        Args:
            user_id: 用户 ID（可选，用于过滤）
            offset: 偏移量
            limit: 限制数量

        Returns:
            数据集列表
        """
        datasets = []

        # 遍历所有数据集目录
        for dataset_dir in self.storage_path.iterdir():
            if dataset_dir.is_dir():
                metadata_file = dataset_dir / "metadata.json"
                if metadata_file.exists():
                    async with aiofiles.open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.loads(await f.read())

                    # 过滤用户
                    if user_id and metadata.get('created_by') != user_id:
                        continue

                    datasets.append(metadata)

        # 按创建时间排序
        datasets.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        # 分页
        total = len(datasets)
        datasets = datasets[offset:offset + limit]

        return {
            'datasets': datasets,
            'total': total,
            'offset': offset,
            'limit': limit
        }

    async def delete_dataset(self, dataset_id: str) -> bool:
        """
        删除数据集

        Args:
            dataset_id: 数据集 ID

        Returns:
            是否删除成功
        """
        dataset_dir = self.storage_path / dataset_id

        if not dataset_dir.exists():
            return False

        # 删除目录及所有内容
        import shutil
        shutil.rmtree(dataset_dir)

        logger.info(f"Dataset {dataset_id} deleted")
        return True

    async def generate_sample_dataset(self, dataset_type: str = 'basic') -> Dict[str, Any]:
        """
        生成示例数据集

        Args:
            dataset_type: 数据集类型 ('basic', 'with_reference', 'with_contexts')

        Returns:
            生成的数据集信息
        """
        samples = []

        if dataset_type == 'basic':
            samples = [
                {'question': 'What is RAGFlow?'},
                {'question': 'How does RAG work?'},
                {'question': 'What are the benefits of using RAG?'},
                {'question': 'How to install RAGFlow?'},
                {'question': 'What databases does RAGFlow support?'}
            ]
        elif dataset_type == 'with_reference':
            samples = [
                {
                    'question': 'What is RAGFlow?',
                    'expected_answer': 'RAGFlow is an open-source RAG engine for deep document understanding.'
                },
                {
                    'question': 'How does RAG work?',
                    'expected_answer': 'RAG combines retrieval and generation to answer questions based on documents.'
                },
                {
                    'question': 'What are the benefits of using RAG?',
                    'expected_answer': 'RAG provides accurate answers, reduces hallucinations, and leverages existing documents.'
                },
                {
                    'question': 'How to install RAGFlow?',
                    'expected_answer': 'RAGFlow can be installed using Docker or from source code with Python environment.'
                },
                {
                    'question': 'What databases does RAGFlow support?',
                    'expected_answer': 'RAGFlow supports Elasticsearch, Milvus, and other vector databases.'
                }
            ]
        elif dataset_type == 'with_contexts':
            samples = [
                {
                    'question': 'What is RAGFlow?',
                    'expected_answer': 'RAGFlow is an open-source RAG engine for deep document understanding.',
                    'contexts': [
                        'RAGFlow is an open-source RAG (Retrieval-Augmented Generation) engine.',
                        'It focuses on deep document understanding and intelligent question answering.'
                    ],
                    'reference_contexts': [
                        'RAGFlow is an open-source RAG engine based on deep document understanding.'
                    ]
                },
                {
                    'question': 'How does RAG work?',
                    'expected_answer': 'RAG retrieves relevant documents first, then generates answers based on the retrieved context.',
                    'contexts': [
                        'RAG combines information retrieval with language model generation.',
                        'First, relevant documents are retrieved from a knowledge base.',
                        'Then, the language model generates answers based on the retrieved context.'
                    ],
                    'reference_contexts': [
                        'RAG works by first retrieving relevant documents and then using them to generate accurate answers.'
                    ]
                },
                {
                    'question': 'What are the benefits of using RAG?',
                    'expected_answer': 'RAG provides more accurate and grounded answers by leveraging existing knowledge.',
                    'contexts': [
                        'RAG reduces hallucinations by grounding responses in actual documents.',
                        'It allows models to access up-to-date information without retraining.',
                        'RAG enables better control and transparency in answer generation.'
                    ],
                    'reference_contexts': [
                        'The main benefits of RAG are accuracy, reduced hallucinations, and leveraging existing documents.'
                    ]
                },
                {
                    'question': 'How to install RAGFlow?',
                    'expected_answer': 'RAGFlow can be installed using Docker or by setting up a Python environment from source.',
                    'contexts': [
                        'RAGFlow offers Docker-based deployment for quick setup.',
                        'For development, you can install from source with Python 3.10+.',
                        'Dependencies include Elasticsearch, MySQL, and Redis.'
                    ],
                    'reference_contexts': [
                        'Installation options include Docker deployment and source code setup with Python.'
                    ]
                },
                {
                    'question': 'What databases does RAGFlow support?',
                    'expected_answer': 'RAGFlow supports Elasticsearch for search and various vector databases like Milvus.',
                    'contexts': [
                        'RAGFlow uses Elasticsearch as the primary search engine.',
                        'It supports vector databases including Milvus for semantic search.',
                        'MySQL is used for metadata storage and Redis for caching.'
                    ],
                    'reference_contexts': [
                        'RAGFlow supports Elasticsearch, Milvus, MySQL, and Redis for different storage needs.'
                    ]
                }
            ]

        # 创建示例数据集
        dataset_name = f"Sample Dataset - {dataset_type}"
        description = f"Auto-generated sample dataset of type: {dataset_type}"

        # 转换为 JSON 字节
        content = json.dumps(samples, ensure_ascii=False).encode('utf-8')

        return await self.upload_dataset(
            file_content=content,
            file_name='sample.json',
            dataset_name=dataset_name,
            description=description,
            user_id='system'
        )