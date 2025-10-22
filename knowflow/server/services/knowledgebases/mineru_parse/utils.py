#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
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
import mysql.connector
import os
import tiktoken
import json
import re
from markdown import markdown as md_to_html
import time
import difflib
import xxhash
import logging
try:
    from markdown_it import MarkdownIt
    from markdown_it.tree import SyntaxTreeNode
    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False
    print("Warning: markdown-it-py not available. Please install with: pip install markdown-it-py")

from ...config import CONFIG, APP_CONFIG


# 分块模式配置
# CHUNK_METHOD = os.getenv('CHUNK_METHOD', 'smart')  # 默认使用 smart 模式


def get_configured_chunk_method():
    """获取配置的分块方法"""
    return APP_CONFIG.chunk_method


def is_dev_mode():
    """检查是否处于开发模式"""
    return APP_CONFIG.dev_mode


def should_cleanup_temp_files():
    """
    检查是否应该清理临时文件

    清理策略：
    - dev_mode=True:  不清理临时文件（保留用于调试）
    - dev_mode=False: 清理临时文件（节省磁盘空间）
    """
    return not is_dev_mode()


def split_markdown_to_chunks_configured(txt, chunk_token_num=256, min_chunk_tokens=10, coordinate_map=None, **kwargs):
    """
    根据配置选择合适的分块方法的统一接口

    支持的分块方法：
    - 'parent_child': 父子分块模式，基于Smart分块的双层结构
    - 'strict_regex': 严格按正则表达式分块（当配置启用时）
    - 'advanced': split_markdown_to_chunks_advanced (高级分块，混合策略)
    - 'smart': split_markdown_to_chunks_smart (智能分块，基于AST，默认)
    - 'basic': split_markdown_to_chunks (基础分块)

    Args:
        txt: markdown文本
        chunk_token_num: 分块token数
        min_chunk_tokens: 最小分块token数
        coordinate_map: 坐标映射 {line_number: [page, x1, x2, y1, y2]}，如果提供则返回带坐标的分块
        **kwargs: 其他参数

    Returns:
        如果 coordinate_map=None: 返回字符串列表
        如果提供 coordinate_map: 返回字典列表 [{"content": str, "coordinates": [[page, x1, x2, y1, y2], ...]}]

    可通过环境变量 CHUNK_METHOD 配置，支持的值：parent_child, advanced, smart, basic
    也可通过kwargs传入自定义配置：
    - chunking_config: 分块配置字典，包含strategy等字段
    """
    
    # 检查是否有自定义的分块配置（从文档配置传入）
    custom_chunking_config = kwargs.get('chunking_config', None)
    
    if custom_chunking_config:
        # 使用文档级别的分块配置
        strategy = custom_chunking_config.get('strategy', 'smart')
        chunk_token_num = custom_chunking_config.get('chunk_token_num', chunk_token_num)
        min_chunk_tokens = custom_chunking_config.get('min_chunk_tokens', min_chunk_tokens)

        if strategy == 'parent_child':
            chunks = split_markdown_to_chunks_parent_child(
                txt,
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                parent_config=custom_chunking_config.get('parent_config', {}),
                doc_id=kwargs.get('doc_id', 'unknown'),
                kb_id=kwargs.get('kb_id', 'unknown'),
                tenant_id=kwargs.get('tenant_id', 'unknown'),
                enable_heading_in_content=custom_chunking_config.get('enable_heading_in_content', False)
            )
            # 父子分块也支持坐标附加
            if coordinate_map is not None:
                chunks = _attach_coordinates_to_parent_child_chunks(chunks, txt, coordinate_map)

                # 更新 _last_parent_child_result，添加坐标信息
                global _last_parent_child_result
                if _last_parent_child_result and isinstance(chunks, list):
                    if len(chunks) == len(_last_parent_child_result.get('child_chunks', [])):
                        for i, chunk_with_coord in enumerate(chunks):
                            if isinstance(chunk_with_coord, dict) and 'coordinates' in chunk_with_coord:
                                _last_parent_child_result['child_chunks'][i]['coordinates'] = chunk_with_coord['coordinates']
            return chunks
        elif strategy == 'title':
            include_metadata = kwargs.pop('include_metadata', False)
            split_level = custom_chunking_config.get('split_level', 3)
            chunks = split_markdown_to_chunks_title(
                txt,
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                split_level=split_level,
                include_metadata=include_metadata,
                enable_heading_in_content=custom_chunking_config.get('enable_heading_in_content', False)
            )

        elif strategy == 'advanced':
            include_metadata = kwargs.pop('include_metadata', False)
            overlap_ratio = kwargs.pop('overlap_ratio', 0.0)
            chunks = split_markdown_to_chunks_advanced(
                txt,
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                overlap_ratio=overlap_ratio,
                include_metadata=include_metadata
            )

        elif strategy == 'strict_regex':
            regex_pattern = custom_chunking_config.get('regex_pattern', '')
            if regex_pattern:
                chunks = split_markdown_to_chunks_strict_regex(
                    txt,
                    chunk_token_num=chunk_token_num,
                    min_chunk_tokens=min_chunk_tokens,
                    regex_pattern=regex_pattern
                )
            else:
                chunks = split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)

        elif strategy == 'smart':
            enable_heading = custom_chunking_config.get('enable_heading_in_content', False)
            logging.info(f"Smart分块配置: enable_heading_in_content={enable_heading}, custom_chunking_config={custom_chunking_config}")
            chunks = split_markdown_to_chunks_smart(
                txt,
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                enable_heading_in_content=enable_heading
            )
        elif strategy == 'basic':
            delimiter = custom_chunking_config.get('delimiter', "\n!?。；！？")
            chunks = split_markdown_to_chunks(
                txt,
                chunk_token_num=chunk_token_num,
                delimiter=delimiter
            )
        else:
            chunks = []
    else:
        # 使用环境变量配置
        method = get_configured_chunk_method()

        if method == 'advanced':
            include_metadata = kwargs.pop('include_metadata', False)
            overlap_ratio = kwargs.pop('overlap_ratio', 0.0)
            chunks = split_markdown_to_chunks_advanced(
                txt,
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                overlap_ratio=overlap_ratio,
                include_metadata=include_metadata
            )
        elif method == 'basic':
            delimiter = kwargs.pop('delimiter', "\n!?。；！？")
            chunks = split_markdown_to_chunks(
                txt,
                chunk_token_num=chunk_token_num,
                delimiter=delimiter
            )
        else:  # 默认使用智能分块
            chunks = split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)

    # 统一处理坐标映射
    if coordinate_map is not None:
        return _attach_coordinates_to_chunks(chunks, txt, coordinate_map)
    else:
        return chunks


def _attach_coordinates_to_parent_child_chunks(parent_child_data, markdown_text, coordinate_map):
    """
    为父子分块附加坐标信息

    Args:
        parent_child_data: 父子分块数据，可能是：
            - 字典格式: {"parent_chunks": [...], "child_chunks": [...], "relationships": [...]}
            - 列表格式: [chunk1, chunk2, ...] (简化版，只包含子分块)
        markdown_text: 完整的markdown文本
        coordinate_map: 坐标映射

    Returns:
        附加了坐标的父子分块数据（保持输入格式）
    """
    from typing import Dict, List

    # 处理简化的列表格式（只有子分块）
    if isinstance(parent_child_data, list):
        # 提取内容（可能是字符串或字典）
        contents = []
        for item in parent_child_data:
            if isinstance(item, dict):
                contents.append(item.get('content', ''))
            else:
                contents.append(str(item))

        # 附加坐标
        chunks_with_coords = _attach_coordinates_to_chunks(contents, markdown_text, coordinate_map)

        # 合并回原始结构
        result = []
        for i, item in enumerate(parent_child_data):
            if isinstance(item, dict):
                item_copy = item.copy()
                if i < len(chunks_with_coords):
                    item_copy['coordinates'] = chunks_with_coords[i].get('coordinates', [])
                result.append(item_copy)
            else:
                # 字符串转为字典
                if i < len(chunks_with_coords):
                    result.append(chunks_with_coords[i])

        return result

    # 处理完整的字典格式
    if isinstance(parent_child_data, dict):
        # 提取父分块和子分块的内容
        parent_contents = [p.get('content', '') if isinstance(p, dict) else str(p)
                          for p in parent_child_data.get('parent_chunks', [])]
        child_contents = [c.get('content', '') if isinstance(c, dict) else str(c)
                         for c in parent_child_data.get('child_chunks', [])]

        # 使用通用的坐标附加函数
        parent_with_coords = _attach_coordinates_to_chunks(parent_contents, markdown_text, coordinate_map)
        child_with_coords = _attach_coordinates_to_chunks(child_contents, markdown_text, coordinate_map)

        # 将坐标信息合并回原始的父子分块结构
        result = {
            'parent_chunks': [],
            'child_chunks': [],
            'relationships': parent_child_data.get('relationships', [])
        }

        # 合并父分块
        for i, parent in enumerate(parent_child_data.get('parent_chunks', [])):
            if isinstance(parent, dict):
                parent_copy = parent.copy()
                if i < len(parent_with_coords):
                    parent_copy['coordinates'] = parent_with_coords[i].get('coordinates', [])
                result['parent_chunks'].append(parent_copy)

        # 合并子分块
        for i, child in enumerate(parent_child_data.get('child_chunks', [])):
            if isinstance(child, dict):
                child_copy = child.copy()
                if i < len(child_with_coords):
                    child_copy['coordinates'] = child_with_coords[i].get('coordinates', [])
                result['child_chunks'].append(child_copy)

        return result

    # 未知格式，原样返回
    return parent_child_data


def _attach_coordinates_to_chunks(chunks, markdown_text, coordinate_map):
    """
    为分块附加坐标信息（方案A：基于行号的直接映射）

    Args:
        chunks: 字符串分块列表
        markdown_text: 完整的markdown文本
        coordinate_map: 坐标映射 {line_number: [page, x1, x2, y1, y2]}

    Returns:
        带坐标的分块列表 [{"content": str, "coordinates": [[page, x1, x2, y1, y2], ...]}]
    """
    from typing import Dict, List

    # 标准化 coordinate_map 的键为整数
    normalized_coord_map: Dict[int, List] = {}
    for key, value in coordinate_map.items():
        try:
            idx = int(key)
            normalized_coord_map[idx] = value
        except (TypeError, ValueError):
            continue

    # 将markdown按行分割
    md_lines = markdown_text.split('\n')

    # 构建行文本到行号的映射（支持重复文本）
    line_lookup: Dict[str, List[int]] = {}
    for idx, line in enumerate(md_lines):
        stripped = line.strip()
        if stripped:
            line_lookup.setdefault(stripped, []).append(idx)

    # 为每个分块附加坐标
    chunks_with_coords = []
    used_indices = set()  # 记录已使用的行号

    for chunk_idx, chunk in enumerate(chunks):
        # 处理字典或字符串类型的 chunk
        if isinstance(chunk, dict):
            chunk_text = chunk.get('content', '')
            if not chunk_text or not chunk_text.strip():
                continue
        else:
            chunk_text = chunk
            if not chunk_text or not chunk_text.strip():
                continue

        chunk_lines = chunk_text.split('\n')
        chunk_coordinates = []

        # 遍历分块中的每一行
        for chunk_line in chunk_lines:
            stripped_line = chunk_line.strip()
            if not stripped_line:
                continue

            # 1. 精确匹配：查找所有候选行号，选择第一个未使用的
            candidate_indices = line_lookup.get(stripped_line, [])
            selected_idx = None

            for line_idx in candidate_indices:
                if line_idx not in used_indices:
                    selected_idx = line_idx
                    break

            # 2. 如果精确匹配失败，尝试部分匹配（处理列表项或轻微差异）
            if selected_idx is None:
                for line_idx, md_line in enumerate(md_lines):
                    if line_idx in used_indices:
                        continue

                    md_line_stripped = md_line.strip()
                    if not md_line_stripped:
                        continue

                    # 去除列表前缀后再比较
                    md_line_core = md_line_stripped
                    if md_line_core.startswith(('- ', '* ', '• ', '· ')):
                        md_line_core = md_line_core[2:].strip()

                    chunk_core = stripped_line
                    if chunk_core.startswith(('- ', '* ', '• ', '· ')):
                        chunk_core = chunk_core[2:].strip()

                    if (chunk_core and md_line_core and
                            (chunk_core == md_line_core or
                             chunk_core in md_line_core or
                             md_line_core in chunk_core)):
                        selected_idx = line_idx
                        break

            # 3. 记录坐标
            if selected_idx is not None:
                used_indices.add(selected_idx)
                coord = normalized_coord_map.get(selected_idx)
                if coord and coord not in chunk_coordinates:
                    chunk_coordinates.append(coord)

        # 添加带坐标的分块
        chunks_with_coords.append({
            'content': chunk_text,
            'coordinates': chunk_coordinates
        })

    return chunks_with_coords


def singleton(cls, *args, **kw):
    instances = {}

    def _singleton():
        key = str(cls) + str(os.getpid())
        if key not in instances:
            instances[key] = cls(*args, **kw)
        return instances[key]

    return _singleton


# 设置tiktoken缓存目录，优先使用环境变量，否则使用默认路径
tiktoken_cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR", "/opt/tiktoken_cache")
# 确保缓存目录存在
os.makedirs(tiktoken_cache_dir, exist_ok=True)
os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir
# encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
encoder = tiktoken.get_encoding("cl100k_base")


def num_tokens_from_string(string: str, model_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    try:
        return len(encoder.encode(string))
    except Exception:
        return 0


def truncate(string: str, max_len: int) -> str:
    """Returns truncated text if the length of text exceed max_len."""
    return encoder.decode(encoder.encode(string)[:max_len])


def _extract_tables_and_remainder_md(txt: str) -> (str, list[str]):
    """
    Extracts markdown tables from text and returns the remaining text
    and a list of table strings.
    This is a simplified implementation.
    """
    lines = txt.split('\n')
    tables = []
    remainder_lines = []
    in_table = False
    current_table = []

    for line in lines:
        stripped_line = line.strip()
        # Basic check for table row (starts and ends with |)
        is_table_line = stripped_line.startswith('|') and stripped_line.endswith('|')
        # Basic check for table separator (e.g., |---|---| or |:---|:---:|)
        is_separator_line = True
        if is_table_line and '-' in stripped_line:
            parts = [p.strip() for p in stripped_line[1:-1].split('|')]
            if not all(set(p) <= set('-:') for p in parts if p): # allow only -, :
                is_separator_line = False
            if not parts: # Handles | | case
                is_separator_line = False
        else:
            is_separator_line = False


        if is_table_line or (in_table and stripped_line): # Continue table if already in it and line is not empty
            if not in_table and is_table_line and not is_separator_line: # Potential start of a new table (header)
                # Look ahead for a separator line
                next_line_index = lines.index(line) + 1
                if next_line_index < len(lines):
                    next_line_stripped = lines[next_line_index].strip()
                    next_is_separator = next_line_stripped.startswith('|') and next_line_stripped.endswith('|') and '-' in next_line_stripped
                    if next_is_separator:
                        parts_next = [p.strip() for p in next_line_stripped[1:-1].split('|')]
                        if not all(set(p) <= set('-:') for p in parts_next if p):
                            next_is_separator = False
                        if not parts_next:
                            next_is_separator = False
                    if next_is_separator:
                        in_table = True
                        current_table.append(line)
                    else: # Not a table header
                        remainder_lines.append(line)
                else: # No next line
                     remainder_lines.append(line)
            elif in_table:
                current_table.append(line)
                if not is_table_line and not stripped_line: # Empty line might end the table
                    tables.append("\n".join(current_table))
                    current_table = []
                    in_table = False
                    remainder_lines.append(line) # Add the empty line to remainder
            else: # A line that looks like a table line but isn't starting a valid table
                remainder_lines.append(line)

        elif in_table and not stripped_line : # An empty line definitely ends a table
            tables.append("\n".join(current_table))
            current_table = []
            in_table = False
            remainder_lines.append(line) # Add the empty line to remainder
        elif in_table and not is_table_line : # A non-table line also ends a table
            tables.append("\n".join(current_table))
            current_table = []
            in_table = False
            remainder_lines.append(line) # Add this line to remainder
        else:
            remainder_lines.append(line)

    if current_table: # Add any remaining table
        tables.append("\n".join(current_table))

    return "\n".join(remainder_lines), tables

def split_markdown_to_chunks(txt, chunk_token_num=128, delimiter="\n!?。；！？"):
    """
    Splits markdown text into chunks, processing tables separately and merging text sections
    to be consistent with RAGFlow's naive.py markdown handling.
    """
    if not txt or not txt.strip():
        return []

    # 1. Extract tables and remainder text
    remainder_text, extracted_tables = _extract_tables_and_remainder_md(txt)
    
    processed_chunks = []
    
    # 2. Process tables: convert to HTML and add as individual chunks
    for table_md in extracted_tables:
        if table_md.strip():
            # Ensure markdown.extensions.tables is available
            try:
                table_html = md_to_html(table_md, extensions=['markdown.extensions.tables'])
                processed_chunks.append(table_html)
            except Exception as e:
                # If conversion fails, add raw table markdown as a fallback
                # Or log an error and skip
                processed_chunks.append(table_md)
                print(f"[WARNING] Failed to convert table to HTML: {e}. Added raw table markdown.")


    # 3. Initial splitting of remainder_text (non-table text)
    initial_sections = []
    if remainder_text and remainder_text.strip():
        for sec_line in remainder_text.split("\n"):
            line_content = sec_line.strip()
            if not line_content: # Keep empty lines if they are part of structure or to respect original newlines for merging
                initial_sections.append(sec_line) # Add the original line with its spacing
                continue

            if num_tokens_from_string(sec_line) > 3 * chunk_token_num:
                # Split long lines, trying to preserve original spacing if line was just very long
                mid_point = len(sec_line) // 2
                initial_sections.append(sec_line[:mid_point])
                initial_sections.append(sec_line[mid_point:])
            else:
                initial_sections.append(sec_line)
    
    # 4. Merge initial text sections into chunks respecting token limits (naive_merge logic)
    # This part needs to be careful about document order with tables.
    # The strategy here is to process text between tables.
    # However, _extract_tables_and_remainder_md might not preserve order perfectly if tables are interspersed.
    # For simplicity, we'll process all tables first, then all text. A more sophisticated approach
    # would interleave them based on original position.

    final_text_chunks = []
    current_chunk_parts = []
    current_token_count = 0

    for section_text in initial_sections:
        section_token_count = num_tokens_from_string(section_text)
        
        if not section_text.strip() and not current_chunk_parts: # Skip leading empty/whitespace sections
            continue

        if current_token_count + section_token_count <= chunk_token_num:
            current_chunk_parts.append(section_text)
            current_token_count += section_token_count
        else:
            # Finalize current_chunk if it's not empty
            if current_chunk_parts:
                final_text_chunks.append("\n".join(current_chunk_parts).strip())
            
            # Start a new chunk with the current section
            # If a single section itself is too large, it will be added as is.
            # RAGFlow's naive_merge might have more sophisticated splitting for oversized single sections.
            # For now, we add it as is or split it if it's drastically oversized.
            if section_token_count > chunk_token_num and section_token_count <= 3 * chunk_token_num: # Tolerable oversize
                 final_text_chunks.append(section_text.strip())
                 current_chunk_parts = []
                 current_token_count = 0
            elif section_token_count > 3 * chunk_token_num: # Drastically oversized, needs splitting
                # This split is basic, RAGFlow might be more nuanced
                mid = len(section_text) // 2
                final_text_chunks.append(section_text[:mid].strip())
                final_text_chunks.append(section_text[mid:].strip())
                current_chunk_parts = []
                current_token_count = 0
            else: # Start new chunk
                current_chunk_parts = [section_text]
                current_token_count = section_token_count
    
    # Add any remaining part as the last chunk
    if current_chunk_parts:
        final_text_chunks.append("\n".join(current_chunk_parts).strip())

    # Combine table HTML chunks and text chunks.
    # This simple combination appends all text chunks after all table chunks.
    # A more accurate implementation would require knowing the original order.
    # Given the current _extract_tables_and_remainder_md, this is a limitation.
    all_chunks = [chunk for chunk in processed_chunks if chunk.strip()] # Add table chunks first
    all_chunks.extend([chunk for chunk in final_text_chunks if chunk.strip()])
    
    return all_chunks


_blocks_cache = {}


def update_document_progress(doc_id, progress=None, message=None, status=None, run=None, chunk_count=None, process_duration=None):
    """更新数据库中文档的进度和状态"""
    conn = None
    cursor = None
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        updates = []
        params = []

        if progress is not None:
            updates.append("progress = %s")
            params.append(float(progress))
        if message is not None:
            updates.append("progress_msg = %s")
            params.append(message)
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if run is not None:
            updates.append("run = %s")
            params.append(run)
        if chunk_count is not None:
             updates.append("chunk_num = %s")
             params.append(chunk_count)
        if process_duration is not None:
            updates.append("process_duration = %s")
            params.append(process_duration)


        if not updates:
            return

        query = f"UPDATE document SET {', '.join(updates)} WHERE id = %s"
        params.append(doc_id)
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        print(f"[Parser-ERROR] 更新文档 {doc_id} 进度失败: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def split_markdown_to_chunks_smart(txt, chunk_token_num=256, min_chunk_tokens=10, enable_heading_in_content=False):
    """
    基于 markdown-it-py AST 的智能分块方法，解决 RAG Markdown 文件分块问题：
    1. 基于语义切分（使用 AST）
    2. 维护表格完整性，即使超出了最大 tokens
    3. 考虑 markdown 父子分块关系
    """
    if not MARKDOWN_IT_AVAILABLE:
        print("Warning: markdown-it-py not available, falling back to simple chunking")
        return split_markdown_to_chunks(txt, chunk_token_num)
    
    if not txt or not txt.strip():
        return []

    # 初始化 markdown-it 解析器
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(['table'])
    
    try:
        # 解析为 AST
        tokens = md.parse(txt)
        tree = SyntaxTreeNode(tokens)
        
        # 基于 AST 进行智能分块
        chunks = []
        current_chunk = []
        current_tokens = 0
        context_stack = []  # 维护标题层级栈
        
        for node in tree.children:
            node_type = node.type

            # 如果是标题节点，先完成前一个分块，再处理标题
            if node_type == "heading":
                # 1. 先完成前一个分块（使用旧的 context_stack）
                if current_chunk and current_tokens >= min_chunk_tokens:
                    chunk_content = _finalize_ast_chunk(current_chunk, context_stack, enable_heading_in_content)
                    if isinstance(chunk_content, dict) and chunk_content.get('content', '').strip():
                        chunks.append(chunk_content)
                    elif isinstance(chunk_content, str) and chunk_content.strip():
                        chunks.append(chunk_content)
                    current_chunk = []
                    current_tokens = 0

                # 2. 处理标题节点
                level = int(node.tag[1])
                title_text = _extract_text_from_node(node)

                # 3. 更新 context_stack（标题节点之后的内容都属于新的上下文）
                _update_context_stack(context_stack, level, title_text)

                # 4. 标题作为新分块的第一行
                chunk_data = node.markup + " " + title_text
                current_chunk.append(chunk_data)
                current_tokens = num_tokens_from_string(chunk_data)
            else:
                # 处理非标题节点
                chunk_data, _ = _process_non_heading_node(node, chunk_token_num)

                if chunk_data:
                    chunk_tokens = num_tokens_from_string(chunk_data)

                    # 检查是否需要分块（基于大小）
                    if (current_tokens + chunk_tokens > chunk_token_num and
                        current_chunk and current_tokens >= min_chunk_tokens):

                        chunk_content = _finalize_ast_chunk(current_chunk, context_stack, enable_heading_in_content)
                        if isinstance(chunk_content, dict) and chunk_content.get('content', '').strip():
                            chunks.append(chunk_content)
                        elif isinstance(chunk_content, str) and chunk_content.strip():
                            chunks.append(chunk_content)
                        current_chunk = []
                        current_tokens = 0

                    current_chunk.append(chunk_data)
                    current_tokens += chunk_tokens

        # 处理最后的块
        if current_chunk:
            chunk_content = _finalize_ast_chunk(current_chunk, context_stack, enable_heading_in_content)
            if isinstance(chunk_content, dict) and chunk_content.get('content', '').strip():
                chunks.append(chunk_content)
            elif isinstance(chunk_content, str) and chunk_content.strip():
                chunks.append(chunk_content)

        # 过滤空块并返回
        result = []
        for chunk in chunks:
            if isinstance(chunk, dict):
                if chunk.get('content', '').strip():
                    result.append(chunk)
            elif isinstance(chunk, str) and chunk.strip():
                result.append(chunk)
        return result
    
    except Exception as e:
        print(f"AST parsing failed: {e}, falling back to simple chunking")
        return split_markdown_to_chunks(txt, chunk_token_num)


def _process_non_heading_node(node, chunk_token_num):
    """
    处理非标题的 AST 节点

    Returns:
        tuple: (content, should_break)
    """
    node_type = node.type
    should_break = False
    content = ""

    if node_type == "table":
        # 表格处理 - 保持完整性
        content = _render_table_from_ast(node)
        table_tokens = num_tokens_from_string(content)
        
        # 表格过大时也要保持完整性
        if table_tokens > chunk_token_num:
            should_break = True
            
    elif node_type == "code_block":
        # 代码块处理
        content = f"```{node.info or ''}\n{node.content}```"
        
    elif node_type == "blockquote":
        # 引用块处理
        content = _render_blockquote_from_ast(node)
        
    elif node_type in ("list", "bullet_list", "ordered_list"):
        # 列表处理
        content = _render_list_from_ast(node)
        
    elif node_type == "paragraph":
        # 段落处理
        content = _extract_text_from_node(node)
        
    elif node_type == "hr":
        # 分隔符
        content = "---"
        should_break = True
        
    else:
        # 其他类型节点
        content = _extract_text_from_node(node)

    return content, should_break


def _update_context_stack(context_stack, level, title):
    """更新标题上下文栈"""
    # 移除比当前级别更深的标题
    while context_stack and context_stack[-1]['level'] >= level:
        context_stack.pop()
    
    # 添加当前标题
    context_stack.append({'level': level, 'title': title})


def _extract_text_from_node(node):
    """从 AST 节点提取文本内容"""
    if hasattr(node, 'content') and node.content:
        return node.content
    
    text_parts = []
    if hasattr(node, 'children') and node.children:
        for child in node.children:
            if child.type == "text":
                text_parts.append(child.content)
            elif child.type == "code_inline":
                text_parts.append(f"`{child.content}`")
            elif child.type == "strong":
                text_parts.append(f"**{_extract_text_from_node(child)}**")
            elif child.type == "em":
                text_parts.append(f"*{_extract_text_from_node(child)}*")
            elif child.type == "link":
                link_text = _extract_text_from_node(child)
                text_parts.append(f"[{link_text}]({child.attrGet('href') or ''})")
            else:
                text_parts.append(_extract_text_from_node(child))
    
    return "".join(text_parts)


def _render_table_from_ast(table_node):
    """从 AST 渲染表格为 HTML"""
    try:
        # 构建表格的 markdown 表示
        table_md = []
        
        for child in table_node.children:
            if child.type == "thead":
                # 表头处理
                for row in child.children:
                    if row.type == "tr":
                        cells = []
                        for cell in row.children:
                            if cell.type in ["th", "td"]:
                                cells.append(_extract_text_from_node(cell))
                        table_md.append("| " + " | ".join(cells) + " |")
                
                # 添加分隔符
                if table_md:
                    separator = "| " + " | ".join(["---"] * len(cells)) + " |"
                    table_md.append(separator)
                    
            elif child.type == "tbody":
                # 表体处理
                for row in child.children:
                    if row.type == "tr":
                        cells = []
                        for cell in row.children:
                            if cell.type in ["th", "td"]:
                                cells.append(_extract_text_from_node(cell))
                        table_md.append("| " + " | ".join(cells) + " |")
        
        # 转换为 HTML
        table_markdown = "\n".join(table_md)
        return md_to_html(table_markdown, extensions=['markdown.extensions.tables'])
        
    except Exception as e:
        print(f"Table rendering error: {e}")
        return _extract_text_from_node(table_node)


def _render_list_from_ast(list_node):
    """从 AST 渲染列表"""
    list_items = []
    list_type = list_node.attrGet('type') or 'bullet'
    
    for i, item in enumerate(list_node.children):
        if item.type == "list_item":
            item_content = _extract_text_from_node(item)
            if list_type == 'ordered':
                list_items.append(f"{i+1}. {item_content}")
            else:
                list_items.append(f"- {item_content}")
    
    return "\n".join(list_items)


def _render_blockquote_from_ast(blockquote_node):
    """从 AST 渲染引用块"""
    content = _extract_text_from_node(blockquote_node)
    lines = content.split('\n')
    return '\n'.join(f"> {line}" for line in lines)


def _finalize_ast_chunk(chunk_parts, context_stack, enable_heading_in_content=False):
    """完成基于 AST 的 chunk 格式化"""
    chunk_content = "\n\n".join(chunk_parts).strip()

    # 提取标题元数据
    headers = {item['level']: item['title'] for item in context_stack}

    # 调试日志
    logging.debug(f"_finalize_ast_chunk: enable_heading_in_content={enable_heading_in_content}, headers={headers}")

    # 如果启用了标题添加到内容，且有标题层级
    if enable_heading_in_content and headers:
        # 提取分块内容中已存在的标题文本（用于去重）
        existing_headings = set()  # 存储格式: "level:title"

        for line in chunk_content.split('\n'):
            line = line.strip()
            if line.startswith('#'):
                # 计算标题层级 (# = 1, ## = 2, ### = 3, ...)
                level = len(line) - len(line.lstrip('#'))
                if level > 0 and level <= 6:
                    # 提取标题文本（去除 # 和空格）
                    heading_text = line.lstrip('#').strip()
                    existing_headings.add(f"{level}:{heading_text}")

        # 添加 context_stack 中缺失的父级标题
        missing_heading_lines = []
        for level in sorted(headers.keys()):
            heading_key = f"{level}:{headers[level]}"
            # 如果这个标题不在分块内容中，才添加
            if heading_key not in existing_headings:
                heading_prefix = '#' * level
                missing_heading_lines.append(f"{heading_prefix} {headers[level]}")

        # 如果有缺失的父级标题，添加到内容前面
        if missing_heading_lines:
            missing_heading_text = '\n'.join(missing_heading_lines)
            chunk_content = f"{missing_heading_text}\n\n{chunk_content}"
            logging.debug(f"添加缺失的父级标题: {missing_heading_text}, 分块中已有标题: {existing_headings}")

    # 返回字典格式，包含标题元数据
    return {
        'content': chunk_content,
        'heading_metadata': {
            'headers': headers,
            'level': max(headers.keys()) if headers else 0
        }
    }


def split_markdown_to_chunks_title(txt, chunk_token_num=256, min_chunk_tokens=10,
                                   split_level=3, include_metadata=False, enable_heading_in_content=False):
    """
    基于标题层级的严格分块方法

    特点：
    1. 严格按照指定的标题级别分割（H1/H2/H3 等）
    2. 不进行大小控制（不合并小块，不分割大块）
    3. 保持标题层级上下文
    4. 适合结构清晰、标题规范的文档

    Args:
        txt: markdown 文本
        chunk_token_num: 目标分块 token 数（仅用于参考）
        min_chunk_tokens: 最小分块 token 数（仅用于参考）
        split_level: 分割的最大标题级别 (1-6), 默认3表示在H1/H2/H3处分割
        include_metadata: 是否包含元数据

    Returns:
        分块列表（字符串或字典）
    """
    if not MARKDOWN_IT_AVAILABLE:
        return split_markdown_to_chunks(txt, chunk_token_num)

    if not txt or not txt.strip():
        return []

    # 配置分割的标题级别
    headers_to_split_on = list(range(1, split_level + 1))  # [1, 2, 3] for split_level=3

    # 初始化 markdown-it 解析器
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(['table'])

    try:
        # 解析为 AST
        tokens = md.parse(txt)
        tree = SyntaxTreeNode(tokens)

        # 提取所有节点和标题信息
        nodes_with_headers = _extract_nodes_with_header_info(tree, headers_to_split_on)

        # 基于标题层级进行分块（严格分割，不做大小调整）
        chunks = _split_by_header_levels(nodes_with_headers, headers_to_split_on)

        # 生成最终分块内容（统一返回字典格式）
        final_chunks = []
        for chunk_info in chunks:
            content = _render_header_chunk(chunk_info)
            if content.strip():
                headers = chunk_info.get('headers', {})

                # 如果启用了标题添加到内容，且有标题层级
                if enable_heading_in_content and headers:
                    # 检查内容是否已经是标题
                    is_heading = content.strip().startswith('#')

                    # 如果内容本身不是标题，添加父级标题路径
                    if not is_heading:
                        # 生成 Markdown 标题格式
                        heading_lines = []
                        for level in sorted(headers.keys()):
                            heading_prefix = '#' * level
                            heading_lines.append(f"{heading_prefix} {headers[level]}")

                        heading_text = '\n'.join(heading_lines)
                        content = f"{heading_text}\n\n{content}"

                # 统一返回字典格式
                chunk_data = {
                    'content': content,
                    'heading_metadata': {
                        'headers': headers,
                        'level': max(headers.keys()) if headers else 0
                    }
                }
                final_chunks.append(chunk_data)

        return final_chunks

    except Exception as e:
        logging.error(f"Title-based chunking failed: {e}, falling back to smart chunking")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)


def split_markdown_to_chunks_advanced(txt, chunk_token_num=256, min_chunk_tokens=10,
                                     overlap_ratio=0.0, include_metadata=False):
    """
    基于标题层级的高级 Markdown 分块方法 (混合分块策略 + 动态阈值调整)
    
    核心特性：
    1. 保持标题作为主要分块边界
    2. 动态大小控制：目标300-600 tokens，最大800 tokens，最小50 tokens  
    3. 处理超大分块：在段落边界进一步分割
    4. 处理超小分块：与相邻分块合并
    5. 特殊内容处理：保持表格、代码块、公式完整性
    6. 智能上下文增强
    """
    if not MARKDOWN_IT_AVAILABLE:
        return split_markdown_to_chunks(txt, chunk_token_num)
    
    if not txt or not txt.strip():
        return []

    # 动态阈值配置
    target_min_tokens = max(50, min_chunk_tokens // 2)  # 最小50 tokens
    target_tokens = min(600, chunk_token_num)  # 目标大小：300-600 tokens
    target_max_tokens = min(800, chunk_token_num * 1.5)  # 最大800 tokens
    
    # 配置要作为分块边界的标题级别
    headers_to_split_on = [1, 2, 3]  # H1, H2, H3 作为分块边界
    
    # 初始化 markdown-it 解析器
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(['table'])
    
    try:
        # 解析为 AST
        tokens = md.parse(txt)
        tree = SyntaxTreeNode(tokens)
        
        # 提取所有节点和标题信息
        nodes_with_headers = _extract_nodes_with_header_info(tree, headers_to_split_on)
        
        # 基于标题层级进行初步分块
        initial_chunks = _split_by_header_levels(nodes_with_headers, headers_to_split_on)
        
        # 应用动态大小控制和优化
        optimized_chunks = _apply_size_control_and_optimization(
            initial_chunks, target_min_tokens, target_tokens, target_max_tokens
        )
        
        # 生成最终分块内容
        final_chunks = []
        for chunk_info in optimized_chunks:
            content = _render_header_chunk_advanced(chunk_info)
            if content.strip():
                if include_metadata:
                    chunk_data = {
                        'content': content,
                        'metadata': chunk_info.get('headers', {}),
                        'token_count': num_tokens_from_string(content),
                        'chunk_type': chunk_info.get('chunk_type', 'header_based'),
                        'has_special_content': chunk_info.get('has_special_content', False),
                        'source_sections': chunk_info.get('source_sections', 1)
                    }
                    final_chunks.append(chunk_data)
                else:
                    final_chunks.append(content)
        
        return final_chunks
    
    except Exception as e:
        print(f"Advanced header-based parsing failed: {e}, falling back to smart chunking")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)


def _apply_size_control_and_optimization(chunks, min_tokens, target_tokens, max_tokens):
    """应用动态大小控制和优化策略"""
    optimized_chunks = []
    
    i = 0
    while i < len(chunks):
        chunk = chunks[i]
        chunk_content = _render_header_chunk(chunk)
        chunk_tokens = num_tokens_from_string(chunk_content)
        
        # 检查特殊内容类型
        has_special_content = _has_special_content(chunk)
        
        if chunk_tokens <= max_tokens and chunk_tokens >= min_tokens:
            # 大小合适，直接添加
            chunk['chunk_type'] = 'normal'
            chunk['has_special_content'] = has_special_content
            optimized_chunks.append(chunk)
            
        elif chunk_tokens > max_tokens and not has_special_content:
            # 超大分块，需要进一步分割（除非包含特殊内容）
            split_chunks = _split_oversized_chunk(chunk, target_tokens, max_tokens)
            optimized_chunks.extend(split_chunks)
            
        elif chunk_tokens < min_tokens:
            # 超小分块，尝试与下一个分块合并
            merged_chunk = _try_merge_with_next(chunk, chunks, i, target_tokens)
            if merged_chunk:
                optimized_chunks.append(merged_chunk)
                # 跳过被合并的分块
                i += merged_chunk.get('merged_count', 1) - 1
            else:
                # 无法合并，添加上下文增强
                enhanced_chunk = _enhance_small_chunk_with_context(chunk)
                optimized_chunks.append(enhanced_chunk)
        else:
            # 包含特殊内容的超大分块，保持完整性但添加标记
            chunk['chunk_type'] = 'oversized_special'
            chunk['has_special_content'] = has_special_content
            optimized_chunks.append(chunk)
        
        i += 1
    
    return optimized_chunks


def _has_special_content(chunk):
    """检查分块是否包含特殊内容（表格、代码块、公式等）"""
    for node_info in chunk.get('nodes', []):
        node_type = node_info.get('type', '')
        content = node_info.get('content', '')
        
        # 检查特殊内容类型
        if node_type in ['table', 'code_block']:
            return True
        
        # 检查数学公式
        if '$$' in content or '$' in content:
            return True
            
        # 检查HTML表格
        if '<table>' in content and '</table>' in content:
            return True
            
    return False


def _split_oversized_chunk(chunk, target_tokens, max_tokens):
    """分割超大分块，在段落边界进行分割"""
    split_chunks = []
    nodes = chunk.get('nodes', [])
    headers = chunk.get('headers', {})
    
    current_nodes = []
    current_tokens = 0
    
    for node_info in nodes:
        node_content = node_info.get('content', '')
        node_tokens = num_tokens_from_string(node_content)
        
        # 检查是否是标题节点
        is_heading = node_info.get('type') == 'heading'
        
        # 如果当前节点会导致超出目标大小，且当前已有内容
        if current_tokens + node_tokens > target_tokens and current_nodes:
            # 创建一个分块
            new_chunk = {
                'headers': headers.copy(),
                'nodes': current_nodes.copy(),
                'chunk_type': 'split_from_oversized',
                'has_special_content': any(_has_special_content({'nodes': [n]}) for n in current_nodes)
            }
            split_chunks.append(new_chunk)
            
            # 开始新分块
            current_nodes = [node_info]
            current_tokens = node_tokens
            
            # 如果是标题，更新headers上下文
            if is_heading:
                level = node_info.get('level', 3)
                title = node_info.get('title', '')
                new_headers = {k: v for k, v in headers.items() if k < level}
                new_headers[level] = title
                headers = new_headers
        else:
            current_nodes.append(node_info)
            current_tokens += node_tokens
            
            # 更新标题上下文
            if is_heading:
                level = node_info.get('level', 3)
                title = node_info.get('title', '')
                headers = {k: v for k, v in headers.items() if k < level}
                headers[level] = title
    
    # 添加最后一个分块
    if current_nodes:
        final_chunk = {
            'headers': headers.copy(),
            'nodes': current_nodes,
            'chunk_type': 'split_from_oversized',
            'has_special_content': any(_has_special_content({'nodes': [n]}) for n in current_nodes)
        }
        split_chunks.append(final_chunk)
    
    return split_chunks


def _try_merge_with_next(current_chunk, all_chunks, current_index, target_tokens):
    """尝试将小分块与后续分块合并"""
    if current_index >= len(all_chunks) - 1:
        return None
    
    next_chunk = all_chunks[current_index + 1]
    
    # 计算合并后的大小
    current_content = _render_header_chunk(current_chunk)
    next_content = _render_header_chunk(next_chunk)
    merged_tokens = num_tokens_from_string(current_content + "\n\n" + next_content)
    
    # 如果合并后大小合适
    if merged_tokens <= target_tokens * 1.2:  # 允许轻微超出目标大小
        merged_chunk = {
            'headers': next_chunk.get('headers', current_chunk.get('headers', {})),
            'nodes': current_chunk.get('nodes', []) + next_chunk.get('nodes', []),
            'chunk_type': 'merged_small',
            'has_special_content': (_has_special_content(current_chunk) or 
                                  _has_special_content(next_chunk)),
            'merged_count': 2,
            'source_sections': 2
        }
        return merged_chunk
    
    return None


def _enhance_small_chunk_with_context(chunk):
    """为小分块增强上下文信息"""
    enhanced_chunk = chunk.copy()
    enhanced_chunk['chunk_type'] = 'small_enhanced'
    enhanced_chunk['has_special_content'] = _has_special_content(chunk)
    
    # 确保包含足够的标题上下文
    headers = chunk.get('headers', {})
    if headers:
        # 添加完整的标题路径作为上下文
        context_parts = []
        for level in sorted(headers.keys()):
            context_parts.append(f"{'#' * level} {headers[level]}")
        
        # 在节点前添加上下文信息
        if context_parts:
            context_node = {
                'type': 'context',
                'content': '\n'.join(context_parts),
                'headers': headers.copy(),
                'is_split_boundary': False
            }
            enhanced_chunk['nodes'] = [context_node] + enhanced_chunk.get('nodes', [])
    
    return enhanced_chunk


def _render_header_chunk_advanced(chunk_info):
    """高级渲染基于标题的分块内容，包含更好的格式化"""
    content_parts = []
    
    # 处理标题上下文
    chunk_has_header = any(node['type'] == 'heading' for node in chunk_info.get('nodes', []))
    headers = chunk_info.get('headers', {})
    
    # 为某些类型的分块添加标题上下文
    chunk_type = chunk_info.get('chunk_type', 'normal')
    if chunk_type in ['split_from_oversized', 'small_enhanced'] and headers and not chunk_has_header:
        # 添加最相关的上下文标题
        context_header = _get_most_relevant_header_advanced(headers, chunk_type)
        if context_header:
            content_parts.append(context_header)
    
    # 渲染所有节点内容（移除标记，保持内容干净）
    for node_info in chunk_info.get('nodes', []):
        if node_info.get('content', '').strip():
            content = node_info['content']
            # 直接使用原始内容，不添加任何标记
            content_parts.append(content)
    
    result = "\n\n".join(content_parts).strip()
    
    # 移除重叠分块的标识，保持内容干净
    # if chunk_type == 'overlap':
    #     result = f"[上下文关联内容]\n{result}"
    
    return result


def _get_most_relevant_header_advanced(headers, chunk_type):
    """获取最相关的上下文标题（高级版本）"""
    if not headers:
        return None
    
    # 根据分块类型选择不同的上下文策略
    if chunk_type == 'split_from_oversized':
        # 分割分块：显示最深层级的标题
        max_level = max(headers.keys())
        return f"{'#' * max_level} {headers[max_level]}"
    
    elif chunk_type in ['small_enhanced']:
        # 增强分块：显示最相关的标题
        max_level = max(headers.keys())
        return f"{'#' * max_level} {headers[max_level]}"
    
    else:
        # 普通分块：显示最相关的标题
        max_level = max(headers.keys())
        return f"{'#' * max_level} {headers[max_level]}"


def optimize_chunks_for_rag(chunks, target_vector_dim=1536):
    """
    基础RAG分块优化，为向量化做准备
    """
    optimized_chunks = []
    
    for chunk_data in chunks:
        if isinstance(chunk_data, str):
            chunk_data = {'content': chunk_data, 'token_count': num_tokens_from_string(chunk_data)}
        
        optimized_chunks.append(chunk_data)
    
    return optimized_chunks

def _extract_nodes_with_header_info(tree, headers_to_split_on):
    """提取所有节点及其对应的标题信息"""
    nodes_with_headers = []
    current_headers = {}  # 当前的标题层级路径
    
    for node in tree.children:
        if node.type == "heading":
            level = int(node.tag[1])  # h1 -> 1, h2 -> 2, etc.
            title = _extract_text_from_node(node)
            
            # 更新当前标题路径
            # 移除比当前级别更深的标题
            current_headers = {k: v for k, v in current_headers.items() if k < level}
            # 添加当前标题
            current_headers[level] = title
            
            # 如果是分块边界标题，标记为分块起始点
            is_split_boundary = level in headers_to_split_on
            
            nodes_with_headers.append({
                'node': node,
                'type': 'heading',
                'level': level,
                'title': title,
                'headers': current_headers.copy(),
                'is_split_boundary': is_split_boundary,
                'content': node.markup + " " + title
            })
        else:
            # 非标题节点
            content = _render_node_content(node)
            if content.strip():
                nodes_with_headers.append({
                    'node': node,
                    'type': node.type,
                    'headers': current_headers.copy(),
                    'is_split_boundary': False,
                    'content': content
                })
    
    return nodes_with_headers


def _render_node_content(node):
    """渲染单个节点的内容"""
    if node.type == "heading":
        # 修复：保留标题的markdown格式，与smart分块保持一致
        title_text = _extract_text_from_node(node)
        return node.markup + " " + title_text
    elif node.type == "table":
        return _render_table_from_ast(node)
    elif node.type == "code_block":
        return f"```{node.info or ''}\n{node.content}```"
    elif node.type == "blockquote":
        return _render_blockquote_from_ast(node)
    elif node.type in ["bullet_list", "ordered_list"]:
        return _render_list_from_ast(node)
    elif node.type == "paragraph":
        return _extract_text_from_node(node)
    elif node.type == "hr":
        return "---"
    else:
        return _extract_text_from_node(node)


def _split_by_header_levels(nodes_with_headers, headers_to_split_on):
    """基于标题层级进行分块，智能处理连续标题"""
    chunks = []
    current_chunk = {
        'headers': {},
        'nodes': []
    }
    
    i = 0
    while i < len(nodes_with_headers):
        node_info = nodes_with_headers[i]
        
        # 检查是否为分块边界标题
        if node_info['is_split_boundary']:
            # 处理连续标题的情况
            if node_info['type'] == 'heading':
                # 查看后续是否还有连续标题或者是否直到内容出现
                has_following_content = False

                # 检查后续节点
                j = i + 1
                while j < len(nodes_with_headers):
                    next_node = nodes_with_headers[j]
                    # 如果是标题，继续查找
                    if next_node.get('type') == 'heading':
                        j += 1
                        continue
                    # 如果找到非标题内容
                    if next_node.get('content', '').strip():
                        has_following_content = True
                        break
                    j += 1

                # 如果后续没有内容（只有连续标题），不作为分块边界
                if not has_following_content:
                    # 直接添加到当前块
                    current_chunk['nodes'].append(node_info)
                    # 更新当前块的标题信息
                    if node_info['headers']:
                        current_chunk['headers'] = node_info['headers'].copy()
                    i += 1
                    continue
            
            # 正常的分块边界处理
            # 完成当前块（如果有内容）
            if (current_chunk['nodes'] and 
                any(n for n in current_chunk['nodes'] if n['content'].strip())):
                chunks.append(current_chunk)
                current_chunk = {
                    'headers': {},
                    'nodes': []
                }
        
        # 更新当前块的标题信息
        if node_info['headers']:
            current_chunk['headers'] = node_info['headers'].copy()
        
        # 添加节点到当前块
        current_chunk['nodes'].append(node_info)
        i += 1
    
    # 添加最后一个块
    if current_chunk['nodes'] and any(n for n in current_chunk['nodes'] if n['content'].strip()):
        chunks.append(current_chunk)
    
    return chunks


def _render_header_chunk(chunk_info):
    """渲染基于标题的分块内容（原始版本，用于兼容性）"""
    content_parts = []
    
    # 添加标题上下文（如果分块本身不包含标题）
    chunk_has_header = any(node['type'] == 'heading' for node in chunk_info.get('nodes', []))
    
    if not chunk_has_header and chunk_info.get('headers'):
        # 添加最相关的上下文标题
        context_header = _get_most_relevant_header(chunk_info['headers'])
        if context_header:
            content_parts.append(context_header)
    
    # 渲染所有节点内容
    for node_info in chunk_info.get('nodes', []):
        if node_info.get('content', '').strip():
            content_parts.append(node_info['content'])
    
    return "\n\n".join(content_parts).strip()


def _get_most_relevant_header(headers):
    """获取最相关的上下文标题（原始版本）"""
    if not headers:
        return None
    
    # 选择最深层级的标题作为上下文
    max_level = max(headers.keys())
    return f"{'#' * max_level} {headers[max_level]}"


def split_markdown_to_chunks_strict_regex(txt, chunk_token_num=256, min_chunk_tokens=10, regex_pattern=''):
    """
    使用自定义正则表达式进行严格分块
    
    Args:
        txt: 要分块的文本
        chunk_token_num: 目标分块大小（tokens）
        min_chunk_tokens: 最小分块大小（tokens）
        regex_pattern: 自定义正则表达式
        
    Returns:
        分块列表
    """
    if not txt or not txt.strip():
        return []
    
    if not regex_pattern or not regex_pattern.strip():
        logger.warning("正则表达式为空，回退到智能分块")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)

    try:
        
        # 使用更精确的方法：逐行处理，确保每个匹配都开始新分块
        # 优化正则表达式，只匹配行开头或前面只有空格的条文
        precise_pattern = r'^\s*' + regex_pattern
        
        lines = txt.split('\n')
        chunks = []
        current_chunk = []
        
        for line in lines:
            # 检查当前行是否以正则表达式匹配开始（真正的条文开始）
            if re.search(precise_pattern, line) and current_chunk:
                # 如果当前行包含匹配且当前已有内容，先保存当前分块
                chunk_content = '\n'.join(current_chunk).strip()
                if chunk_content:
                    chunks.append(chunk_content)
                
                # 开始新分块
                current_chunk = [line]
            else:
                # 将当前行添加到当前分块
                current_chunk.append(line)
        
        # 添加最后一个分块
        if current_chunk:
            chunk_content = '\n'.join(current_chunk).strip()
            if chunk_content:
                chunks.append(chunk_content)
        
        # 过滤和统计
        final_chunks = [chunk for chunk in chunks if chunk.strip()]
        return final_chunks

    except re.error as e:
        logger.error(f"正则分块失败，正则表达式错误: {e}，回退到智能分块")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)
    except Exception as e:
        logger.error(f"正则分块发生异常: {e}，回退到智能分块")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)


def _get_es_connection():
    """获取 Elasticsearch 连接"""
    from elasticsearch import Elasticsearch

    es_host = os.getenv('ES_HOST', 'es01')
    es_port = int(os.getenv('ES_PORT', 1200))
    es_password = os.getenv('ELASTIC_PASSWORD', 'infini_rag_flow')

    return Elasticsearch(
        [f"http://{es_host}:{es_port}"],
        basic_auth=("elastic", es_password),
        request_timeout=30
    )


def _get_mysql_connection():
    """获取 MySQL 连接"""
    mysql_host = os.getenv('MYSQL_HOST', 'mysql')
    mysql_port = int(os.getenv('MYSQL_PORT', 3306))
    mysql_user = os.getenv('MYSQL_USER', 'root')
    mysql_password = os.getenv('MYSQL_PASSWORD', 'infini_rag_flow')
    mysql_db = os.getenv('MYSQL_DBNAME', 'rag_flow')

    return mysql.connector.connect(
        host=mysql_host,
        port=mysql_port,
        user=mysql_user,
        password=mysql_password,
        database=mysql_db
    )


def _save_parent_chunks_to_es(parent_chunks, kb_id, doc_id, tenant_id):
    """
    批量保存父块到 RAGFlow ES ragflow_{tenant_id}_parent 索引

    Args:
        parent_chunks: 父块列表 [ASTChunkInfo, ...]
        kb_id: 知识库ID
        doc_id: 文档ID
        tenant_id: 租户ID
    """
    if not parent_chunks:
        return

    try:
        from datetime import datetime
        from elasticsearch.helpers import bulk

        es = _get_es_connection()
        parent_index = f"ragflow_{tenant_id}_parent"
        now = datetime.now()
        create_time = now.strftime("%Y-%m-%d %H:%M:%S")
        create_timestamp = now.timestamp()

        # 批量准备文档
        actions = []
        for parent_chunk in parent_chunks:
            if not parent_chunk.id or not parent_chunk.content:
                continue

            actions.append({
                "_index": parent_index,
                "_id": parent_chunk.id,
                "_source": {
                    "id": parent_chunk.id,
                    "doc_id": doc_id,
                    "kb_id": kb_id,
                    "content_with_weight": parent_chunk.content,
                    "create_time": create_time,
                    "create_timestamp_flt": create_timestamp,
                }
            })

        # 批量索引
        if actions:
            success, failed = bulk(es, actions, refresh=False, raise_on_error=False)
            logging.info(f"Saved {success}/{len(actions)} parent chunks to ES index {parent_index}")
            if failed:
                logging.warning(f"Failed to save {len(failed)} parent chunks")

    except Exception as e:
        logging.exception(f"Failed to save parent chunks to ES: {e}")
        raise


def _save_parent_child_mappings(relationships, kb_id, doc_id):
    """
    批量保存父子映射关系到 RAGFlow MySQL parent_child_mapping 表

    Args:
        relationships: 映射关系列表 [{"parent_id": ..., "child_id": ...}, ...]
        kb_id: 知识库ID
        doc_id: 文档ID
    """
    if not relationships:
        return

    try:
        from datetime import datetime

        conn = _get_mysql_connection()
        cursor = conn.cursor()

        # 批量准备数据
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values = []
        for relationship in relationships:
            parent_id = relationship.get('parent_id', '')
            child_id = relationship.get('child_id', '')

            if not parent_id or not child_id:
                continue

            values.append((parent_id, child_id, doc_id, kb_id, 100, now, now))

        # 批量插入
        if values:
            sql = """
                INSERT IGNORE INTO parent_child_mapping
                (parent_chunk_id, child_chunk_id, doc_id, kb_id, relevance_score, create_time, update_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.executemany(sql, values)
            conn.commit()
            logging.info(f"Saved {len(values)} parent-child relationships to MySQL")

        cursor.close()
        conn.close()

    except Exception as e:
        logging.exception(f"Failed to save parent-child mappings to MySQL: {e}")
        raise


def _write_parent_child_debug_file(parent_chunks, child_chunks, relationships, doc_id, kb_id, tenant_id):
    """
    在 dev_mode 下输出父子分块调试日志

    Args:
        parent_chunks: 父块列表
        child_chunks: 子块列表
        relationships: 父子关系列表
        doc_id: 文档ID
        kb_id: 知识库ID
        tenant_id: 租户ID
    """
    try:
        # 创建调试日志目录
        log_dir = "/tmp/knowflow_chunk_logs"
        os.makedirs(log_dir, exist_ok=True)

        # 生成日志文件名（包含时间戳和doc_id）
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"parent_child_debug_{doc_id}_{timestamp}.txt")

        with open(log_file, 'w', encoding='utf-8') as f:
            # 1. 基本信息
            f.write("=" * 80 + "\n")
            f.write("父子分块调试日志\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"文档ID: {doc_id}\n")
            f.write(f"知识库ID: {kb_id}\n")
            f.write(f"租户ID: {tenant_id}\n")
            f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"父块数量: {len(parent_chunks)}\n")
            f.write(f"子块数量: {len(child_chunks)}\n")
            f.write(f"映射关系数量: {len(relationships)}\n")
            f.write("\n")

            # 2. 父块详情
            f.write("=" * 80 + "\n")
            f.write("父块详情\n")
            f.write("=" * 80 + "\n\n")
            for idx, parent in enumerate(parent_chunks):
                f.write(f"[父块 #{idx + 1}]\n")
                f.write(f"  ID: {parent.id}\n")
                f.write(f"  顺序: {parent.order}\n")
                f.write(f"  行号范围: {parent.start_line} - {parent.end_line}\n")
                f.write(f"  Token数: {num_tokens_from_string(parent.content)}\n")
                f.write(f"  元数据: {parent.metadata}\n")
                f.write(f"  内容:\n")
                f.write("-" * 60 + "\n")
                f.write(parent.content[:500] + ("..." if len(parent.content) > 500 else "") + "\n")
                f.write("-" * 60 + "\n\n")

            # 3. 子块详情
            f.write("=" * 80 + "\n")
            f.write("子块详情\n")
            f.write("=" * 80 + "\n\n")
            for idx, child in enumerate(child_chunks):
                f.write(f"[子块 #{idx + 1}]\n")
                f.write(f"  ID: {child.id}\n")
                f.write(f"  顺序: {child.order}\n")
                f.write(f"  行号范围: {child.start_line} - {child.end_line}\n")
                f.write(f"  Token数: {num_tokens_from_string(child.content)}\n")
                f.write(f"  元数据: {child.metadata}\n")
                f.write(f"  内容:\n")
                f.write("-" * 60 + "\n")
                f.write(child.content[:500] + ("..." if len(child.content) > 500 else "") + "\n")
                f.write("-" * 60 + "\n\n")

            # 4. 父子关系映射
            f.write("=" * 80 + "\n")
            f.write("父子关系映射\n")
            f.write("=" * 80 + "\n\n")

            # 创建映射字典便于查找
            child_to_parent = {rel.get('child_id', ''): rel.get('parent_id', '')
                              for rel in relationships}

            # 按子块顺序显示映射
            for idx, child in enumerate(child_chunks):
                parent_id = child_to_parent.get(child.id, '未找到映射')

                # 查找父块顺序
                parent_order = "N/A"
                for p_idx, parent in enumerate(parent_chunks):
                    if parent.id == parent_id:
                        parent_order = p_idx + 1
                        break

                f.write(f"[映射 #{idx + 1}]\n")
                f.write(f"  子块ID: {child.id}\n")
                f.write(f"  子块顺序: {idx + 1}\n")
                f.write(f"  子块行范围: {child.start_line} - {child.end_line}\n")
                f.write(f"  ↓\n")
                f.write(f"  父块ID: {parent_id}\n")
                f.write(f"  父块顺序: {parent_order}\n")

                if parent_id != '未找到映射':
                    # 查找父块行范围
                    for parent in parent_chunks:
                        if parent.id == parent_id:
                            f.write(f"  父块行范围: {parent.start_line} - {parent.end_line}\n")
                            break

                f.write("\n")

            # 5. 统计信息
            f.write("=" * 80 + "\n")
            f.write("统计信息\n")
            f.write("=" * 80 + "\n\n")

            mapped_count = len([c for c in child_chunks if c.id in child_to_parent])
            unmapped_count = len(child_chunks) - mapped_count

            f.write(f"成功映射的子块数: {mapped_count}/{len(child_chunks)}\n")
            f.write(f"未映射的子块数: {unmapped_count}\n")

            if unmapped_count > 0:
                f.write("\n未映射的子块:\n")
                for child in child_chunks:
                    if child.id not in child_to_parent:
                        f.write(f"  - {child.id} (行 {child.start_line}-{child.end_line})\n")

            f.write("\n")

        logging.info(f"[DEV_MODE] 父子分块调试日志已保存: {log_file}")

    except Exception as e:
        logging.warning(f"[DEV_MODE] 写入父子分块调试日志失败: {e}")


def split_markdown_to_chunks_parent_child(txt, chunk_token_num=256, min_chunk_tokens=10,
                                         parent_config=None, doc_id='unknown', kb_id='unknown', tenant_id='unknown',
                                         enable_heading_in_content=False):
    """
    端到端的父子分块方法 - 生成真实ID、保存父块和映射关系

    Args:
        txt: 要分块的文本
        chunk_token_num: 子分块大小（tokens）
        min_chunk_tokens: 最小子分块大小
        parent_config: 父分块配置
        doc_id: 文档ID
        kb_id: 知识库ID
        tenant_id: 租户ID

    Returns:
        list: 子分块字典列表 [{"content": str, "id": str}, ...]

    Note:
        在 KnowFlow Server 端完成所有父子分块处理：
        1. AST 创建父块和子块
        2. 使用 RAGFlow 的 ID 生成规则（xxhash）
        3. 保存父块到 ES ragflow_{tenant_id}_parent
        4. 保存映射关系到 MySQL
        5. 返回带真实 ID 的子块
    """
    if not txt or not txt.strip():
        return []

    parent_config = parent_config or {}

    try:
        # 1. 调用本地AST父子分块函数（生成临时ID）
        parent_chunks, child_chunks, relationships = split_markdown_to_chunks_ast_parent_child(
            txt=txt,
            chunk_token_num=chunk_token_num,
            min_chunk_tokens=min_chunk_tokens,
            parent_config=parent_config,
            doc_id=doc_id,
            kb_id=kb_id
        )

        logging.info(f"AST 父子分块完成: {len(parent_chunks)} 父块, {len(child_chunks)} 子块")

        # 2. 为子块和父块生成真实 ID（使用 RAGFlow 的 xxhash 规则）
        temp_to_real_id = {}  # 临时ID → 真实ID 映射

        # 子块 ID: xxhash(content + doc_id)
        for child in child_chunks:
            real_id = xxhash.xxh64((child.content + doc_id).encode("utf-8", "surrogatepass")).hexdigest()
            temp_to_real_id[child.id] = real_id
            child.id = real_id

        # 父块 ID: {doc_id}_parent_{序号}_{hash[:8]}
        for i, parent in enumerate(parent_chunks):
            real_id = f"{doc_id}_parent_{i:04d}_{xxhash.xxh64(parent.content.encode('utf-8')).hexdigest()[:8]}"
            temp_to_real_id[parent.id] = real_id
            parent.id = real_id

        logging.info(f"ID 生成完成: {len(child_chunks)} 子块, {len(parent_chunks)} 父块")

        # 3. 更新映射关系使用真实 ID
        updated_relationships = [
            {
                'parent_id': temp_to_real_id.get(rel.get('parent_chunk_id', rel.get('parent_id', '')), ''),
                'child_id': temp_to_real_id.get(rel.get('child_chunk_id', rel.get('child_id', '')), '')
            }
            for rel in relationships
        ]

        # 4. 保存父块到 ES 和映射关系到 MySQL
        _save_parent_chunks_to_es(parent_chunks, kb_id, doc_id, tenant_id)
        _save_parent_child_mappings(updated_relationships, kb_id, doc_id)

        # 5. 【DEV_MODE】输出调试日志
        if is_dev_mode():
            _write_parent_child_debug_file(
                parent_chunks, child_chunks, updated_relationships,
                doc_id, kb_id, tenant_id
            )

        # 6. 返回子块（带真实 ID，并处理标题添加到内容）
        result = []
        for chunk in child_chunks:
            # 提取标题元数据
            context_stack = chunk.metadata.get('context_stack', [])
            headers = {item['level']: item['title'] for item in context_stack}

            chunk_content = chunk.content

            # 如果启用了标题添加到内容，且有标题层级
            if enable_heading_in_content and headers:
                # 检查内容是否已经是标题
                is_heading = chunk_content.strip().startswith('#')

                # 如果内容本身不是标题，添加父级标题路径
                if not is_heading:
                    # 生成 Markdown 标题格式
                    heading_lines = []
                    for level in sorted(headers.keys()):
                        heading_prefix = '#' * level
                        heading_lines.append(f"{heading_prefix} {headers[level]}")

                    heading_text = '\n'.join(heading_lines)
                    chunk_content = f"{heading_text}\n\n{chunk_content}"

            chunk_dict = {
                "content": chunk_content,
                "id": chunk.id,
                "heading_metadata": {
                    'headers': headers,
                    'level': max(headers.keys()) if headers else 0
                }
            }
            result.append(chunk_dict)

        logging.info(f"父子分块完成: 返回 {len(result)} 个子块")
        return result

    except Exception as e:
        logging.exception(f"父子分块失败: {e}，回退到智能分块")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)


# _save_parent_child_chunks_to_db 函数已移至 RAGFlow API 层处理


# 全局变量存储最后一次父子分块结果
_last_parent_child_result = None


def get_last_parent_child_result():
    """获取最后一次父子分块的完整结果"""
    global _last_parent_child_result
    return _last_parent_child_result


# ===== 基于AST的父子分块实现 =====

class ASTChunkInfo:
    """基于AST的分块信息类"""
    def __init__(self, id, content, start_line, end_line, order, doc_id='', metadata=None, ast_nodes=None):
        self.id = id
        self.content = content
        self.start_line = start_line
        self.end_line = end_line
        self.order = order
        self.doc_id = doc_id
        self.metadata = metadata or {}
        self.ast_nodes = ast_nodes or []
        
        # AST特有信息
        self.section_title = metadata.get('section_title', '')
        self.context_stack = metadata.get('context_stack', [])
        self.semantic_elements = metadata.get('semantic_elements', {})


def split_markdown_to_chunks_ast_parent_child(txt, chunk_token_num=256, min_chunk_tokens=10, 
                                             parent_config=None, doc_id='unknown', kb_id='unknown'):
    """
    基于AST的父子分块方法
    
    Args:
        txt: 要分块的文本
        chunk_token_num: 子分块大小（tokens）
        min_chunk_tokens: 最小子分块大小
        parent_config: 父分块配置
        doc_id: 文档ID
        kb_id: 知识库ID
        
    Returns:
        tuple: (parent_chunks, child_chunks, relationships)
    """
    if not MARKDOWN_IT_AVAILABLE:
        print("Warning: markdown-it-py not available, falling back to simple parent-child")
        # 回退到现有的父子分块实现
        from api.apps.chunk_app import parent_child_split
        return parent_child_split()
    
    if not txt or not txt.strip():
        return [], [], []
    
    parent_config = parent_config or {}
    parent_split_level = parent_config.get('parent_split_level', 2)  # 默认H2分割
    
    try:
        # 1. 解析AST并创建增强节点
        enhanced_nodes = _create_enhanced_ast_nodes(txt)
        
        # 2. 基于AST创建子分块
        child_chunks = _create_ast_child_chunks(
            enhanced_nodes, chunk_token_num, min_chunk_tokens, doc_id
        )
        
        # 3. 基于AST和标题层级创建父分块  
        parent_chunks = _create_ast_parent_chunks(
            enhanced_nodes, parent_split_level, doc_id
        )
        
        # 4. 建立精确的AST关联关系
        relationships = _create_ast_relationships(
            child_chunks, parent_chunks, enhanced_nodes, doc_id, kb_id
        )

        return parent_chunks, child_chunks, relationships

    except Exception as e:
        logger.error(f"AST父子分块失败: {e}")
        import traceback
        traceback.print_exc()
        return [], [], []


def _create_enhanced_ast_nodes(txt):
    """创建增强的AST节点信息"""
    from markdown_it import MarkdownIt
    from markdown_it.tree import SyntaxTreeNode
    
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(['table'])
    
    tokens = md.parse(txt)
    tree = SyntaxTreeNode(tokens)
    
    enhanced_nodes = []
    context_stack = []  # 标题上下文栈
    line_offset = 0
    
    for node in tree.children:
        node_info = _create_enhanced_node_info(node, context_stack, line_offset)
        if node_info['content'].strip():  # 只保留有内容的节点
            enhanced_nodes.append(node_info)
        line_offset = node_info['line_end']
    
    return enhanced_nodes


def _create_enhanced_node_info(node, context_stack, line_offset):
    """为AST节点创建增强信息"""
    content = _render_node_content(node)  # 复用现有函数
    
    # 估算行号（markdown-it-py的map信息可能不准确）
    content_lines = content.count('\n') + 1 if content.strip() else 0
    line_start = line_offset
    line_end = line_offset + content_lines
    
    node_info = {
        'node': node,
        'type': node.type,
        'content': content,
        'line_start': line_start,
        'line_end': line_end,
        'context_stack': [c.copy() for c in context_stack],  # 深拷贝上下文
        'is_section_boundary': False,
        'header_level': None,
        'header_title': None
    }
    
    # 处理标题节点
    if node.type == "heading":
        level = int(node.tag[1]) if hasattr(node, 'tag') and node.tag else 1
        title = _extract_text_from_node(node)
        
        # 更新上下文栈
        _update_context_stack(context_stack, level, title)
        
        node_info.update({
            'header_level': level,
            'header_title': title,
            'is_section_boundary': True,
            'context_stack': [c.copy() for c in context_stack]  # 更新后的上下文
        })
    
    return node_info


def _create_ast_child_chunks(enhanced_nodes, chunk_token_num, min_chunk_tokens, doc_id):
    """基于AST节点创建子分块"""
    child_chunks = []
    current_chunk_nodes = []
    current_tokens = 0
    chunk_order = 0
    
    for node_info in enhanced_nodes:
        content = node_info['content']
        if not content.strip():
            continue
            
        content_tokens = num_tokens_from_string(content)
        
        # 检查是否需要分块
        should_break = (
            node_info['type'] == 'heading' and 
            node_info.get('header_level', 99) <= 3  # H1, H2, H3作为分块边界
        )
        
        if should_break and current_chunk_nodes and current_tokens >= min_chunk_tokens:
            # 创建子分块
            child_chunk = _create_ast_child_chunk_obj(
                current_chunk_nodes, chunk_order, doc_id
            )
            child_chunks.append(child_chunk)
            chunk_order += 1
            current_chunk_nodes = []
            current_tokens = 0
        
        # 检查token限制
        if (current_tokens + content_tokens > chunk_token_num and 
            current_chunk_nodes and current_tokens >= min_chunk_tokens):
            
            child_chunk = _create_ast_child_chunk_obj(
                current_chunk_nodes, chunk_order, doc_id
            )
            child_chunks.append(child_chunk)
            chunk_order += 1
            current_chunk_nodes = []
            current_tokens = 0
        
        current_chunk_nodes.append(node_info)
        current_tokens += content_tokens
    
    # 处理最后一个分块
    if current_chunk_nodes and current_tokens >= min_chunk_tokens:
        child_chunk = _create_ast_child_chunk_obj(
            current_chunk_nodes, chunk_order, doc_id
        )
        child_chunks.append(child_chunk)
    
    return child_chunks


def _create_ast_child_chunk_obj(nodes, order, doc_id):
    """创建子分块对象"""
    import hashlib
    
    content = "\n\n".join([n['content'] for n in nodes if n['content'].strip()])
    chunk_id = f"{doc_id}_child_ast_{order:04d}_{hashlib.md5(content.encode('utf-8')).hexdigest()[:8]}"
    
    return ASTChunkInfo(
        id=chunk_id,
        content=content,
        start_line=nodes[0]['line_start'],
        end_line=nodes[-1]['line_end'],
        order=order,
        doc_id=doc_id,
        ast_nodes=nodes,
        metadata={
            'chunk_type': 'child',
            'creation_method': 'ast_semantic',
            'contains_headers': any(n['type'] == 'heading' for n in nodes),
            'contains_tables': any(n['type'] == 'table' for n in nodes),
            'contains_code': any(n['type'] == 'code_block' for n in nodes),
            'ast_node_count': len(nodes),
            'context_stack': nodes[0]['context_stack'] if nodes else []
        }
    )


def _create_ast_parent_chunks(enhanced_nodes, parent_split_level, doc_id):
    """基于AST和标题层级创建父分块"""
    parent_chunks = []
    current_section_nodes = []
    current_section_header = None
    parent_order = 0
    
    for node_info in enhanced_nodes:
        # 检查是否是父分块边界标题
        if (node_info['type'] == 'heading' and 
            node_info.get('header_level', 99) <= parent_split_level):
            
            # 完成当前父分块
            if current_section_nodes:
                parent_chunk = _create_ast_parent_chunk_obj(
                    current_section_nodes, current_section_header, parent_order, doc_id
                )
                parent_chunks.append(parent_chunk)
                parent_order += 1
            
            # 开始新的父分块
            current_section_nodes = [node_info]
            current_section_header = {
                'level': node_info['header_level'],
                'title': node_info['header_title'],
                'context_stack': node_info['context_stack']
            }
        else:
            current_section_nodes.append(node_info)
    
    # 处理最后一个父分块
    if current_section_nodes:
        parent_chunk = _create_ast_parent_chunk_obj(
            current_section_nodes, current_section_header, parent_order, doc_id
        )
        parent_chunks.append(parent_chunk)
    
    return parent_chunks


def _create_ast_parent_chunk_obj(nodes, header_info, order, doc_id):
    """创建父分块对象"""
    import hashlib

    # 生成原始内容
    content = "\n\n".join([n['content'] for n in nodes if n['content'].strip()])

    # 生成标题层级路径前缀
    context_prefix = ""
    context_depth = 0
    if header_info and header_info.get('context_stack'):
        context_stack = header_info['context_stack']
        current_level = header_info.get('level', 0)

        # 只有当当前标题层级 > 1 时，才需要添加上级标题上下文
        if current_level > 1 and len(context_stack) > 1:
            # 构建标题路径：从 H1 到当前层级的前一级
            # 例如：当前是 H3，则包含 H1 > H2
            title_path_parts = []
            for ctx in context_stack[:-1]:  # 排除当前层级（最后一个）
                level = ctx.get('level', 1)
                title = ctx.get('title', '')
                if title:
                    # 生成 markdown 标题格式
                    prefix_mark = '#' * level
                    title_path_parts.append(f"{prefix_mark} {title}")

            # 如果有上级标题，生成前缀
            if title_path_parts:
                context_prefix = " > ".join(title_path_parts) + "\n\n"
                context_depth = len(title_path_parts)

    # 将前缀添加到内容开头
    if context_prefix:
        content = context_prefix + content

    chunk_id = f"{doc_id}_parent_ast_{order:04d}_{hashlib.md5(content.encode('utf-8')).hexdigest()[:8]}"

    return ASTChunkInfo(
        id=chunk_id,
        content=content,
        start_line=nodes[0]['line_start'],
        end_line=nodes[-1]['line_end'],
        order=order,
        doc_id=doc_id,
        ast_nodes=nodes,
        metadata={
            'chunk_type': 'parent',
            'creation_method': 'ast_semantic',
            'section_title': header_info['title'] if header_info else '',
            'header_level': header_info['level'] if header_info else 0,
            'context_stack': header_info['context_stack'] if header_info else [],
            'semantic_completeness': True,
            'ast_node_count': len(nodes),
            'has_context_prefix': bool(context_prefix),
            'context_depth': context_depth
        }
    )


def _create_ast_relationships(child_chunks, parent_chunks, enhanced_nodes, doc_id, kb_id):
    """基于AST结构创建精确的父子关联"""
    relationships = []
    
    for child_chunk in child_chunks:
        # 通过行号范围找到对应的父分块
        matching_parent = _find_parent_by_line_range(
            child_chunk.start_line, child_chunk.end_line, parent_chunks
        )
        
        if matching_parent:
            # 从AST中提取语义信息
            semantic_info = _extract_ast_semantic_info(child_chunk, matching_parent)
            
            relationships.append({
                'child_chunk_id': child_chunk.id,
                'parent_chunk_id': matching_parent.id,
                'doc_id': doc_id,
                'kb_id': kb_id,
                'relevance_score': 100,
                'relationship_type': 'ast_containment',
                'section_title': matching_parent.section_title,
                'child_start_line': child_chunk.start_line,
                'child_end_line': child_chunk.end_line,
                'parent_start_line': matching_parent.start_line,
                'parent_end_line': matching_parent.end_line,
                'semantic_info': semantic_info
            })
    
    return relationships


def _find_parent_by_line_range(child_start, child_end, parent_chunks):
    """通过行号范围找到对应的父分块"""
    for parent in parent_chunks:
        if (parent.start_line <= child_start and parent.end_line >= child_end):
            return parent
    return None


def _extract_ast_semantic_info(child_chunk, parent_chunk):
    """从AST中提取语义信息"""
    child_nodes = child_chunk.ast_nodes
    
    semantic_info = {
        'contains_headers': len([n for n in child_nodes if n['type'] == 'heading']),
        'contains_tables': len([n for n in child_nodes if n['type'] == 'table']),
        'contains_code': len([n for n in child_nodes if n['type'] == 'code_block']),
        'contains_lists': len([n for n in child_nodes if n['type'] in ['bullet_list', 'ordered_list']]),
        'context_hierarchy': parent_chunk.context_stack,
        'ast_node_types': list(set([n['type'] for n in child_nodes])),
        'parent_section_title': parent_chunk.section_title
    }
    
    return semantic_info


# 以下函数已被简化方案替代，请使用 middle_json_simple.py 和 use_middle_json.py