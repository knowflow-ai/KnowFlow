#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""
MinerU Parser Base Class - MinerU 解析器抽象基类

提供标准的文档解析流程，子类只需实现差异化逻辑
"""

import logging
import os
import re
import copy
import tempfile
from abc import ABC, abstractmethod

from deepdoc.parser import MinerUParser
from rag.nlp import rag_tokenizer, tokenize, add_positions
from rag.app.parser_utils import (
    ensure_pdf,
    extract_text_and_coordinates,
    call_chunking_service
)


class MinerUParserBase(ABC):
    """
    MinerU 解析器抽象基类

    标准流程：
    1. 文件转换（ensure_pdf）
    2. 准备基础文档
    3. MinerU 解析
    4. 提取文本和坐标
    5. 调用分块服务
    6. 转换为 RAGFlow 格式
    7. 清理临时文件

    子类需要实现：
    - get_default_config(): 返回默认配置
    - build_chunking_config(parser_config): 构建分块配置
    - process_chunks_result(result): 处理分块结果（可选）
    """

    def __init__(self, strategy_name):
        """
        Args:
            strategy_name: 策略名称，用于日志和错误消息
        """
        self.strategy_name = strategy_name

    @abstractmethod
    def get_default_config(self):
        """
        返回默认的 parser_config

        Returns:
            dict: 默认配置
        """
        pass

    @abstractmethod
    def build_chunking_config(self, parser_config):
        """
        根据 parser_config 构建 chunking_config

        Args:
            parser_config: 解析器配置

        Returns:
            dict: 分块配置
        """
        pass

    def process_chunks_result(self, result):
        """
        处理分块服务返回的结果

        默认实现：直接返回结果
        子类可以重写此方法以实现特殊逻辑（如 parent_child）

        Args:
            result: 分块服务返回的结果

        Returns:
            list: 分块列表
        """
        return result if isinstance(result, list) else result.get('chunks', [])

    def chunk(self, filename, binary=None, from_page=0, to_page=100000,
              lang="Chinese", callback=None, **kwargs):
        """
        标准分块流程

        Args:
            filename: 文件路径或文件名
            binary: 二进制文件内容
            from_page: 起始页码
            to_page: 结束页码
            lang: 语言（Chinese/English）
            callback: 进度回调函数
            **kwargs: 额外参数，包括 parser_config、doc_id、kb_id、tenant_id 等

        Returns:
            List[dict]: 分块结果列表
        """
        temp_pdf_to_cleanup = None

        try:
            # 1. 确保输入是 PDF（如果不是则转换）
            pdf_path, temp_pdf_to_cleanup, pdf_binary = ensure_pdf(filename, binary)

            # 2. 准备基础文档（使用原始文件名）
            doc = self._prepare_base_doc(filename)

            # 3. 获取配置
            parser_config = kwargs.get("parser_config", self.get_default_config())

            callback(0.1, "Start to parse.")
            logging.info(f"Using MinerU parser for {self.strategy_name} chunking")
            callback(0.2, "Parsing with MinerU...")

            # 4. MinerU 解析
            kb_id = kwargs.get('kb_id', '') or kwargs.get('knowledgebase_id', '')
            sections, tables = self._parse_with_mineru(
                pdf_path, pdf_binary, from_page, to_page, kb_id
            )

            callback(0.5, "MinerU parsing finished.")

            # 5. 提取文本和坐标
            markdown_text, coordinate_map = extract_text_and_coordinates(sections)

            callback(0.6, f"Calling {self.strategy_name} chunking service...")

            # 6. 调用分块服务
            chunking_config = self.build_chunking_config(parser_config)
            result = call_chunking_service(
                markdown_text, coordinate_map, chunking_config,
                kwargs.get('doc_id', 'unknown'),
                kb_id,
                kwargs.get('tenant_id', 'unknown')
            )

            callback(0.9, f"{self.strategy_name} chunking completed.")

            # 7. 处理结果
            chunks_list = self.process_chunks_result(result)

            # 8. 转换为 RAGFlow 格式
            res = self._convert_to_ragflow_format(chunks_list, doc, lang)

            logging.info(f"{self.strategy_name} chunking completed: {len(res)} chunks created")
            callback(1.0, f"Completed: {len(res)} chunks")

            return res

        except Exception as e:
            logging.error(f"{self.strategy_name} chunking failed: {e}")
            callback(0.9, f"{self.strategy_name} chunking failed: {e}")
            raise

        finally:
            # 9. 清理临时文件
            self._cleanup_temp_files(temp_pdf_to_cleanup)

    def _prepare_base_doc(self, filename):
        """准备基础文档字典"""
        doc = {
            "docnm_kwd": filename,
            "title_tks": rag_tokenizer.tokenize(re.sub(r"\.[a-zA-Z]+$", "", filename))
        }
        doc["title_sm_tks"] = rag_tokenizer.fine_grained_tokenize(doc["title_tks"])
        return doc

    def _parse_with_mineru(self, pdf_path, pdf_binary, from_page, to_page, kb_id):
        """使用 MinerU 解析 PDF"""
        pdf_parser = MinerUParser()
        sections, tables = pdf_parser(
            pdf_path if not pdf_binary else pdf_binary,
            from_page=from_page,
            to_page=to_page,
            kb_id=kb_id
        )
        return sections, tables

    def _convert_to_ragflow_format(self, chunks_list, base_doc, lang):
        """将分块结果转换为 RAGFlow 格式"""
        is_english = lang.lower() == "english"
        res = []

        for chunk_data in chunks_list:
            d = copy.deepcopy(base_doc)

            # 提取文本和坐标
            chunk_text = chunk_data.get('content', '')
            positions = chunk_data.get('positions', [])

            if not chunk_text.strip():
                continue

            # 如果有预设 ID（父子分块），保留它
            if 'id' in chunk_data:
                d['_id_override'] = chunk_data['id']

            # 添加坐标信息
            if positions:
                add_positions(d, positions)

            # Tokenize
            tokenize(d, chunk_text, is_english)
            res.append(d)

        return res

    def _cleanup_temp_files(self, temp_pdf_to_cleanup):
        """清理临时 PDF 文件"""
        if temp_pdf_to_cleanup and os.path.exists(temp_pdf_to_cleanup):
            try:
                import shutil
                temp_dir = os.path.dirname(temp_pdf_to_cleanup)
                if temp_dir and os.path.exists(temp_dir) and temp_dir.startswith(tempfile.gettempdir()):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logging.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logging.warning(f"Failed to cleanup temporary files: {e}")
