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
Parent-Child Chunking Method

父子分块解析方法。

流程：
1. MinerU Parser 调用 KnowFlow Server 解析 PDF，返回 markdown + coordinate_map
2. 从 markdown 中提取纯文本和坐标映射
3. 调用 KnowFlow Server 的父子分块服务
4. 返回带坐标的分块结果（子块）

特点：
- 双层分块结构：父块（大块）+ 子块（小块）
- 父块用于上下文检索，子块用于精确匹配
- 精确的行级别坐标映射
"""

import logging
import os
import re
import copy
import requests

from deepdoc.parser import MinerUParser
from rag.nlp import rag_tokenizer, tokenize, add_positions


def chunk(filename, binary=None, from_page=0, to_page=100000,
          lang="Chinese", callback=None, **kwargs):
    """
    Parent-Child Chunking - 父子分块方法

    流程：
    1. MinerU 解析 PDF → markdown + coordinate_map
    2. 提取纯文本和坐标映射
    3. 调用父子分块服务 → 带坐标的分块结果

    Args:
        filename: 文件路径或文件名
        binary: 二进制文件内容
        from_page: 起始页码
        to_page: 结束页码
        lang: 语言（Chinese/English）
        callback: 进度回调函数
        **kwargs: 额外参数，包括 parser_config 等

    Returns:
        List[dict]: 分块结果列表（子块）
    """

    parser_config = kwargs.get(
        "parser_config", {
            "chunk_token_num": 256,  # 子块 token 数
            "min_chunk_tokens": 10,
            "parent_config": {
                "parent_chunk_size": 1024,
                "parent_chunk_overlap": 100,
                "retrieval_mode": "parent",
                "parent_split_level": 2
            }
        })

    doc = {
        "docnm_kwd": filename,
        "title_tks": rag_tokenizer.tokenize(re.sub(r"\.[a-zA-Z]+$", "", filename))
    }
    doc["title_sm_tks"] = rag_tokenizer.fine_grained_tokenize(doc["title_tks"])

    # 只支持 PDF 文件
    if not re.search(r"\.pdf$", filename, re.IGNORECASE):
        raise NotImplementedError("Parent-child chunking only supports PDF files")

    callback(0.1, "Start to parse.")
    logging.info("Using MinerU parser for parent-child chunking")
    callback(0.2, "Parsing with MinerU...")

    # 提取 kb_id（用于生成图片链接）
    kb_id = kwargs.get('kb_id', '') or kwargs.get('knowledgebase_id', '')

    pdf_parser = MinerUParser()
    sections, tables = pdf_parser(filename if not binary else binary,
                                 from_page=from_page, to_page=to_page,
                                 kb_id=kb_id)

    callback(0.5, "MinerU parsing finished.")

    # 从 sections 中提取文本和坐标映射
    markdown_text, coordinate_map = _extract_text_and_coordinates(sections)

    callback(0.6, "Calling parent-child chunking service...")

    # 调用 KnowFlow Server 的父子分块服务
    try:
        # 构建分块配置
        parent_config = parser_config.get('parent_config', {})
        chunking_config = {
            'strategy': 'parent_child',
            'chunk_token_num': int(parser_config.get('chunk_token_num', 256)),
            'min_chunk_tokens': int(parser_config.get('min_chunk_tokens', 10)),
            'parent_config': {
                'parent_chunk_size': int(parent_config.get('parent_chunk_size', 1024)),
                'parent_chunk_overlap': int(parent_config.get('parent_chunk_overlap', 100)),
                'retrieval_mode': parent_config.get('retrieval_mode', 'parent'),
                'parent_split_level': int(parent_config.get('parent_split_level', 2))
            }
        }

        result = _call_chunking_service(
            markdown_text, coordinate_map, chunking_config,
            kwargs.get('doc_id', 'unknown'),
            kwargs.get('kb_id', 'unknown'),
            kwargs.get('tenant_id', 'unknown')
        )

        callback(0.9, "Parent-child chunking completed.")

    except Exception as e:
        logging.error(f"Parent-child chunking service failed: {e}")
        callback(0.9, f"Parent-child chunking failed: {e}")
        raise

    # 转换为 RAGFlow 格式
    # KnowFlow Server 已经保存了父块和映射关系
    is_english = lang.lower() == "english"
    res = []

    # result 可能是列表（普通分块）或字典（包含 chunks 字段）
    chunks_list = result if isinstance(result, list) else result.get('chunks', [])

    for chunk_data in chunks_list:
        d = copy.deepcopy(doc)

        # 提取文本和坐标
        chunk_text = chunk_data.get('content', '')
        positions = chunk_data.get('positions', [])

        if not chunk_text.strip():
            continue

        # 如果 KnowFlow Server 返回了预设 ID（父子分块），使用它
        if 'id' in chunk_data:
            d['_id_override'] = chunk_data['id']

        # 添加坐标信息
        if positions:
            add_positions(d, positions)

        # Tokenize
        tokenize(d, chunk_text, is_english)
        res.append(d)

    logging.info(f"Parent-child chunking completed: {len(res)} child chunks created")
    callback(1.0, f"Completed: {len(res)} child chunks")

    return res


def _extract_text_and_coordinates(sections):
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


def _call_chunking_service(markdown_text, coordinate_map, chunking_config, doc_id, kb_id, tenant_id):
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
        List[dict]: [{"content": str, "positions": [[page, x1, x2, y1, y2], ...]}, ...]
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

        # 返回子块列表
        # KnowFlow Server 已经处理了父块的存储和映射关系
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


if __name__ == "__main__":
    import sys

    def dummy(prog=None, msg=""):
        print(f"[{prog*100:.1f}%] {msg}")

    if len(sys.argv) > 1:
        result = chunk(sys.argv[1], from_page=0, to_page=10, callback=dummy)
        print(f"\nGenerated {len(result)} chunks")
