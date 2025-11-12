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
Modern Parser Base Class - 现代解析器抽象基类

支持多种 PDF 解析器（MinerU、DOTS 等），提供标准的文档解析流程。
子类只需实现差异化逻辑。
"""

import logging
import os
import re
import copy
import tempfile
from abc import ABC, abstractmethod

from rag.nlp import rag_tokenizer, tokenize, add_positions
from rag.app.parser_utils import (
    ensure_pdf,
    extract_text_and_coordinates,
    call_chunking_service,
    process_markdown_images
)


class ModernParserBase(ABC):
    """
    现代解析器抽象基类

    支持多种 PDF 解析器（通过 layout_recognize 配置选择）：
    - MinerU: 高精度 OCR 解析器
    - DOTS: 另一种 OCR 解析器
    - DeepDOC: 默认解析器（未来支持）

    标准流程：
    1. 文件转换（ensure_pdf）
    2. 准备基础文档
    3. 解析器解析（根据 layout_recognize 选择）
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

    def _extract_vision_config(self, parser_config):
        """
        从 parser_config 中提取图片理解配置

        Args:
            parser_config: 解析器配置

        Returns:
            dict: 图片理解配置
        """
        vision_config = {}

        # 提取图片理解相关配置
        if 'enable_vision_enhancement' in parser_config:
            vision_config['enable_vision_enhancement'] = parser_config['enable_vision_enhancement']

        if 'vision_description_format' in parser_config:
            vision_config['vision_description_format'] = parser_config['vision_description_format']

        if 'vision_batch_size' in parser_config:
            vision_config['vision_batch_size'] = parser_config['vision_batch_size']

        return vision_config

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
        is_markdown = False

        try:
            # 检查是否是 Markdown 文件
            if isinstance(filename, str) and filename.lower().endswith(('.md', '.markdown')):
                is_markdown = True
                logging.info(f"Detected Markdown file: {filename}")
                pdf_path = filename
                pdf_binary = binary
            else:
                # 1. 确保输入是 PDF（如果不是则转换）
                pdf_path, temp_pdf_to_cleanup, pdf_binary = ensure_pdf(filename, binary)

            # 2. 准备基础文档（使用原始文件名）
            doc = self._prepare_base_doc(filename)

            # 3. 获取配置
            parser_config = kwargs.get("parser_config", self.get_default_config())

            callback(0.1, "Start to parse.")

            # 4. 处理 Markdown 或 PDF
            kb_id = kwargs.get('kb_id', '') or kwargs.get('knowledgebase_id', '')

            if is_markdown:
                # Markdown 文件：直接读取内容
                logging.info(f"Reading Markdown content directly")
                callback(0.2, "Reading Markdown file...")

                # 读取 Markdown 内容
                if pdf_binary:
                    markdown_text = pdf_binary.decode('utf-8')
                else:
                    with open(pdf_path, 'r', encoding='utf-8') as f:
                        markdown_text = f.read()

                # 处理 Markdown 中的图片（上传到 MinIO 并替换路径）
                callback(0.3, "Processing images in Markdown...")
                markdown_text = process_markdown_images(markdown_text, pdf_path, kb_id)

                # Markdown 不需要坐标映射
                coordinate_map = {}

                # 生成虚拟的 sections（用于后续处理）
                sections = [(markdown_text, "")]
                tables = []

                callback(0.5, "Markdown file processed successfully.")
            else:
                # PDF 文件：使用现有��程
                # 4. 根据 layout_recognize 选择解析器
                layout_recognizer = parser_config.get("layout_recognize", "MinerU")
                logging.info(f"Using {layout_recognizer} parser for {self.strategy_name} chunking")
                callback(0.2, f"Parsing with {layout_recognizer}...")

                # 5. 解析 PDF
                sections, tables = self._parse_with_layout_recognizer(
                    layout_recognizer, pdf_path, pdf_binary, from_page, to_page, kb_id
                )

                callback(0.5, f"{layout_recognizer} parsing finished.")

                # 6. 提取文本和坐标
                markdown_text, coordinate_map = extract_text_and_coordinates(sections)

            callback(0.6, f"Calling {self.strategy_name} chunking service...")

            # 7. 调用分块服务（PDF 和 Markdown 统一处理）
            chunking_config = self.build_chunking_config(parser_config)
            result = call_chunking_service(
                markdown_text, coordinate_map, chunking_config,
                kwargs.get('doc_id', 'unknown'),
                kb_id,
                kwargs.get('tenant_id', 'unknown')
            )

            callback(0.9, f"{self.strategy_name} chunking completed.")

            # 8. 处理结果
            chunks_list = self.process_chunks_result(result)

            # 9. 转换为 RAGFlow 格式
            res = self._convert_to_ragflow_format(chunks_list, doc, lang)

            logging.info(f"{self.strategy_name} chunking completed: {len(res)} chunks created")
            callback(1.0, f"Completed: {len(res)} chunks")

            return res

        except Exception as e:
            logging.error(f"{self.strategy_name} chunking failed: {e}")
            callback(0.9, f"{self.strategy_name} chunking failed: {e}")
            raise

        finally:
            # 10. 清理临时文件
            self._cleanup_temp_files(temp_pdf_to_cleanup)

    def _prepare_base_doc(self, filename):
        """准备基础文档字典"""
        doc = {
            "docnm_kwd": filename,
            "title_tks": rag_tokenizer.tokenize(re.sub(r"\.[a-zA-Z]+$", "", filename))
        }
        doc["title_sm_tks"] = rag_tokenizer.fine_grained_tokenize(doc["title_tks"])
        return doc

    def _parse_with_layout_recognizer(self, layout_recognizer, pdf_path, pdf_binary, from_page, to_page, kb_id):
        """
        根据 layout_recognizer 选择并使用对应的解析器

        Args:
            layout_recognizer: 布局识别器类型 (MinerU/DOTS/PaddleOCR/DeepDOC)
            pdf_path: PDF 文件路径
            pdf_binary: PDF 二进制数据
            from_page: 起始页码
            to_page: 结束页码
            kb_id: 知识库 ID

        Returns:
            Tuple[List, List]: (sections, tables)
        """
        if layout_recognizer == "MinerU":
            from deepdoc.parser import MinerUParser
            pdf_parser = MinerUParser()
        elif layout_recognizer == "DOTS":
            from deepdoc.parser import DOTSParser
            pdf_parser = DOTSParser()
        elif layout_recognizer == "PaddleOCR":
            from deepdoc.parser import PaddleOCRParser
            pdf_parser = PaddleOCRParser()
        else:
            # 默认使用 MinerU
            logging.warning(f"Unknown layout_recognizer: {layout_recognizer}, falling back to MinerU")
            from deepdoc.parser import MinerUParser
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

        for chunk_idx, chunk_data in enumerate(chunks_list):
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
                # 使用 chunk_index 作为排序依据，确保 chunks 按生成顺序排列
                d["top_int"] = [chunk_idx]

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
