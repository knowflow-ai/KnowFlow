"""
评测服务核心模块
负责执行知识库的评测任务，集成 RAGAS 评估引擎
"""

import asyncio
import logging
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
import json
import pandas as pd
import aiohttp

# 优先导入 langchain 核心类，确保 Pydantic 模型正确初始化
try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError:
    logging.warning("LangChain packages not fully installed")
    ChatOpenAI = None
    OpenAIEmbeddings = None

# 然后导入 ragas，此时 Pydantic 模型已经完整
try:
    from ragas import evaluate
    from ragas.metrics import (
        Faithfulness,
        AnswerCorrectness,
        ContextPrecision,
        ContextRecall,
        AnswerRelevancy
    )
    from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
    from ragas.llms.base import LangchainLLMWrapper
    from ragas.embeddings.base import LangchainEmbeddingsWrapper
    from ragas.run_config import RunConfig
except ImportError:
    logging.warning("RAGAS not installed. Please install with: pip install ragas")
    # 提供占位符以避免导入错误
    evaluate = None
    Faithfulness = None
    AnswerCorrectness = None
    ContextPrecision = None
    ContextRecall = None
    AnswerRelevancy = None
    SingleTurnSample = None
    EvaluationDataset = None
    LangchainLLMWrapper = None
    LangchainEmbeddingsWrapper = None
    RunConfig = None

logger = logging.getLogger(__name__)


class EvaluationService:
    """
    RAG 评测服务
    提供知识库的多维度质量评估
    """

    def __init__(self, llm_model: str = "gpt-4", ragflow_url: str = "http://ragflow:9380", api_config: Dict = None):
        """
        初始化评测服务

        Args:
            llm_model: 用于评测的 LLM 模型
            ragflow_url: RAGFlow 服务地址
            api_config: API配置（包含 provider, apiKey, endpoint, embeddingModel 等）
        """
        self.ragflow_url = ragflow_url
        self.llm_model = llm_model
        self.api_config = api_config or {}
        self.llm = None  # 延迟初始化，避免启动时的网络问题
        self.embeddings = None  # 延迟初始化 embeddings

        # 初始化评测指标
        self.metrics_map = self._initialize_metrics()

        logger.info(f"EvaluationService initialized with LLM: {llm_model}")
        logger.info(f"API config: provider={self.api_config.get('provider')}, endpoint={self.api_config.get('endpoint')}, embeddingModel={self.api_config.get('embeddingModel')}")

    def _get_llm(self):
        """
        延迟获取 LLM 实例
        从系统配置读取 API Key 和 Endpoint，支持多种 LLM 提供商
        """
        if self.llm is None and ChatOpenAI and LangchainLLMWrapper:
            # 从配置读取参数
            api_key = self.api_config.get('apiKey', os.getenv('OPENAI_API_KEY', ''))
            base_url = self.api_config.get('endpoint', None)
            temperature = self.api_config.get('temperature', 0.1)
            provider = self.api_config.get('provider', 'openai')

            # 根据 provider 设置默认 endpoint
            provider_endpoints = {
                'siliconflow': 'https://api.siliconflow.cn/v1',
                'deepseek': 'https://api.deepseek.com/v1',
                'zhipu': 'https://open.bigmodel.cn/api/paas/v4',
                'openai': None  # OpenAI 使用默认 endpoint
            }

            # 如果没有提供 endpoint，使用默认值
            if not base_url and provider in provider_endpoints:
                base_url = provider_endpoints[provider]

            # 创建 ChatOpenAI 实例
            kwargs = {
                'model': self.llm_model,
                'temperature': temperature,
                'api_key': api_key
            }

            # 如果配置了自定义 endpoint（如硅基流动），添加 base_url
            if base_url:
                kwargs['base_url'] = base_url

            openai_model = ChatOpenAI(**kwargs)

            # 包装成 Ragas 需要的格式
            self.llm = LangchainLLMWrapper(openai_model)
            logger.info(f"LLM instance created: {self.llm_model} (provider: {provider}, endpoint: {base_url})")

        return self.llm

    def _get_embeddings(self):
        """
        延迟获取 Embeddings 实例
        使用与 LLM 相同的配置源 (self.api_config)
        """
        if self.embeddings is None and OpenAIEmbeddings and LangchainEmbeddingsWrapper:
            # 使用驼峰命名统一获取配置
            api_key = self.api_config.get('apiKey', os.getenv('OPENAI_API_KEY', ''))
            base_url = self.api_config.get('endpoint', None)
            provider = self.api_config.get('provider', 'openai')
            embedding_model = self.api_config.get('embeddingModel', '')

            # 处理 embeddingModel 可能是数组的情况（前端使用 tags mode）
            if isinstance(embedding_model, list):
                embedding_model = embedding_model[0] if embedding_model else ''

            if not embedding_model:
                logger.warning("No embedding model configured in system settings. Some metrics (like AnswerCorrectness) may fail.")
                return None

            # 根据 provider 设置默认 endpoint
            provider_endpoints = {
                'siliconflow': 'https://api.siliconflow.cn/v1',
                'deepseek': 'https://api.deepseek.com/v1',
                'zhipu': 'https://open.bigmodel.cn/api/paas/v4',
                'openai': None  # OpenAI 使用默认 endpoint
            }

            # 如果没有提供 endpoint，使用默认值
            if not base_url and provider in provider_endpoints:
                base_url = provider_endpoints[provider]

            # 创建 OpenAIEmbeddings 实例（兼容 OpenAI API 的服务）
            kwargs = {
                'model': embedding_model,
                'api_key': api_key
            }

            if base_url:
                kwargs['base_url'] = base_url

            openai_embeddings = OpenAIEmbeddings(**kwargs)

            # 包装成 Ragas 需要的格式
            self.embeddings = LangchainEmbeddingsWrapper(openai_embeddings)
            logger.info(f"Embeddings instance created: {embedding_model} (provider: {provider}, endpoint: {base_url})")

        return self.embeddings

    def _initialize_metrics(self) -> Dict:
        """
        初始化可用的评测指标
        注意：某些指标（如 AnswerCorrectness, AnswerRelevancy）需要 embeddings 模型
        这些指标会在执行时动态获取 embeddings 实例
        """
        if not Faithfulness:
            return {}

        return {
            'faithfulness': Faithfulness(),
            'answer_correctness': AnswerCorrectness(),  # 需要 embeddings
            'context_precision': ContextPrecision(),
            'context_recall': ContextRecall(),
            'answer_relevancy': AnswerRelevancy()  # 需要 embeddings
        }

    async def evaluate_knowledge_base(
        self,
        chat_id: str,
        dataset_id: str,
        selected_metrics: List[str],
        dataset_samples: List[Dict],
        batch_size: int = 10,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        评测对话助手

        Args:
            chat_id: 对话助手 ID (Chat Assistant ID)
            dataset_id: 数据集 ID
            selected_metrics: 选择的评测指标
            dataset_samples: 数据集样本
            batch_size: 批处理大小
            progress_callback: 进度回调函数，接收绝对进度值 (0-99)

        Returns:
            评测结果
        """
        if not evaluate:
            raise ImportError("RAGAS not installed. Please install with: pip install ragas")

        logger.info(f"Starting evaluation for Chat: {chat_id}, Dataset: {dataset_id}")
        logger.info(f"Selected metrics: {selected_metrics}")
        logger.info(f"Dataset samples: {len(dataset_samples)}, Batch size: {batch_size}")

        try:
            # 1. 准备评测样本 (0-50%)
            logger.info("Step 1: Preparing evaluation samples...")

            # 包装进度回调，将样本进度映射到 0-50%
            def sample_progress_callback(processed: int, total: int):
                if progress_callback:
                    progress = int((processed / total) * 50)  # 0-50%
                    progress_callback(progress)

            # 传递原始数据集样本信息
            evaluation_samples, rag_responses = await self._prepare_samples_with_responses(chat_id, dataset_samples, sample_progress_callback)

            # 2. 创建 RAGAS 数据集 (50%)
            logger.info("Step 2: Creating RAGAS dataset...")
            if progress_callback:
                progress_callback(50)
            eval_dataset = EvaluationDataset(samples=evaluation_samples)

            # 3. 选择评测指标 (55%)
            logger.info("Step 3: Selecting metrics...")
            if progress_callback:
                progress_callback(55)
            metrics = []
            for metric_name in selected_metrics:
                if metric_name in self.metrics_map:
                    metrics.append(self.metrics_map[metric_name])
                    logger.info(f"  - Added metric: {metric_name}")
                else:
                    logger.warning(f"  - Unknown metric: {metric_name}")

            # 4. 配置运行参数 (60%)
            if progress_callback:
                progress_callback(60)
            run_config = RunConfig(
                max_workers=2,  # 减少并发数从 4 到 2
                max_retries=2,  # 减少重试次数从 3 到 2
                timeout=300     # 增加超时时间到 300 秒（5分钟）
            )

            # 5. 执行评测 (60-95%)
            logger.info(f"Step 4: Running evaluation with {len(metrics)} metrics...")
            logger.info(f"  - Max workers: {run_config.max_workers}")
            logger.info(f"  - Timeout: {run_config.timeout}s")
            logger.info(f"  - Max retries: {run_config.max_retries}")

            # 获取 embeddings（某些指标需要）
            embeddings = self._get_embeddings()
            if embeddings:
                logger.info(f"  - Using embeddings model")
            else:
                logger.info(f"  - No embeddings model configured")

            # evaluate() 是同步函数，在事件循环中运行
            loop = asyncio.get_event_loop()

            logger.info("Starting RAGAS evaluation...")
            if progress_callback:
                progress_callback(65)  # 评测开始

            results = await loop.run_in_executor(
                None,
                lambda: evaluate(
                    dataset=eval_dataset,
                    metrics=metrics,
                    llm=self._get_llm(),
                    embeddings=embeddings,
                    run_config=run_config
                )
            )
            logger.info("RAGAS evaluation completed")
            if progress_callback:
                progress_callback(95)  # 评测完成

            # 6. 处理结果 (95-99%)
            logger.info("Step 5: Processing results...")
            evaluation_result = self._process_results(results, chat_id, dataset_id, rag_responses)
            if progress_callback:
                progress_callback(99)  # 结果处理完成，但不设置为 100%

            # 记录成功率
            success_rate = evaluation_result['evaluation_metadata'].get('success_rate', '0 / 0')
            logger.info(f"Evaluation completed for Chat: {chat_id}, Success rate: {success_rate}")

            return evaluation_result

        except Exception as e:
            logger.error(f"Evaluation failed: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def _prepare_samples(
        self,
        chat_id: str,
        dataset_samples: List[Dict],
        progress_callback=None
    ) -> List[SingleTurnSample]:
        """
        准备评测样本，查询 RAGFlow 获取响应

        Args:
            chat_id: 对话助手 ID
            dataset_samples: 原始数据集样本
            progress_callback: 进度回调函数，接收 (processed_count, total_count)

        Returns:
            RAGAS 格式的评测样本
        """
        samples = []
        total_samples = len(dataset_samples)

        for idx, item in enumerate(dataset_samples, 1):
            logger.info(f"Preparing sample {idx}/{total_samples}: {item.get('question', '')[:50]}...")

            # 查询 RAGFlow
            try:
                rag_response = await self._query_ragflow(chat_id, item['question'])
                logger.info(f"Sample {idx}/{total_samples}: Got response with {len(rag_response.get('contexts', []))} contexts")
            except Exception as e:
                logger.error(f"Sample {idx}/{total_samples}: Failed to query RAGFlow: {str(e)}")
                rag_response = {'answer': '', 'contexts': []}

            # 创建 RAGAS 样本
            sample = SingleTurnSample(
                user_input=item['question'],
                retrieved_contexts=rag_response.get('contexts', []),
                response=rag_response.get('answer', ''),
                reference=item.get('expected_answer'),
                reference_contexts=item.get('reference_contexts', [])
            )
            samples.append(sample)

            # 调用进度回调 (传递样本数而非进度百分比)
            if progress_callback:
                progress_callback(idx, total_samples)

        logger.info(f"Prepared {len(samples)} samples for evaluation")
        return samples

    async def _prepare_samples_with_responses(
        self,
        chat_id: str,
        dataset_samples: List[Dict],
        progress_callback=None
    ) -> tuple[List[SingleTurnSample], List[Dict]]:
        """
        准备评测样本，查询 RAGFlow 获取响应，并保留原始数据

        Args:
            chat_id: 对话助手 ID
            dataset_samples: 原始数据集样本
            progress_callback: 进度回调函数，接收 (processed_count, total_count)

        Returns:
            tuple: (RAGAS格式的评测样本, RAGFlow响应列表)
        """
        samples = []
        rag_responses = []
        total_samples = len(dataset_samples)

        for idx, item in enumerate(dataset_samples, 1):
            logger.info(f"Preparing sample {idx}/{total_samples}: {item.get('question', '')[:50]}...")

            # 查询 RAGFlow
            try:
                rag_response = await self._query_ragflow(chat_id, item['question'])
                logger.info(f"Sample {idx}/{total_samples}: Got response with {len(rag_response.get('contexts', []))} contexts")
            except Exception as e:
                logger.error(f"Sample {idx}/{total_samples}: Failed to query RAGFlow: {str(e)}")
                rag_response = {'answer': '', 'contexts': []}

            # 保存 RAGFlow 响应
            rag_response['original_question'] = item['question']
            rag_response['expected_answer'] = item.get('expected_answer', '')
            rag_responses.append(rag_response)

            # 创建 RAGAS 样本
            sample = SingleTurnSample(
                user_input=item['question'],
                retrieved_contexts=rag_response.get('contexts', []),
                response=rag_response.get('answer', ''),
                reference=item.get('expected_answer'),
                reference_contexts=item.get('reference_contexts', [])
            )
            samples.append(sample)

            # 调用进度回调 (传递样本数而非进度百分比)
            if progress_callback:
                progress_callback(idx, total_samples)

        logger.info(f"Prepared {len(samples)} samples for evaluation")
        return samples, rag_responses

    async def _query_ragflow(self, chat_id: str, question: str) -> Dict:
        """
        查询 RAGFlow 对话助手

        Args:
            chat_id: 对话助手 ID（Chat ID）
            question: 查询问题

        Returns:
            RAGFlow 响应，包含 answer 和 contexts
        """
        import aiohttp

        # 创建超时配置
        timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=50)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            # RAGFlow 对话接口
            url = f"{self.ragflow_url}/api/v1/chats/{chat_id}/completions"

            # 从环境变量或配置读取 API Key
            api_key = os.getenv('RAGFLOW_API_KEY', 'YOUR_API_TOKEN')

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }

            # 检查是否已有有效的 session_id
            session_id = getattr(self, '_cached_session_id', None)

            if not session_id:
                # 为当前 chat_id 创建一个新的会话
                session_url = f"{self.ragflow_url}/api/v1/chats/{chat_id}/sessions"

                try:
                    async with session.post(session_url, json={}, headers=headers) as session_response:
                        if session_response.status == 200:
                            session_data = await session_response.json()
                            if session_data.get('code') == 0 and 'data' in session_data:
                                session_id = session_data['data']['id']
                                self._cached_session_id = session_id  # 缓存 session_id 以供后续使用
                                logger.info(f"✅ Created new session: {session_id} for chat: {chat_id}")
                            else:
                                logger.warning(f"Failed to create session: {session_data}")
                        else:
                            logger.warning(f"Failed to create session, status: {session_response.status}")
                except Exception as e:
                    logger.error(f"Error creating session: {e}")

            payload = {
                'question': question,
                'stream': False,  # 使用非流式响应，便于解析
                'session_id': session_id  # 使用有效的 session_id 来维持对话上下文
            }

            try:
                logger.info(f"=== RAGFlow API Request ===")
                logger.info(f"URL: {url}")
                logger.info(f"Chat ID: {chat_id}")
                logger.info(f"Question: {question}")
                logger.info(f"Session ID: {session_id}")
                logger.info(f"Payload: {payload}")
                logger.info(f"Headers: {headers}")
                logger.info(f"API Key (first 10 chars): {api_key[:10]}..." if api_key != 'YOUR_API_TOKEN' else "API Key: NOT SET")

                async with session.post(url, json=payload, headers=headers) as response:
                    logger.info(f"Response Status: {response.status}")
                    logger.info(f"Response Headers: {dict(response.headers)}")

                    if response.status == 200:
                        result = await response.json()

                        logger.info(f"=== RAGFlow API Response ===")
                        logger.info(f"Full Response: {json.dumps(result, indent=2, ensure_ascii=False)}")

                        # 解析 RAGFlow 响应
                        if result.get('code') == 0 and 'data' in result:
                            data = result['data']

                            logger.info(f"=== RAGFlow Data Analysis ===")
                            logger.info(f"Answer: {data.get('answer', 'No answer')}")
                            logger.info(f"Answer Length: {len(data.get('answer', ''))}")
                            logger.info(f"Session ID: {data.get('session_id', 'No session ID')}")
                            logger.info(f"Reference Type: {type(data.get('reference', {}))}")
                            logger.info(f"Reference Content: {data.get('reference', 'No reference')}")

                            # 提取检索到的上下文
                            contexts = []
                            reference = data.get('reference', {})

                            if reference and 'chunks' in reference and reference['chunks']:
                                # 有检索到的上下文
                                contexts = [
                                    chunk.get('content', '')
                                    for chunk in reference['chunks']
                                    if chunk.get('content')
                                ]
                                logger.info(f"✓ Successfully extracted {len(contexts)} contexts from RAGFlow")
                                for i, ctx in enumerate(contexts[:3]):  # 只打印前3个上下文
                                    logger.info(f"Context {i+1}: {ctx[:100]}..." if len(ctx) > 100 else f"Context {i+1}: {ctx}")
                                if len(contexts) > 3:
                                    logger.info(f"... and {len(contexts) - 3} more contexts")
                            else:
                                # 没有检索到上下文
                                logger.warning("✗ RAGFlow returned no contexts")
                                logger.warning(f"Reference field: {reference}")
                                logger.warning("Possible causes:")
                                logger.warning("  1. Chat assistant has no associated knowledge base")
                                logger.warning("  2. Knowledge base has no indexed documents")
                                logger.warning("  3. Query matched no relevant documents")

                            logger.info(f"=== Final Extracted Data ===")
                            logger.info(f"Answer: {data.get('answer', '')}")
                            logger.info(f"Contexts Count: {len(contexts)}")

                            return {
                                'answer': data.get('answer', ''),
                                'contexts': contexts,
                                'session_id': data.get('session_id')
                            }
                        else:
                            logger.error(f"✗ RAGFlow returned error")
                            logger.error(f"Error Code: {result.get('code')}")
                            logger.error(f"Error Message: {result.get('message')}")
                            logger.error(f"Full Error Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
                            return {'answer': '', 'contexts': []}
                    else:
                        logger.error(f"✗ RAGFlow query failed with HTTP {response.status}")
                        response_text = await response.text()
                        logger.error(f"Response Body: {response_text}")
                        return {'answer': '', 'contexts': []}

            except asyncio.TimeoutError:
                logger.error(f"RAGFlow query timeout after 60 seconds for question: {question[:50]}...")
                return {'answer': '', 'contexts': []}
            except aiohttp.ClientError as e:
                logger.error(f"Network error querying RAGFlow: {str(e)}")
                return {'answer': '', 'contexts': []}
            except Exception as e:
                logger.error(f"Failed to query RAGFlow: {str(e)}")
                return {'answer': '', 'contexts': []}

    def _process_results(
        self,
        results: Any,
        chat_id: str,
        dataset_id: str,
        rag_responses: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        处理评测结果

        Args:
            results: RAGAS 评测结果
            chat_id: 对话助手 ID
            dataset_id: 数据集 ID
            rag_responses: RAGFlow 响应列表（包含原始问题、答案等）

        Returns:
            格式化的评测结果
        """
        import pandas as pd
        import numpy as np

        # 从 EvaluationResult 获取分数列表
        scores_list = results.scores

        # 转换为 DataFrame 进行统计计算
        if scores_list:
            scores_df = pd.DataFrame(scores_list)
        else:
            scores_df = pd.DataFrame()

        # 计算总体指标
        overall_scores = {}
        for metric in scores_df.columns:
            if metric != 'user_input' and not scores_df[metric].isna().all():
                # 过滤掉 NaN 值进行统计
                valid_scores = scores_df[metric].dropna()
                if len(valid_scores) > 0:
                    mean_value = float(valid_scores.mean())
                    std_value = float(valid_scores.std()) if len(valid_scores) > 1 else 0.0

                    # 处理可能的 NaN 值
                    if np.isnan(std_value):
                        std_value = 0.0

                    overall_scores[metric] = {
                        'mean': mean_value,
                        'std': std_value,
                        'min': float(valid_scores.min()),
                        'max': float(valid_scores.max()),
                        'valid_count': len(valid_scores),
                        'total_count': len(scores_df[metric])
                    }

        # 处理详细分数中的 NaN 值，并合并 RAGFlow 响应数据
        processed_scores = []
        if rag_responses and scores_list:
            for idx, (score_dict, rag_response) in enumerate(zip(scores_list, rag_responses)):
                processed_dict = {}
                # 添加基础字段
                processed_dict['user_input'] = rag_response.get('original_question', '')
                processed_dict['actual_answer'] = rag_response.get('answer', '')
                processed_dict['expected_answer'] = rag_response.get('expected_answer', '')
                processed_dict['contexts'] = rag_response.get('contexts', [])

                # 添加评测分数
                for key, value in score_dict.items():
                    if key != 'user_input':
                        if pd.isna(value) or (isinstance(value, float) and np.isnan(value)):
                            processed_dict[key] = None  # 将 NaN 转换为 None（JSON 兼容）
                        else:
                            processed_dict[key] = value
                processed_scores.append(processed_dict)

        # 计算成功的样本数
        success_count = len([s for s in processed_scores if any(v is not None for k, v in s.items()
                          if k not in ['user_input', 'actual_answer', 'expected_answer', 'contexts'])]) if processed_scores else 0

        # 构建返回结果
        evaluation_result = {
            'chat_id': chat_id,
            'dataset_id': dataset_id,
            'timestamp': datetime.now().isoformat(),
            'overall_scores': overall_scores,
            'detailed_scores': processed_scores,  # 包含完整信息的分数
            'evaluation_metadata': {
                'llm_model': self.llm_model,
                'num_samples': len(scores_list),
                'metrics_used': list(overall_scores.keys()),
                'success_rate': f"{success_count} / {len(scores_list)}" if scores_list else "0 / 0",
                'success_count': success_count,
                'total_count': len(scores_list)
            }
        }

        return evaluation_result

    async def quick_evaluate(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        metric_name: str = 'faithfulness'
    ) -> float:
        """
        快速评测单个问答对

        Args:
            question: 问题
            answer: 答案
            contexts: 上下文
            metric_name: 评测指标名称

        Returns:
            评分
        """
        if metric_name not in self.metrics_map:
            raise ValueError(f"Unknown metric: {metric_name}")

        metric = self.metrics_map[metric_name]

        # 创建单个样本
        sample = SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts
        )

        # 执行评测
        score = await metric.single_turn_ascore(sample, llm=self._get_llm())

        return score

    def get_available_metrics(self) -> List[Dict[str, str]]:
        """
        获取可用的评测指标列表

        Returns:
            指标列表
        """
        metrics_info = [
            {
                'name': 'faithfulness',
                'display_name': '忠实度',
                'description': '评估回答是否基于检索到的上下文',
                'type': 'llm_based'
            },
            {
                'name': 'answer_correctness',
                'display_name': '答案正确性',
                'description': '评估回答与参考答案的匹配程度',
                'type': 'llm_based'
            },
            {
                'name': 'context_precision',
                'display_name': '上下文精准度',
                'description': '评估检索到的上下文的相关性',
                'type': 'llm_based'
            },
            {
                'name': 'context_recall',
                'display_name': '上下文召回率',
                'description': '评估是否检索到所有相关信息',
                'type': 'llm_based'
            },
            {
                'name': 'answer_relevancy',
                'display_name': '答案相关性',
                'description': '评估回答与问题的相关程度',
                'type': 'llm_based'
            }
        ]

        # 只返回已安装的指标
        available_metrics = [m for m in metrics_info if m['name'] in self.metrics_map]
        return available_metrics


# 创建全局评估服务实例 - 使用统一配置服务
from config import get_config_service

config_service = get_config_service()
api_config = config_service.get_api_config()

evaluation_service = EvaluationService(
    llm_model=config_service.get_llm_model(),
    ragflow_url=config_service.get_ragflow_url(),
    api_config=api_config
)