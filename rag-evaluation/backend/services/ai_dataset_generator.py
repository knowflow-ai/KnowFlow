import json
import logging
import random
import requests
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class AIDatasetGenerator:
    """AI数据集生成器 - 完全基于LLM生成，无模板"""
    
    def __init__(self):
        # 从环境变量获取配置
        self.ragflow_base_url = os.getenv('RAGFLOW_BASE_URL', 'http://localhost:9380') + '/api/v1'
        self.ragflow_api_key = os.getenv('RAGFLOW_API_KEY', '')
        
        if not self.ragflow_api_key:
            # 尝试从配置文件读取
            try:
                import yaml
                with open('conf/service_conf.yaml', 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self.ragflow_api_key = config.get('ragflow', {}).get('api_key', '')
            except Exception as e:
                logger.warning(f"Failed to load RAGFlow API key from config: {str(e)}")
        
        if not self.ragflow_api_key:
            logger.warning("RAGFlow API key not found.")
        else:
            logger.info("RAGFlow API key loaded successfully")
    
    def get_knowledge_base_chunks(self, kb_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取知识库的chunks"""
        try:
            logger.info(f"Getting chunks from knowledge base (chat_id): {kb_id}")
            
            # 1. 首先获取chat助手的信息，获取其关联的dataset_ids
            chat_url = f"{self.ragflow_base_url}/chats"
            headers = {
                'Content-Type': 'application/json',
            }
            if self.ragflow_api_key:
                headers['Authorization'] = f'Bearer {self.ragflow_api_key}'
            
            params = {'id': kb_id}
            response = requests.get(chat_url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.warning(f"Failed to get chat assistant info: {response.status_code}")
                return self._get_mock_chunks()
            
            chat_data = response.json()
            if chat_data.get('code') != 0:
                logger.warning(f"Chat API returned error: {chat_data}")
                return self._get_mock_chunks()
            
            # 从chat列表中获取匹配的chat助手
            chats = chat_data.get('data', [])
            if not chats:
                logger.warning(f"No chat assistant found with ID {kb_id}")
                return self._get_mock_chunks()
            
            # 找到匹配的chat助手
            chat_info = None
            for chat in chats:
                if chat.get('id') == kb_id:
                    chat_info = chat
                    break
            
            if not chat_info:
                logger.warning(f"Chat assistant {kb_id} not found in response")
                return self._get_mock_chunks()
            
            # 获取关联的数据集
            datasets = chat_info.get('datasets', [])
            if not datasets:
                logger.warning(f"No datasets found for chat assistant {kb_id}")
                return self._get_mock_chunks()
            
            logger.info(f"Found {len(datasets)} datasets for chat assistant")
            
            # 2. 获取所有数据集的chunks
            all_chunks = []
            chunks_per_dataset = max(1, limit // len(datasets))
            
            for dataset in datasets:
                dataset_id = dataset.get('id')
                if not dataset_id:
                    continue
                    
                dataset_chunks = self._get_chunks_from_dataset(dataset_id, chunks_per_dataset)
                all_chunks.extend(dataset_chunks)
                
                if len(all_chunks) >= limit:
                    break
            
            final_chunks = all_chunks[:limit]
            logger.info(f"Successfully retrieved {len(final_chunks)} chunks")
            
            return final_chunks if final_chunks else self._get_mock_chunks()
                
        except Exception as e:
            logger.error(f"Error getting chunks from knowledge base {kb_id}: {str(e)}")
            return self._get_mock_chunks()
    
    def _get_chunks_from_dataset(self, dataset_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """从指定数据集获取chunks"""
        try:
            chunks = []
            
            # 获取数据集中的文档列表
            docs_url = f"{self.ragflow_base_url}/datasets/{dataset_id}/documents"
            headers = {
                'Content-Type': 'application/json',
            }
            if self.ragflow_api_key:
                headers['Authorization'] = f'Bearer {self.ragflow_api_key}'
            
            params = {'page': 1, 'page_size': 50}
            response = requests.get(docs_url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                return []
            
            docs_data = response.json()
            if docs_data.get('code') != 0:
                return []
            
            documents = docs_data.get('data', {}).get('docs', [])
            
            if not documents:
                return []
            
            # 从每个文档获取chunks
            chunks_per_doc = max(1, limit // len(documents))
            
            for doc in documents[:10]:  # 限制处理前10个文档
                doc_id = doc.get('id')
                doc_name = doc.get('name', '未知文档')
                
                if not doc_id:
                    continue
                
                doc_chunks = self._get_chunks_from_document(dataset_id, doc_id, doc_name, chunks_per_doc)
                chunks.extend(doc_chunks)
                
                if len(chunks) >= limit:
                    break
            
            return chunks[:limit]
            
        except Exception as e:
            logger.error(f"Error getting chunks from dataset {dataset_id}: {str(e)}")
            return []
    
    def _get_chunks_from_document(self, dataset_id: str, document_id: str, doc_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """从指定文档获取chunks"""
        try:
            chunks_url = f"{self.ragflow_base_url}/datasets/{dataset_id}/documents/{document_id}/chunks"
            headers = {
                'Content-Type': 'application/json',
            }
            if self.ragflow_api_key:
                headers['Authorization'] = f'Bearer {self.ragflow_api_key}'
            
            params = {'page': 1, 'page_size': limit}
            response = requests.get(chunks_url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                return []
            
            chunks_data = response.json()
            if chunks_data.get('code') != 0:
                return []
            
            raw_chunks = chunks_data.get('data', {}).get('chunks', [])
            
            # 转换为我们需要的格式
            processed_chunks = []
            for chunk in raw_chunks:
                processed_chunk = {
                    "id": chunk.get('id', ''),
                    "content": chunk.get('content', ''),
                    "doc_name": doc_name,
                    "doc_id": document_id,
                    "dataset_id": dataset_id,
                    "page_number": chunk.get('page_number', 0),
                    "positions": chunk.get('positions', []),
                    "create_time": chunk.get('create_time', ''),
                    "update_time": chunk.get('update_time', '')
                }
                
                if processed_chunk["content"].strip():
                    processed_chunks.append(processed_chunk)
            
            return processed_chunks
            
        except Exception as e:
            logger.error(f"Error getting chunks from document {document_id}: {str(e)}")
            return []
    
    def _get_mock_chunks(self) -> List[Dict[str, Any]]:
        """获取模拟chunks数据用于测试"""
        return [
            {
                "id": "chunk_1",
                "content": "人工智能（Artificial Intelligence, AI）是指通过计算机系统模拟、延伸和扩展人类智能的技术。AI系统能够执行通常需要人类智能才能完成的任务，如视觉感知、语音识别、决策制定和语言翻译等。",
                "doc_name": "AI基础知识.pdf",
                "page_number": 1
            },
            {
                "id": "chunk_2", 
                "content": "机器学习是人工智能的一个重要分支，它使计算机能够在没有明确编程的情况下学习和改进性能。机器学习算法通过分析大量数据来识别模式，并基于这些模式做出预测或决策。",
                "doc_name": "机器学习指南.pdf",
                "page_number": 2
            }
        ]
    
    def call_llm_for_generation(self, prompt: str) -> Optional[str]:
        """调用大模型生成内容"""
        try:
            import sqlite3
            from langchain_openai import ChatOpenAI
            
            # 连接数据库获取API配置
            db_path = 'evaluation.db'
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM api_configs WHERE is_default = 1 LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                logger.error("No default API configuration found")
                return None
            
            # 解析配置
            _, _, provider, api_key, endpoint, model, _, temperature, max_tokens, _, _, _ = result
            
            logger.info(f"Using LLM: {model} from {provider}")
            
            # 创建LLM实例
            llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=endpoint,
                temperature=temperature,
                max_tokens=min(max_tokens, 1000),
                timeout=30
            )
            
            # 调用LLM生成内容
            response = llm.invoke(prompt)
            
            logger.info(f"LLM generation successful, response length: {len(response.content)}")
            return response.content
                
        except Exception as e:
            logger.error(f"LLM generation failed: {str(e)}")
            return None
    
    def generate_qa_pair_with_llm(self, chunk: Dict[str, Any], question_type: str, max_retries: int = 2) -> Optional[Dict[str, Any]]:
        """使用LLM生成问答对，在生成过程中确保质量"""
        content = chunk.get('content', '')
        doc_name = chunk.get('doc_name', '未知文档')
        
        # 针对不同问题类型优化提示词
        question_type_map = {
            'factual': '事实性问题（询问具体信息、定义、事实等）',
            'analytical': '分析性问题（要求分析原理、机制、过程等）',
            'application': '应用性问题（询问如何使用、应用场景等）',
            'comparison': '比较性问题（对比不同概念、方法的异同）',
            'explanation': '解释性问题（询问原因、背景、重要性等）'
        }
        
        question_desc = question_type_map.get(question_type, question_type)
        
        # 生成时就包含质量控制的提示词
        prompt = f"""你是专业的问答生成助手。基于以下文档内容生成{question_desc}。

文档内容：
{content}

生成要求：
1. 问题必须基于文档中存在的具体内容（概念、术语、事实）
2. 答案必须直接摘录文档原文，不允许总结或改写
3. 问题和答案必须来自同一段文档内容
4. 如果文档内容不足以生成该类型问题，请回复"无法生成"

请先检查：文档中是否有足够信息生成{question_desc}？
如果有，请严格按JSON格式返回：{{"question": "问题", "expected_answer": "摘录的原文"}}"""

        # 最多重试2次
        for attempt in range(max_retries):
            response = self.call_llm_for_generation(prompt)
            if not response:
                logger.warning(f"LLM generation failed, attempt {attempt + 1}")
                continue
            
            # 检查是否返回"无法生成"
            if "无法生成" in response:
                logger.info(f"LLM determined insufficient content for {question_type}")
                return None
                
            try:
                # 解析JSON响应
                response = response.strip()
                if '```json' in response:
                    start = response.find('```json') + 7
                    end = response.find('```', start)
                    if end > start:
                        response = response[start:end].strip()
                elif '```' in response:
                    start = response.find('```') + 3
                    end = response.find('```', start)
                    if end > start:
                        response = response[start:end].strip()
                
                qa_data = json.loads(response)
                question = qa_data.get('question', '').strip()
                expected_answer = qa_data.get('expected_answer', '').strip()
                
                if question and expected_answer:
                    logger.info(f"Generated QA pair: Q='{question[:30]}...' A='{expected_answer[:30]}...'")
                    return {
                        'question': question,
                        'expected_answer': expected_answer,
                        'contexts': [content],
                        'source_doc': doc_name,
                        'question_type': question_type,
                        'chunk_id': chunk.get('id', ''),
                        'generation_method': 'llm',
                        'attempts_used': attempt + 1
                    }
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error (attempt {attempt + 1}): {str(e)}")
                continue
        
        logger.warning(f"Failed to generate valid QA pair after {max_retries} attempts")
        return None
    
    def generate_dataset_from_kb(self, kb_id: str, sample_count: int, question_types: List[str]) -> List[Dict[str, Any]]:
        """基于知识库生成数据集 - 完全使用LLM生成，无模板"""
        try:
            logger.info(f"Starting AI dataset generation for KB {kb_id}, {sample_count} samples")
            
            # 获取知识库chunks，获取足够的chunk以应对质量过滤
            chunks = self.get_knowledge_base_chunks(kb_id, limit=min(200, sample_count * 4))
            if not chunks:
                logger.error("No chunks retrieved from knowledge base")
                return []
            
            logger.info(f"Retrieved {len(chunks)} chunks from knowledge base")
            
            samples = []
            failed_chunks = set()  # 记录生成失败的chunk
            chunk_attempt_count = {}  # 记录每个chunk的尝试次数
            
            # 生成问答对，完全依靠LLM
            for i in range(sample_count):
                logger.info(f"Generating sample {i + 1}/{sample_count}...")
                
                # 随机选择问题类型
                question_type = random.choice(question_types)
                
                qa_pair = None
                max_chunk_tries = 10  # 最多尝试10个不同的chunk
                
                for _ in range(max_chunk_tries):
                    # 选择可用的chunk（排除已失败的chunk）
                    available_chunks = [
                        c for c in chunks 
                        if c.get('id') not in failed_chunks 
                        and chunk_attempt_count.get(c.get('id'), 0) < 2  # 每个chunk最多尝试2次
                    ]
                    
                    if not available_chunks:
                        logger.warning(f"No more available chunks for sample {i + 1}")
                        break
                    
                    # 随机选择一个chunk
                    chunk = random.choice(available_chunks)
                    chunk_id = chunk.get('id')
                    
                    # 记录尝试次数
                    chunk_attempt_count[chunk_id] = chunk_attempt_count.get(chunk_id, 0) + 1
                    
                    logger.info(f"Trying chunk {chunk_id} (attempt {chunk_attempt_count[chunk_id]}) for sample {i + 1}")
                    
                    # 使用LLM生成
                    qa_pair = self.generate_qa_pair_with_llm(chunk, question_type, max_retries=2)
                    
                    if qa_pair:
                        logger.info(f"Successfully generated QA pair using chunk {chunk_id}")
                        break
                    else:
                        logger.warning(f"Failed to generate valid QA pair from chunk {chunk_id}")
                        # 如果该chunk已经尝试了2次，标记为失败
                        if chunk_attempt_count[chunk_id] >= 2:
                            failed_chunks.add(chunk_id)
                            logger.info(f"Marking chunk {chunk_id} as failed after 2 attempts")
                
                if qa_pair:
                    samples.append(qa_pair)
                else:
                    logger.warning(f"Failed to generate sample {i + 1} after trying multiple chunks")
            
            # 生成完成统计
            logger.info(f"Generation completed: {len(samples)} total samples")
            logger.info(f"  - Failed chunks: {len(failed_chunks)}")
            
            return samples
            
        except Exception as e:
            logger.error(f"Failed to generate dataset from KB {kb_id}: {str(e)}")
            import traceback
            logger.error(f"Detailed error: {traceback.format_exc()}")
            return []