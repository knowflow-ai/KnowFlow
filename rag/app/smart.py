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
Smart Chunking Method

基于 MinerU middle.json 的智能分块解析方法。

特点：
1. 使用 MinerU 解析 PDF，获取精确的文档结构和坐标
2. 调用 KnowFlow Server 的智能分块服务进行高质量分块
3. 保留精确的坐标信息用于文档定位
"""

import logging
import os
import re
import json
import copy
import requests
from io import BytesIO
from timeit import default_timer as timer

from api.db import LLMType
from api.db.services.llm_service import LLMBundle
from deepdoc.parser import MinerUParser
from deepdoc.parser.pdf_parser import PlainParser
from rag.nlp import rag_tokenizer, tokenize


def chunk(filename, binary=None, from_page=0, to_page=100000,
          lang="Chinese", callback=None, **kwargs):
    """
    Smart Chunking - 智能分块方法

    该方法使用 MinerU 解析 PDF，然后调用 KnowFlow Server 的智能分块服务。

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
            "chunk_token_num": 256,
            "min_chunk_tokens": 10,
            "chunking_strategy": "smart",  # smart/advanced/parent_child
            "layout_recognize": "MinerU"   # 默认使用 MinerU
        })

    doc = {
        "docnm_kwd": filename,
        "title_tks": rag_tokenizer.tokenize(re.sub(r"\.[a-zA-Z]+$", "", filename))
    }
    doc["title_sm_tks"] = rag_tokenizer.fine_grained_tokenize(doc["title_tks"])

    # 只支持 PDF 文件
    if not re.search(r"\.pdf$", filename, re.IGNORECASE):
        raise NotImplementedError("Smart chunking only supports PDF files")

    layout_recognizer = parser_config.get("layout_recognize", "MinerU")
    callback(0.1, "Start to parse.")

    # 检查是否使用 MinerU 解析
    if layout_recognizer not in ["MinerU", "DOTS"]:
        # 如果不是 MinerU/DOTS，降级到 Plain Text
        logging.warning(f"Smart chunking requires MinerU or DOTS, but got {layout_recognizer}. Falling back to PlainParser.")
        pdf_parser = PlainParser()
        sections, tables = pdf_parser(filename if not binary else binary,
                                     from_page=from_page, to_page=to_page, callback=callback)

        # 简单合并文本
        markdown_text = '\n\n'.join([text for text, _ in sections])
        coordinate_map = None

    else:
        # 使用 MinerU 解析
        logging.info(f"Using {layout_recognizer} parser for smart chunking")
        callback(0.2, f"Parsing with {layout_recognizer}...")

        # 提取 kb_id（用于生成图片链接）
        kb_id = kwargs.get('kb_id', '') or kwargs.get('knowledgebase_id', '')

        pdf_parser = MinerUParser()
        sections, tables = pdf_parser(filename if not binary else binary,
                                     from_page=from_page, to_page=to_page,
                                     kb_id=kb_id)

        callback(0.5, f"{layout_recognizer} parsing finished.")

        # 从 sections 中提取文本和坐标映射
        # sections 格式: [(text_with_tags, position_tag), ...]
        markdown_text, coordinate_map = _extract_text_and_coordinates(sections)

    callback(0.6, "Calling smart chunking service...")

    # 调用 KnowFlow Server 的智能分块服务
    try:
        chunks_with_positions = _call_smart_chunk_service(
            markdown_text=markdown_text,
            coordinate_map=coordinate_map,
            chunking_config={
                'strategy': parser_config.get('chunking_strategy', 'smart'),
                'chunk_token_num': int(parser_config.get('chunk_token_num', 256)),
                'min_chunk_tokens': int(parser_config.get('min_chunk_tokens', 10))
            },
            doc_id=kwargs.get('doc_id', 'unknown'),
            kb_id=kwargs.get('kb_id', 'unknown')
        )

        callback(0.9, "Smart chunking completed.")

    except Exception as e:
        logging.error(f"Smart chunking service failed: {e}")
        callback(0.9, f"Smart chunking failed: {e}")
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
            from rag.nlp import add_positions
            add_positions(d, positions)

        # Tokenize
        tokenize(d, chunk_text, is_english)
        res.append(d)

    logging.info(f"Smart chunking completed: {len(res)} chunks created")
    callback(1.0, f"Completed: {len(res)} chunks")

    return res


def _extract_text_and_coordinates(sections):
    """
    从 MinerU sections 中提取纯文本和坐标映射

    Args:
        sections: [(text_with_tags, position_tag), ...]

    Returns:
        (markdown_text, coordinate_map)
        coordinate_map: {line_number: [page, x1, x2, y1, y2]}
    """
    import re

    lines = []
    coordinate_map = {}
    line_number = 0

    pattern = r'@@(\d+)\t([\d.]+)\t([\d.]+)\t([\d.]+)\t([\d.]+)##'

    for text_with_tag, _ in sections:
        # 提取所有位置标签
        matches = list(re.finditer(pattern, text_with_tag))

        # 移除位置标签，获取纯文本
        clean_text = re.sub(pattern, '', text_with_tag)

        # 按行分割
        text_lines = clean_text.split('\n')

        for line in text_lines:
            if line.strip():
                # 为每一行记录坐标（使用该块的第一个坐标）
                if matches:
                    match = matches[0]
                    page_num = int(match.group(1))
                    x0 = float(match.group(2))
                    x1 = float(match.group(3))
                    top = float(match.group(4))
                    bottom = float(match.group(5))

                    coordinate_map[line_number] = [page_num, x0, x1, top, bottom]

            lines.append(line)
            line_number += 1

    markdown_text = '\n'.join(lines)
    return markdown_text, coordinate_map if coordinate_map else None


def _call_smart_chunk_service(markdown_text, coordinate_map, chunking_config, doc_id, kb_id):
    """
    调用 KnowFlow Server 的智能分块服务

    Args:
        markdown_text: markdown 文本
        coordinate_map: 坐标映射
        chunking_config: 分块配置
        doc_id: 文档ID
        kb_id: 知识库ID

    Returns:
        List[dict]: [{"content": str, "positions": [[page, x1, x2, y1, y2], ...]}, ...]
    """
    knowflow_server_url = os.getenv('KNOWFLOW_SERVER_URL', 'http://localhost:5000')
    api_url = f"{knowflow_server_url}/api/parse/smart_chunk"

    # 准备请求数据
    request_data = {
        'markdown_text': markdown_text,
        'chunking_config': chunking_config,
        'doc_id': doc_id,
        'kb_id': kb_id
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
            error_msg = f"Smart chunk API error: {response.status_code} - {response.text}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

        result = response.json()

        if not result.get('success'):
            error_msg = f"Smart chunking failed: {result.get('error', 'Unknown error')}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

        chunks = result.get('chunks', [])
        logging.info(f"Smart chunking service returned {len(chunks)} chunks")

        return chunks

    except requests.exceptions.Timeout:
        raise RuntimeError("Smart chunking service timeout (>300s)")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Cannot connect to KnowFlow Server at {knowflow_server_url}: {e}")
    except Exception as e:
        logging.exception(f"Smart chunking service failed: {e}")
        raise


if __name__ == "__main__":
    import sys

    def dummy(prog=None, msg=""):
        print(f"[{prog*100:.1f}%] {msg}")

    if len(sys.argv) > 1:
        result = chunk(sys.argv[1], from_page=0, to_page=10, callback=dummy)
        print(f"\nGenerated {len(result)} chunks")
