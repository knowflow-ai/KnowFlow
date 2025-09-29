#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOTS JSON 到 Markdown 转换器，保留精确坐标信息（类似 MinerU 的 middle.json 处理）
"""

import os
import logging
import re
from typing import Dict, List, Optional, Tuple, Any, Iterable
from pathlib import Path

from .format_transformer import clean_text, get_formula_in_markdown

logger = logging.getLogger(__name__)


class DotsJsonConverter:
    """DOTS JSON 到 Markdown 转换器，保留精确坐标信息"""

    def __init__(self, kb_id: Optional[str] = None):
        """初始化转换器

        Args:
            kb_id: 知识库ID（用于生成图片URL）
        """
        self.kb_id = kb_id
        self.coordinate_cache = {}  # 缓存坐标信息
        self.dpi_scale_factor = 72.0 / 200.0  # DOTS坐标 -> PDF坐标

    def convert_pages_to_markdown_with_coordinates(self, pages_data: List[Dict],
                                                   output_dir: Optional[str] = None) -> Tuple[str, Dict, List]:
        """
        将 DOTS pages_data 转换为 markdown，同时保留坐标映射（类似 MinerU 的 middle.json 处理）

        Args:
            pages_data: DOTS 处理器的 pages_data（包含 layout_elements）
            output_dir: 图片输出目录（可选）

        Returns:
            (markdown内容, 坐标映射字典, 提取的图片列表)
            坐标字典的键为行号（整数），值为 [page_idx, x1, x2, y1, y2]
        """
        markdown_lines = []
        coordinate_map = {}  # {行号: [page_idx, x1, x2, y1, y2]}
        line_counter = 0
        extracted_images = []

        for page_idx, page_data in enumerate(pages_data):
            # 获取页面的布局元素
            layout_elements = page_data.get('layout_elements', [])
            if not layout_elements:
                continue

            # 获取页面图像（用于图片提取）
            page_image = page_data.get('page_image')

            # 处理每个布局元素
            for element_idx, element in enumerate(layout_elements):
                # 转换元素为 markdown
                markdown_text, image_path = self._element_to_markdown(
                    element, page_idx, element_idx, page_image, output_dir
                )

                if image_path:
                    extracted_images.append(image_path)

                if markdown_text:
                    bbox = element.get('bbox', [0, 0, 0, 0])
                    coords = self._convert_bbox_to_pdf_coords(bbox, page_idx)

                    text_lines = markdown_text.split('\n')
                    for line in text_lines:
                        markdown_lines.append(line)
                        if line.strip() and coords:
                            coordinate_map[line_counter] = coords
                        line_counter += 1

                    # 块之间添加空行，保持与 layoutjson2md 一致
                    markdown_lines.append('')
                    line_counter += 1

        while markdown_lines and markdown_lines[-1] == '':
            markdown_lines.pop()
            line_counter -= 1

        markdown_content = '\n'.join(markdown_lines)

        # 记录坐标映射信息
        logger.info(f"DOTS 转换完成: {len(markdown_lines)} 行 markdown，{len(coordinate_map)} 个坐标映射")

        return markdown_content, coordinate_map, extracted_images

    def _element_to_markdown(self, element: Dict, page_idx: int, element_idx: int,
                            page_image: Optional[Any] = None,
                            output_dir: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        将布局元素转换为 markdown 格式（类似 MinerU 的块处理）

        Args:
            element: 布局元素
            page_idx: 页面索引
            element_idx: 元素索引
            page_image: PIL Image 对象（用于提取图片）
            output_dir: 图片输出目录

        Returns:
            (markdown文本, 图片路径或None)
        """
        category = element.get('category', 'Text')
        raw_text = element.get('text', '') or ''
        text = clean_text(raw_text)
        bbox = element.get('bbox', [0, 0, 0, 0])
        image_path = None

        # 跳过页眉页脚（与 layoutjson2md 的 no_page_hf=True 保持一致）
        if category in ['Page-header', 'Page-footer']:
            return '', None

        # 处理图片
        if category == 'Picture':
            if page_image and output_dir:
                try:
                    from PIL import Image

                    # 确保输出目录存在
                    os.makedirs(output_dir, exist_ok=True)

                    # 提取图片区域
                    x1, y1, x2, y2 = [int(coord) for coord in bbox]
                    image_crop = page_image.crop((x1, y1, x2, y2))

                    # 保存图片
                    image_filename = f"image_{page_idx}_{element_idx}_{x1}_{y1}.png"
                    image_path = os.path.join(output_dir, image_filename)
                    image_crop.save(image_path)

                    # 生成 markdown 图片链接
                    if self.kb_id:
                        # MinIO 路径格式
                        minio_path = f"/minio/{self.kb_id}/{image_filename}"
                        return f"![]({minio_path})", image_path
                    else:
                        # 相对路径
                        return f"![]({image_filename})", image_path
                except Exception as e:
                    logger.warning(f"提取图片失败: {e}")
                    return f"[图片: {text if text else 'Picture'}]", None
            else:
                # 如果没有页面图像或输出目录，生成占位符
                return f"[图片: {text if text else 'Picture'}]", None

        # 处理公式
        elif category == 'Formula':
            return get_formula_in_markdown(raw_text), None

        # 表格保持 HTML 输出
        if category == 'Table':
            return raw_text, None

        # 标题级别映射
        heading_level = None
        category_lower = category.lower()
        if category == 'Title':
            heading_level = 1
        elif category == 'Section':
            heading_level = 2
        elif category_lower.startswith('heading'):
            match = re.search(r'(\d+)', category)
            heading_level = int(match.group(1)) if match else 3
        elif category_lower in {'subtitle', 'subheading'}:
            heading_level = 3

        if heading_level:
            heading_level = max(1, min(heading_level, 6))
            return f"{'#' * heading_level} {text}", None

        # 列表处理：逐项补充前缀
        if category_lower in {'list', 'bullet_list', 'bullet'}:
            list_lines = []
            for line in raw_text.split('\n'):
                cleaned = clean_text(line)
                if not cleaned:
                    continue
                if cleaned.startswith(('-', '*', '•', '·')) or re.match(r'^\d+\.', cleaned):
                    list_lines.append(cleaned)
                else:
                    list_lines.append(f"- {cleaned}")
            return '\n'.join(list_lines), None

        return text, None

    def convert_elements_to_markdown_with_coordinates(self, elements: List,
                                                     output_dir: Optional[str] = None) -> Tuple[str, Dict, List]:
        """
        将 DOTS 元素列表转换为 markdown，同时保留坐标映射

        Args:
            elements: DOTSLayoutElement 对象列表
            output_dir: 图片输出目录（可选）

        Returns:
            (markdown内容, 坐标映射字典, 提取的图片列表)
        """
        markdown_lines = []
        coordinate_map = {}
        line_counter = 0
        extracted_images = []

        # 按页面和位置排序元素
        sorted_elements = sorted(elements, key=lambda e: (e.page_number, e.center_y, e.center_x))

        for element in sorted_elements:
            # 转换为字典格式
            element_dict = {
                'category': element.category,
                'text': element.text,
                'bbox': element.bbox
            }

            # 转换为 markdown
            markdown_text, image_path = self._element_to_markdown(
                element_dict, element.page_number - 1, 0, None, output_dir
            )

            if image_path:
                extracted_images.append(image_path)

            if markdown_text:
                coords = self._convert_bbox_to_pdf_coords(
                    element.bbox,
                    element.page_number - 1
                )

                text_lines = markdown_text.split('\n')
                for line in text_lines:
                    markdown_lines.append(line)
                    if line.strip() and coords:
                        coordinate_map[line_counter] = coords
                    line_counter += 1

                markdown_lines.append('')
                line_counter += 1

        while markdown_lines and markdown_lines[-1] == '':
            markdown_lines.pop()
            line_counter -= 1

        markdown_content = '\n'.join(markdown_lines)
        return markdown_content, coordinate_map, extracted_images

    def _convert_bbox_to_pdf_coords(self, bbox: List[Any], page_idx: int) -> Optional[List[int]]:
        """将 DOTS 200DPI 坐标转换为 72DPI PDF 坐标"""
        if not bbox or len(bbox) != 4:
            return None

        try:
            scale = self.dpi_scale_factor
            x1, y1, x2, y2 = [float(v) for v in bbox]
            pdf_x1 = int(round(x1 * scale))
            pdf_y1 = int(round(y1 * scale))
            pdf_x2 = int(round(x2 * scale))
            pdf_y2 = int(round(y2 * scale))
            page_index = int(page_idx)
            return [page_index, pdf_x1, pdf_x2, pdf_y1, pdf_y2]
        except (TypeError, ValueError):
            return None

    def process_dots_chunks_with_coordinates(self, chunks: List[Dict]) -> Tuple[List[str], Dict]:
        """
        处理 DOTS 分块，返回文本列表和坐标映射

        Args:
            chunks: DOTS 分块列表

        Returns:
            (文本列表, 坐标映射字典)
        """
        texts = []
        coordinate_map = {}

        for i, chunk in enumerate(chunks):
            if isinstance(chunk, dict):
                text = chunk.get('content', '') or chunk.get('text', '')
                texts.append(text)

                # 提取坐标信息
                if 'positions' in chunk and chunk['positions']:
                    # DOTS 格式的坐标
                    coordinate_map[i] = chunk['positions'][0]
                elif 'bbox' in chunk:
                    # 标准 bbox 格式
                    bbox = chunk['bbox']
                    page_idx = chunk.get('page_idx', 0)
                    coords = self._convert_bbox_to_pdf_coords(bbox, page_idx)
                    if coords:
                        coordinate_map[i] = coords
            else:
                # 纯文本
                texts.append(str(chunk))

        return texts, coordinate_map

    def map_chunk_to_coordinates(self,
                                 chunk_text: str,
                                 markdown_lines: Iterable[str],
                                 coordinate_map: Dict) -> List[List[int]]:
        """根据 markdown 行坐标映射获取 chunk 对应的坐标列表"""
        if not chunk_text:
            return []

        if not coordinate_map or not markdown_lines:
            return []

        # 构建行索引 -> 坐标的快速访问字典（支持 str/int 键）
        normalized_coord_map: Dict[int, List[int]] = {}
        for key, value in coordinate_map.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            normalized_coord_map[idx] = value

        # 构建行文本映射
        line_lookup: Dict[str, List[int]] = {}
        for idx, raw_line in enumerate(markdown_lines):
            stripped = raw_line.strip()
            if not stripped:
                continue
            line_lookup.setdefault(stripped, []).append(idx)

        used_indices = set()
        coordinates: List[List[int]] = []

        for raw_chunk_line in chunk_text.split('\n'):
            stripped_line = raw_chunk_line.strip()
            if not stripped_line:
                continue

            candidate_indices = line_lookup.get(stripped_line, [])
            selected_idx = None

            for idx in candidate_indices:
                if idx not in used_indices:
                    selected_idx = idx
                    break

            if selected_idx is None:
                # 尝试在 markdown 中做部分匹配（处理列表项或轻微差异）
                for idx, raw_line in enumerate(markdown_lines):
                    if idx in used_indices:
                        continue

                    stripped_md_line = raw_line.strip()
                    if not stripped_md_line:
                        continue

                    # 去除列表前缀后再比较
                    md_line_core = stripped_md_line
                    if md_line_core.startswith(('- ', '* ', '• ', '· ')):
                        md_line_core = md_line_core[2:].strip()

                    chunk_core = stripped_line
                    if chunk_core.startswith(('- ', '* ', '• ', '· ')):
                        chunk_core = chunk_core[2:].strip()

                    if (chunk_core and md_line_core and
                            (chunk_core == md_line_core or
                             chunk_core in md_line_core or
                             md_line_core in chunk_core)):
                        selected_idx = idx
                        break

            if selected_idx is None:
                continue

            used_indices.add(selected_idx)
            coord = normalized_coord_map.get(selected_idx)

            if coord and coord not in coordinates:
                coordinates.append(coord)

        return coordinates
