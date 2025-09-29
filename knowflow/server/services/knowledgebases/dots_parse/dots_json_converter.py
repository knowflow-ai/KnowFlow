#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOTS JSON 到 Markdown 转换器，保留精确坐标信息（类似 MinerU 的 middle.json 处理）
"""

import os
import logging
import re
from typing import Dict, List, Optional, Tuple, Any, Iterable

from .format_transformer import clean_text, get_formula_in_markdown
from ..mineru_parse.middle_json_simple import SimpleMiddleJsonConverter

logger = logging.getLogger(__name__)


class DotsJsonConverter:
    """DOTS JSON 到 Markdown 转换器，保留精确坐标信息"""

    def __init__(self, kb_id: Optional[str] = None):
        """初始化转换器

        Args:
            kb_id: 知识库ID（用于生成图片URL）
        """
        self.kb_id = kb_id
        self.dpi_scale_factor = 72.0 / 200.0  # DOTS坐标 -> PDF坐标
        self.middle_converter = SimpleMiddleJsonConverter(kb_id=kb_id)

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
        block_pages: List[List[Dict[str, Any]]] = []
        extracted_images: List[str] = []

        for page_idx, page_data in enumerate(pages_data):
            layout_elements = page_data.get('layout_elements', [])
            page_image = page_data.get('page_image')
            page_blocks: List[Dict[str, Any]] = []

            for element_idx, element in enumerate(layout_elements):
                block, image_path = self._element_to_block(
                    element,
                    page_idx=page_idx,
                    element_idx=element_idx,
                    page_image=page_image,
                    output_dir=output_dir,
                )

                if image_path:
                    extracted_images.append(image_path)

                if block:
                    page_blocks.append(block)

            block_pages.append(page_blocks)

        markdown_content, coordinate_map = self.middle_converter.convert_block_pages_to_markdown(block_pages)
        logger.info(
            "DOTS 转换完成: %d 行 markdown，%d 个坐标映射",
            len(markdown_content.split('\n')),
            len(coordinate_map),
        )

        return markdown_content, coordinate_map, extracted_images

    def _element_to_block(
        self,
        element: Dict,
        page_idx: int,
        element_idx: int,
        page_image: Optional[Any] = None,
        output_dir: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        category = element.get('category', 'Text')
        raw_text = element.get('text', '') or ''
        text = clean_text(raw_text)
        bbox = self._convert_bbox_to_pdf_coords(element.get('bbox', [0, 0, 0, 0])) or [0, 0, 0, 0]

        # 跳过页眉页脚（与 MinerU 保持一致）
        if category in ['Page-header', 'Page-footer']:
            return None, None

        block: Dict[str, Any] = {
            'bbox': bbox,
            'type': 'text',
            'text': text,
            'page_idx': page_idx,
        }
        image_path = None

        category_lower = category.lower()

        if category == 'Picture':
            block['type'] = 'image'
            block['text'] = text
            if page_image and output_dir:
                try:
                    from PIL import Image

                    os.makedirs(output_dir, exist_ok=True)
                    x1, y1, x2, y2 = [int(coord) for coord in element.get('bbox', [0, 0, 0, 0])]
                    image_crop = page_image.crop((x1, y1, x2, y2))
                    image_filename = f"image_{page_idx}_{element_idx}_{x1}_{y1}.png"
                    image_path = os.path.join(output_dir, image_filename)
                    image_crop.save(image_path)
                    if self.kb_id:
                        import os as _os
                        image_name = _os.path.basename(image_path)
                        block['image_path'] = f"/minio/{self.kb_id}/{image_name}"
                    else:
                        block['image_path'] = image_filename
                except Exception as e:
                    logger.warning(f"提取图片失败: {e}")
                    block['image_path'] = None
            else:
                block['image_path'] = None

        elif category == 'Formula':
            block['type'] = 'formula'
            block['text'] = get_formula_in_markdown(raw_text)

        elif category == 'Table':
            block['type'] = 'table'
            block['text'] = raw_text

        elif category in ['Title', 'Section'] or category_lower.startswith('heading') or category_lower in {'subtitle', 'subheading'}:
            block['type'] = 'title'
            level = 1
            if category == 'Section':
                level = 2
            elif category_lower.startswith('heading'):
                match = re.search(r'(\d+)', category)
                level = int(match.group(1)) if match else 3
            elif category_lower in {'subtitle', 'subheading'}:
                level = 3
            block['level'] = max(1, min(level, 6))
            block['text'] = text

        elif category_lower in {'list', 'bullet_list', 'bullet'}:
            block['type'] = 'list'
            list_lines = []
            for line in raw_text.split('\n'):
                cleaned = clean_text(line)
                if not cleaned:
                    continue
                if cleaned.startswith(('-', '*', '•', '·')) or re.match(r'^\d+\.', cleaned):
                    list_lines.append(cleaned)
                else:
                    list_lines.append(f"- {cleaned}")
            block['text'] = '\n'.join(list_lines)

        else:
            block['text'] = text

        return block, image_path

    def convert_elements_to_markdown_with_coordinates(
        self,
        elements: List,
        output_dir: Optional[str] = None,
    ) -> Tuple[str, Dict, List]:
        """将 DOTS 元素列表转换为 markdown，同时保留坐标映射"""

        sorted_elements = sorted(elements, key=lambda e: (e.page_number, e.center_y, e.center_x))
        block_pages: List[List[Dict[str, Any]]] = []
        extracted_images: List[str] = []

        current_page_idx = None
        current_page_blocks: List[Dict[str, Any]] = []

        for element_idx, element in enumerate(sorted_elements):
            page_idx = element.page_number - 1
            if current_page_idx is None or page_idx != current_page_idx:
                if current_page_blocks:
                    block_pages.append(current_page_blocks)
                current_page_blocks = []
                current_page_idx = page_idx

            element_dict = {
                'category': element.category,
                'text': element.text,
                'bbox': element.bbox,
            }

            block, image_path = self._element_to_block(
                element_dict,
                page_idx=page_idx,
                element_idx=element_idx,
                page_image=None,
                output_dir=output_dir,
            )

            if image_path:
                extracted_images.append(image_path)

            if block:
                current_page_blocks.append(block)

        if current_page_blocks:
            block_pages.append(current_page_blocks)

        markdown_content, coordinate_map = self.middle_converter.convert_block_pages_to_markdown(block_pages)
        return markdown_content, coordinate_map, extracted_images

    def _convert_bbox_to_pdf_coords(self, bbox: List[Any]) -> Optional[List[int]]:
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
            return [pdf_x1, pdf_y1, pdf_x2, pdf_y2]
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
                    coords = self._convert_bbox_to_pdf_coords(bbox)
                    if coords:
                        coordinate_map[i] = [page_idx, coords[0], coords[2], coords[1], coords[3]]
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
