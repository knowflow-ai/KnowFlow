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

        block_pages = []
        for page_idx, page in enumerate(data['pdf_info']):
            blocks = self._extract_blocks_from_page(page, page_idx)
            # 按y坐标排序
            blocks.sort(key=lambda b: b['bbox'][1] if len(b['bbox']) > 1 else 0)
            block_pages.append(blocks)

        markdown_content, coordinate_map = self.convert_block_pages_to_markdown(block_pages)

        # 可选统计（不打印）

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

    def convert_block_pages_to_markdown(self, block_pages: List[List[Dict]], output_md_path: Optional[str] = None) -> Tuple[str, Dict]:
        """将预处理好的 block_pages 转换为 markdown 与坐标映射"""

        markdown_lines, coordinate_map = self._build_markdown_from_block_pages(block_pages)
        markdown_content = '\n'.join(markdown_lines)

        if output_md_path:
            with open(output_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            coord_map_str_keys = {str(k): v for k, v in coordinate_map.items()}
            coord_file = output_md_path.replace('.md', '_coords.json')
            with open(coord_file, 'w', encoding='utf-8') as f:
                json.dump(coord_map_str_keys, f, ensure_ascii=False, indent=2)

            self.coordinate_cache[output_md_path] = coord_map_str_keys

        return markdown_content, coordinate_map

    def _build_markdown_from_block_pages(self, block_pages: List[List[Dict]]) -> Tuple[List[str], Dict[int, List]]:
        markdown_lines: List[str] = []
        coordinate_map: Dict[int, List] = {}
        line_counter = 0

        for blocks in block_pages:
            for block in blocks:
                markdown_text = self._block_to_markdown(block)
                if not markdown_text:
                    continue

                if block.get('type') == 'image' and block.get('blocks'):
                    # 从 caption 子块中提取行级坐标
                    caption_line_bboxes = []
                    for sub_block in block['blocks']:
                        if sub_block.get('type') == 'image_caption' and 'lines' in sub_block:
                            for line in sub_block['lines']:
                                spans = line.get('spans', [])
                                if not spans:
                                    continue

                                # 获取该行的bbox
                                line_bbox = line.get('bbox')
                                if not line_bbox:
                                    # 如果没有line bbox，从spans合并
                                    xs1, ys1, xs2, ys2 = [], [], [], []
                                    for span in spans:
                                        span_bbox = span.get('bbox')
                                        if span_bbox:
                                            xs1.append(span_bbox[0])
                                            ys1.append(span_bbox[1])
                                            xs2.append(span_bbox[2])
                                            ys2.append(span_bbox[3])
                                    if xs1:
                                        line_bbox = [min(xs1), min(ys1), max(xs2), max(ys2)]
                                    else:
                                        line_bbox = sub_block.get('bbox', block['bbox'])

                                caption_line_bboxes.append(line_bbox)
                            break

                    text_lines = markdown_text.split('\n')
                    caption_line_idx = 0  # caption文本行索引

                    for i, line in enumerate(text_lines):
                        markdown_lines.append(line)
                        if line.strip():
                            bbox = block['bbox']

                            # 第一行：<img> 标签，使用 image_body 的bbox
                            if i == 0 and (line.lstrip().startswith('<img') or line.startswith('![Image]')):
                                for sub_block in block['blocks']:
                                    if sub_block.get('type') == 'image_body':
                                        bbox = sub_block.get('bbox', bbox)
                                        break
                            # 后续行：caption文本，使用对应行的精确bbox
                            elif i > 0 and caption_line_idx < len(caption_line_bboxes):
                                bbox = caption_line_bboxes[caption_line_idx]
                                caption_line_idx += 1

                            coordinate_map[line_counter] = [
                                block['page_idx'],
                                bbox[0], bbox[2], bbox[1], bbox[3]
                            ]
                        line_counter += 1
                else:
                    text_lines = markdown_text.split('\n')
                    line_infos = block.get('line_infos', [])
                    info_idx = 0
                    for line in text_lines:
                        markdown_lines.append(line)
                        if line.strip():
                            if info_idx < len(line_infos):
                                info = line_infos[info_idx]
                                info_idx += 1
                                bbox = info.get('bbox') or block['bbox']
                                page_idx = info.get('page_idx', block['page_idx'])
                            else:
                                bbox = block['bbox']
                                page_idx = block['page_idx']

                            coordinate_map[line_counter] = [
                                page_idx,
                                bbox[0],
                                bbox[2],
                                bbox[1],
                                bbox[3]
                            ]
                        line_counter += 1

                markdown_lines.append('')
                line_counter += 1

        while markdown_lines and markdown_lines[-1] == '':
            markdown_lines.pop()
            line_counter -= 1

        return markdown_lines, coordinate_map

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

        # 获取块类型
        block_type = block.get('type', 'text')

        # 检查是否包含图片路径
        image_path = self._extract_image_path(block)

        # 只有当块类型是 'image' 或没有文本内容时，才使用图片
        # 表格即使有 image_path，也应该保持为表格
        if block_type == 'image' or (image_path and not text and block_type != 'table'):
            block_type = 'image'

        result = {
            'bbox': block['bbox'],
            'type': block_type,
            'text': text,
            'page_idx': page_idx,
            'image_path': image_path if block_type == 'image' else None
        }

        # 保留原始的 blocks 数组，用于图片块的精确坐标
        if block_type == 'image' and 'blocks' in block:
            result['blocks'] = block['blocks']

        if block_type not in ('image', 'table'):
            line_infos = self._collect_line_infos(block, page_idx)
            if line_infos:
                result['line_infos'] = line_infos

        return result

    def _extract_text(self, block: Dict) -> str:
        """提取文本内容"""
        # 处理表格
        if block.get('type') == 'table':
            # 直接从 block 获取 HTML
            if 'html' in block:
                return block['html']

            # 从嵌套结构获取 HTML (blocks[0].lines[0].spans[0].html)
            if 'blocks' in block:
                for sub_block in block['blocks']:
                    if 'lines' in sub_block:
                        for line in sub_block['lines']:
                            if 'spans' in line:
                                for span in line['spans']:
                                    if 'html' in span:
                                        return span['html']

        # 处理图片（提取图片标题）
        if block.get('type') == 'image' and 'blocks' in block:
            # 查找 image_caption 子块
            for sub_block in block['blocks']:
                if sub_block.get('type') == 'image_caption':
                    caption_text = self._extract_text_from_lines(sub_block)
                    if caption_text:
                        return caption_text
            # 如果没有找到 caption，返回空
            return ''

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

    def _collect_line_infos(self, block: Dict, default_page_idx: int) -> List[Dict]:
        """提取行级坐标信息，支持跨页文本"""
        line_infos: List[Dict] = []

        for line in block.get('lines', []) or []:
            spans = line.get('spans', [])
            if not spans:
                continue

            line_text = ''.join(span.get('content', '') for span in spans).strip()
            if not line_text:
                continue

            # 处理跨页标记，当前仅支持跨至下一页
            page_offset = 0
            for span in spans:
                if span.get('cross_page'):
                    page_offset = max(page_offset, 1)

            page_idx = default_page_idx + page_offset

            bbox = line.get('bbox')
            if not bbox:
                xs1, ys1, xs2, ys2 = [], [], [], []
                for span in spans:
                    span_bbox = span.get('bbox')
                    if span_bbox:
                        xs1.append(span_bbox[0])
                        ys1.append(span_bbox[1])
                        xs2.append(span_bbox[2])
                        ys2.append(span_bbox[3])
                if xs1:
                    bbox = [min(xs1), min(ys1), max(xs2), max(ys2)]
                else:
                    bbox = block.get('bbox', [0, 0, 0, 0])

            line_infos.append({
                'text': line_text,
                'bbox': bbox,
                'page_idx': page_idx
            })

        return line_infos

    def _extract_image_path(self, block: Dict) -> Optional[str]:
        """提取图片路径（支持多种嵌套结构）"""
        # 直接从block获取
        if 'image_path' in block:
            return block['image_path']

        # 从嵌套结构获取（支持 table 等类型）
        if 'blocks' in block:
            for sub_block in block['blocks']:
                if 'lines' in sub_block:
                    for line in sub_block['lines']:
                        if 'spans' in line:
                            for span in line['spans']:
                                if 'image_path' in span:
                                    return span['image_path']

        # 从 lines 直接获取（某些格式）
        if 'lines' in block:
            for line in block['lines']:
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
            level = block.get('level', 1)
            try:
                level = int(level)
            except (TypeError, ValueError):
                level = 1
            level = max(1, min(level, 6))
            return f"{'#' * level} {text}"
        elif block_type == 'table':
            return text  # HTML表格
        elif block_type == 'image':
            # 生成 <img> 标签；将图片描述作为 alt，同时保留标题文本为下一行说明
            path = block.get('image_path', 'missing_path')
            # 如果有 kb_id，转换为 minio 路径
            if self.kb_id and path and not path.startswith(('http://', 'https://', '/minio/')):
                import os
                image_name = os.path.basename(path)
                path = f"/minio/{self.kb_id}/{image_name}"
            # 将多行 caption 合并为单行用于 alt 属性
            alt_text = (text or '图片').replace('\n', ' ').replace('"', "'")
            lines = [f'<img src="{path}" style="max-width: 500px;max-height: 800px;" alt="{alt_text}">']
            if text:
                lines.append(text)
            return '\n'.join(lines)
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

        # 去除冗余坐标调试输出

        for idx, text_line in enumerate(text_lines):
            text_line = text_line.strip()
            if text_line:
                # 查找这行在原始 markdown 中的行号
                line_no = line_to_number.get(text_line)
                if line_no is not None:
                    # 注意：坐标映射的key是字符串
                    coord = coord_map.get(str(line_no))
                    if coord and coord not in coordinates:
                        coordinates.append(coord)
                else:
                    # 如果精确匹配失败，尝试部分匹配（用于长文本行）
                    found = False
                    for md_line, md_line_no in line_to_number.items():
                        # 处理列表项的匹配（去掉 "- " 前缀）
                        md_line_clean = md_line[2:] if md_line.startswith('- ') else md_line

                        if (text_line in md_line or md_line in text_line or
                            text_line == md_line_clean or text_line in md_line_clean or md_line_clean in text_line):
                            coord = coord_map.get(str(md_line_no))
                            if coord and coord not in coordinates:
                                coordinates.append(coord)
                                found = True
                                break
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
