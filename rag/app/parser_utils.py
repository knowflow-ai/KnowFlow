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
Parser Utilities - 解析器共享工具

提供 MinerU 相关解析器的共享功能
"""

import logging
import os
import re
import copy
import requests

from deepdoc.parser import MinerUParser
from rag.nlp import rag_tokenizer, tokenize, add_positions


def extract_text_and_coordinates(sections):
    """
    从 MinerU sections 中提取纯文本和坐标映射

    Args:
        sections: [(text_with_tags, position_tag), ...]
        每个 section 对应 markdown 的一行，格式: @@page\tx0\tx1\ty0\ty1##text

    Returns:
        (markdown_text, coordinate_map)
        coordinate_map: {line_number: [page, x1, x2, y1, y2]}
    """
    lines = []
    coordinate_map = {}

    pattern = r'@@(\d+)\t([\d.]+)\t([\d.]+)\t([\d.]+)\t([\d.]+)##'

    for line_idx, (text_with_tag, _) in enumerate(sections):
        # 提取位置标签
        match = re.search(pattern, text_with_tag)

        # 移除位置标签，获取纯文本
        clean_text = re.sub(pattern, '', text_with_tag)
        lines.append(clean_text)

        # 记录坐标（如果有的话）
        if match and clean_text.strip():
            page_num = int(match.group(1))
            x0 = float(match.group(2))
            x1 = float(match.group(3))
            top = float(match.group(4))
            bottom = float(match.group(5))

            coordinate_map[line_idx] = [page_num, x0, x1, top, bottom]

    markdown_text = '\n'.join(lines)
    return markdown_text, coordinate_map


def call_chunking_service(markdown_text, coordinate_map, chunking_config, doc_id, kb_id, tenant_id):
    """
    调用 KnowFlow Server 的通用分块服务

    Args:
        markdown_text: markdown 文本
        coordinate_map: 坐标映射
        chunking_config: 分块配置
        doc_id: 文档ID
        kb_id: 知识库ID
        tenant_id: 租户ID

    Returns:
        List[dict]: [{"content": str, "positions": [[page, x1, x2, y1, y2], ...], "id": str (optional)}, ...]
    """
    knowflow_server_url = os.getenv('KNOWFLOW_SERVER_URL', 'http://localhost:5000')
    api_url = f"{knowflow_server_url}/api/parse/smart_chunk"

    # 准备请求数据
    request_data = {
        'markdown_text': markdown_text,
        'chunking_config': chunking_config,
        'doc_id': doc_id,
        'kb_id': kb_id,
        'tenant_id': tenant_id
    }

    # 添加坐标映射（如果有）
    if coordinate_map:
        # 将键转换为字符串（JSON 要求）
        request_data['coordinate_map'] = {str(k): v for k, v in coordinate_map.items()}

    try:
        response = requests.post(
            api_url,
            json=request_data,
            timeout=300  # 5分钟超时
        )

        if response.status_code != 200:
            error_msg = f"Chunking API error: {response.status_code} - {response.text}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

        result = response.json()

        if not result.get('success'):
            error_msg = f"Chunking failed: {result.get('error', 'Unknown error')}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

        chunks = result.get('chunks', [])
        logging.info(f"Chunking service returned {len(chunks)} chunks")

        return chunks

    except requests.exceptions.Timeout:
        raise RuntimeError("Chunking service timeout (>300s)")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Cannot connect to KnowFlow Server at {knowflow_server_url}: {e}")
    except Exception as e:
        logging.exception(f"Chunking service failed: {e}")
        raise


def parse_pdf_with_mineru(filename, binary, from_page, to_page, kb_id, callback):
    """
    使用 MinerU 解析 PDF

    Args:
        filename: 文件名
        binary: 二进制内容
        from_page: 起始页
        to_page: 结束页
        kb_id: 知识库ID
        callback: 回调函数

    Returns:
        (sections, tables): MinerU 解析结果
    """
    callback(0.1, "Start to parse.")
    logging.info("Using MinerU parser")
    callback(0.2, "Parsing with MinerU...")

    pdf_parser = MinerUParser()
    sections, tables = pdf_parser(
        filename if not binary else binary,
        from_page=from_page,
        to_page=to_page,
        kb_id=kb_id
    )

    callback(0.5, "MinerU parsing finished.")
    return sections, tables


def prepare_base_doc(filename):
    """
    准备基础文档字典

    Args:
        filename: 文件名

    Returns:
        dict: 基础文档字典，包含 docnm_kwd, title_tks 等
    """
    doc = {
        "docnm_kwd": filename,
        "title_tks": rag_tokenizer.tokenize(re.sub(r"\.[a-zA-Z]+$", "", filename))
    }
    doc["title_sm_tks"] = rag_tokenizer.fine_grained_tokenize(doc["title_tks"])
    return doc


def convert_chunks_to_ragflow_format(chunks_with_positions, base_doc, lang, callback):
    """
    将分块结果转换为 RAGFlow 格式

    Args:
        chunks_with_positions: 带坐标的分块列表
        base_doc: 基础文档字典
        lang: 语言
        callback: 回调函数

    Returns:
        List[dict]: RAGFlow 格式的分块列表
    """
    is_english = lang.lower() == "english"
    res = []

    for chunk_data in chunks_with_positions:
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


def mineru_chunk_pipeline(
    filename, binary, from_page, to_page, lang, callback,
    strategy, parser_config, doc_id, kb_id, tenant_id,
    strategy_name=""
):
    """
    MinerU 解析器的通用分块流程

    Args:
        filename: 文件名
        binary: 二进制内容
        from_page: 起始页
        to_page: 结束页
        lang: 语言
        callback: 回调函数
        strategy: 分块策略名称
        parser_config: 解析器配置
        doc_id: 文档ID
        kb_id: 知识库ID
        tenant_id: 租户ID
        strategy_name: 策略显示名称（用于日志）

    Returns:
        List[dict]: RAGFlow 格式的分块列表
    """
    # 检查文件类型
    if not re.search(r"\.pdf$", filename, re.IGNORECASE):
        raise NotImplementedError(f"{strategy_name} chunking only supports PDF files")

    # 准备基础文档
    doc = prepare_base_doc(filename)

    # MinerU 解析
    sections, tables = parse_pdf_with_mineru(
        filename, binary, from_page, to_page, kb_id, callback
    )

    # 提取文本和坐标
    markdown_text, coordinate_map = extract_text_and_coordinates(sections)

    callback(0.6, f"Calling {strategy_name} chunking service...")

    # 调用分块服务
    try:
        chunks_with_positions = call_chunking_service(
            markdown_text, coordinate_map, parser_config,
            doc_id, kb_id, tenant_id
        )
        callback(0.9, f"{strategy_name} chunking completed.")
    except Exception as e:
        logging.error(f"{strategy_name} chunking service failed: {e}")
        callback(0.9, f"{strategy_name} chunking failed: {e}")
        raise

    # 转换为 RAGFlow 格式
    res = convert_chunks_to_ragflow_format(chunks_with_positions, doc, lang, callback)

    logging.info(f"{strategy_name} chunking completed: {len(res)} chunks created")
    callback(1.0, f"Completed: {len(res)} chunks")

    return res
