#!/usr/bin/env python3
"""
简化版：将 middle.json 转换为可以直接替代 OCR markdown 的文档
同时保存坐标映射信息供查询使用
"""

import json
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class SimpleMiddleJsonConverter:
    """简化的 middle.json 转换器"""

    def __init__(self, kb_id: Optional[str] = None):
        # 坐标缓存: {md_file_path: {line_number: [page_idx, x1, y1, x2, y2]}}
        self.coordinate_cache = {}
        self.kb_id = kb_id  # 知识库ID，用于生成图片URL

    def convert_to_markdown(self, middle_json_path: str, output_md_path: Optional[str] = None, kb_id: Optional[str] = None) -> Tuple[str, Dict]:
        """
        将 middle.json 转换为普通 markdown，同时保存坐标映射

        Returns:
            (markdown内容, 坐标映射字典)
        """
        with open(middle_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        markdown_lines = []
        coordinate_map = {}  # {行号: 坐标}
        line_counter = 0

        for page_idx, page in enumerate(data['pdf_info']):
            blocks = self._extract_blocks_from_page(page, page_idx)

            # 按y坐标排序
            blocks.sort(key=lambda b: b['bbox'][1] if len(b['bbox']) > 1 else 0)

            for block in blocks:
                markdown_text = self._block_to_markdown(block)
                if markdown_text:
                    # 记录每一行的坐标
                    text_lines = markdown_text.split('\n')
                    for line in text_lines:
                        if line.strip():  # 非空行
                            # 适配前端格式: [page, x1, x2, y1, y2]
                            # 其中 x1=x_min, x2=x_max, y1=y_min, y2=y_max
                            coordinate_map[line_counter] = [
                                block['page_idx'],
                                block['bbox'][0],  # x_min -> x1
                                block['bbox'][2],  # x_max -> x2
                                block['bbox'][1],  # y_min -> y1
                                block['bbox'][3]   # y_max -> y2
                            ]
                            markdown_lines.append(line)
                            line_counter += 1

                    # 添加空行分隔块
                    markdown_lines.append('')
                    line_counter += 1

        markdown_content = '\n'.join(markdown_lines)

        # 保存 markdown 文件
        if output_md_path:
            with open(output_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            # 缓存坐标信息（确保键是字符串）
            self.coordinate_cache[output_md_path] = {str(k): v for k, v in coordinate_map.items()}

            # 同时保存坐标映射文件（用于持久化）
            # 确保键是字符串，以便 JSON 正确序列化
            coord_map_str_keys = {str(k): v for k, v in coordinate_map.items()}
            coord_file = output_md_path.replace('.md', '_coords.json')
            with open(coord_file, 'w', encoding='utf-8') as f:
                json.dump(coord_map_str_keys, f, ensure_ascii=False, indent=2)

        return markdown_content, coordinate_map

    def _extract_blocks_from_page(self, page: Dict, page_idx: int) -> List[Dict]:
        """从页面提取所有块"""
        blocks = []

        # 优先使用 para_blocks (VLM模式)
        if 'para_blocks' in page and isinstance(page['para_blocks'], list):
            for block in page['para_blocks']:
                if block.get('bbox'):
                    blocks.append(self._process_block(block, page_idx))

        # 其次使用 preproc_blocks (Pipeline模式)
        elif 'preproc_blocks' in page:
            for block in page['preproc_blocks']:
                if block.get('bbox'):
                    blocks.append(self._process_block(block, page_idx))

        return blocks

    def _process_block(self, block: Dict, page_idx: int) -> Dict:
        """处理单个块"""
        # 提取文本
        text = self._extract_text(block)

        return {
            'bbox': block['bbox'],
            'type': block.get('type', 'text'),
            'text': text,
            'page_idx': page_idx,
            'image_path': self._extract_image_path(block) if block.get('type') == 'image' else None
        }

    def _extract_text(self, block: Dict) -> str:
        """提取文本内容"""
        # 处理表格
        if block.get('type') == 'table' and 'html' in block:
            return block['html']

        # 处理列表
        if block.get('type') == 'list' and 'blocks' in block:
            items = []
            for sub_block in block['blocks']:
                item_text = self._extract_text_from_lines(sub_block)
                if item_text:
                    items.append(f"- {item_text}")
            return '\n'.join(items)

        # 普通文本
        return self._extract_text_from_lines(block)

    def _extract_text_from_lines(self, block: Dict) -> str:
        """从 lines 结构提取文本"""
        if 'lines' not in block:
            return block.get('text', '')

        lines = []
        for line in block['lines']:
            if 'spans' in line:
                line_text = ''.join(span.get('content', '') for span in line['spans'])
                if line_text:
                    lines.append(line_text)
        return '\n'.join(lines)

    def _extract_image_path(self, block: Dict) -> Optional[str]:
        """提取图片路径"""
        # 直接从block获取
        if 'image_path' in block:
            return block['image_path']

        # 从嵌套结构获取
        if 'blocks' in block:
            for sub_block in block['blocks']:
                if 'lines' in sub_block:
                    for line in sub_block['lines']:
                        if 'spans' in line:
                            for span in line['spans']:
                                if 'image_path' in span:
                                    return span['image_path']
        return None

    def _block_to_markdown(self, block: Dict) -> str:
        """转换块为 markdown 格式（不包含坐标注释）"""
        block_type = block['type']
        text = block['text']

        if not text and block_type != 'image':
            return ''

        # 根据类型生成 markdown
        if block_type == 'title':
            return f"# {text}"
        elif block_type == 'table':
            return text  # HTML表格
        elif block_type == 'image':
            path = block.get('image_path', 'missing_path')
            # 如果有 kb_id，转换为 minio 路径
            if self.kb_id and path and not path.startswith(('http://', 'https://', '/minio/')):
                # 只取文件名，生成 minio 路径
                import os
                image_name = os.path.basename(path)
                path = f"/minio/{self.kb_id}/{image_name}"
            return f"![Image]({path})"
        elif block_type == 'formula':
            if not (text.startswith('$') and text.endswith('$')):
                return f"${text}$"
            return text
        elif block_type == 'list':
            return text  # 已经格式化过了
        else:
            return text

    def get_coordinates_for_text(self, md_file_path: str, text: str) -> List[List[float]]:
        """
        获取文本对应的坐标（用于分块后查询坐标）

        Args:
            md_file_path: markdown 文件路径
            text: 要查询的文本

        Returns:
            坐标列表
        """
        # 从缓存或文件加载坐标映射
        if md_file_path not in self.coordinate_cache:
            coord_file = md_file_path.replace('.md', '_coords.json')
            if Path(coord_file).exists():
                with open(coord_file, 'r') as f:
                    coord_data = json.load(f)
                    # 确保所有键都是字符串
                    coord_data_str_keys = {str(k): v for k, v in coord_data.items()}
                    self.coordinate_cache[md_file_path] = coord_data_str_keys
            else:
                return []

        coord_map = self.coordinate_cache.get(md_file_path, {})

        # 读取 markdown 文件
        with open(md_file_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
            md_lines = md_content.split('\n')

        # 创建行内容到行号的映射
        # 注意：这里需要匹配保存时的逻辑，包括空行也要计数
        line_to_number = {}
        for i, line in enumerate(md_lines):
            if line.strip():  # 非空行才记录映射，但行号使用实际的行索引
                line_to_number[line.strip()] = i

        # 查找匹配的行和坐标
        coordinates = []
        text_lines = text.split('\n')

        for text_line in text_lines:
            text_line = text_line.strip()
            if text_line:
                # 查找这行在原始 markdown 中的行号
                line_no = line_to_number.get(text_line)
                if line_no is not None:
                    # 注意：坐标映射的key是字符串
                    coord = coord_map.get(str(line_no))
                    if coord and coord not in coordinates:
                        coordinates.append(coord)
        return coordinates


# 全局转换器实例
_converter = SimpleMiddleJsonConverter()


def middle_json_to_markdown(middle_json_path: str, output_md_path: str, kb_id: Optional[str] = None) -> str:
    """
    简单接口：将 middle.json 转换为 markdown

    这个 markdown 可以直接替代 OCR 生成的 markdown 使用

    Args:
        middle_json_path: middle.json 文件路径
        output_md_path: 输出 markdown 文件路径
        kb_id: 知识库ID（用于生成 minio 图片路径）
    """
    # 如果有 kb_id，创建新的转换器实例
    if kb_id:
        converter = SimpleMiddleJsonConverter(kb_id=kb_id)
        markdown_content, _ = converter.convert_to_markdown(middle_json_path, output_md_path, kb_id=kb_id)
    else:
        markdown_content, _ = _converter.convert_to_markdown(middle_json_path, output_md_path)
    return markdown_content


def get_chunk_coordinates(md_file_path: str, chunk_text: str) -> List[List[float]]:
    """
    获取分块的坐标信息

    在分块完成后调用此函数获取每个分块对应的坐标
    """
    return _converter.get_coordinates_for_text(md_file_path, chunk_text)