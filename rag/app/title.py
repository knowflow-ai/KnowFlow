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
Title-based Chunking Method

基于标题的分块解析方法。

流程：
1. MinerU Parser 调用 KnowFlow Server 解析 PDF，返回 markdown + coordinate_map
2. 从 markdown 中提取纯文本和坐标映射
3. 调用 KnowFlow Server 的高级分块服务（包含标题识别）
4. 返回带坐标的分块结果

特点：
- 识别文档标题层级结构
- 基于标题进行语义分块
- 保留标题上下文信息
- 精确的行级别坐标映射
"""

import logging
import copy

from deepdoc.parser import MinerUParser
from rag.nlp import rag_tokenizer, tokenize, add_positions
from rag.app.parser_utils import extract_text_and_coordinates, call_chunking_service


def chunk(filename, binary=None, from_page=0, to_page=100000,
          lang="Chinese", callback=None, **kwargs):
    """
    Title-based Chunking - 基于标题的分块方法

    流程：
    1. MinerU 解析 PDF → markdown + coordinate_map
    2. 提取纯文本和坐标映射
    3. 调用标题分块服务 → 带坐标的分块结果

    Args:
        filename: 文件路径或文件名
        binary: 二进制文件内容
        from_page: 起始页码
        to_page: 结束页码
        lang: 语言（Chinese/English）
        callback: 进度回调函数
        **kwargs: 额外参数，包括 parser_config 等

    Returns:
        List[dict]: 分块结果列表
    """

    parser_config = kwargs.get(
        "parser_config", {
            "chunk_token_num": 512,
            "min_chunk_tokens": 10,
            "include_metadata": True,  # 包含标题元数据
            "split_level": 3,  # H1/H2/H3 作为分割边界
        })

    doc = {
        "docnm_kwd": filename,
        "title_tks": rag_tokenizer.tokenize(re.sub(r"\.[a-zA-Z]+$", "", filename))
    }
    doc["title_sm_tks"] = rag_tokenizer.fine_grained_tokenize(doc["title_tks"])

    # 只支持 PDF 文件
    if not re.search(r"\.pdf$", filename, re.IGNORECASE):
        raise NotImplementedError("Title-based chunking only supports PDF files")

    callback(0.1, "Start to parse.")
    logging.info("Using MinerU parser for title-based chunking")
    callback(0.2, "Parsing with MinerU...")

    # 提取 kb_id（用于生成图片链接）
    kb_id = kwargs.get('kb_id', '') or kwargs.get('knowledgebase_id', '')

    pdf_parser = MinerUParser()
    sections, tables = pdf_parser(filename if not binary else binary,
                                 from_page=from_page, to_page=to_page,
                                 kb_id=kb_id)

    callback(0.5, "MinerU parsing finished.")

    # 从 sections 中提取文本和坐标映射
    markdown_text, coordinate_map = extract_text_and_coordinates(sections)

    callback(0.6, "Calling title-based chunking service...")

    # 调用 KnowFlow Server 的标题分块服务
    try:
        chunks_with_positions = call_chunking_service(
            markdown_text, coordinate_map,
            {
                'strategy': 'title',  # 使用 title 策略（严格按标题分割）
                'chunk_token_num': int(parser_config.get('chunk_token_num', 512)),
                'min_chunk_tokens': int(parser_config.get('min_chunk_tokens', 10)),
                'include_metadata': bool(parser_config.get('include_metadata', True)),
                'split_level': int(parser_config.get('split_level', 3))
            },
            kwargs.get('doc_id', 'unknown'),
            kwargs.get('kb_id', 'unknown'),
            kwargs.get('tenant_id', 'unknown')
        )

        callback(0.9, "Title-based chunking completed.")

    except Exception as e:
        logging.error(f"Title-based chunking service failed: {e}")
        callback(0.9, f"Title-based chunking failed: {e}")
        raise

    # 转换为 RAGFlow 格式
    is_english = lang.lower() == "english"
    res = []

    for chunk_data in chunks_with_positions:
        d = copy.deepcopy(doc)

        # 提取文本和坐标
        chunk_text = chunk_data.get('content', '')
        positions = chunk_data.get('positions', [])

        if not chunk_text.strip():
            continue

        # 添加坐标信息
        if positions:
            add_positions(d, positions)

        # Tokenize
        tokenize(d, chunk_text, is_english)
        res.append(d)

    logging.info(f"Title-based chunking completed: {len(res)} chunks created")
    callback(1.0, f"Completed: {len(res)} chunks")

    return res


if __name__ == "__main__":
    import sys

    def dummy(prog=None, msg=""):
        print(f"[{prog*100:.1f}%] {msg}")

    if len(sys.argv) > 1:
        result = chunk(sys.argv[1], from_page=0, to_page=10, callback=dummy)
        print(f"\nGenerated {len(result)} chunks")
