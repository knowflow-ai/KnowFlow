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

            # 预处理：合并表格标题和表格主体
            processed_elements = self._merge_table_captions_with_tables(layout_elements)

            for element_idx, element in enumerate(processed_elements):
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

    def _merge_table_captions_with_tables(self, elements: List[Dict]) -> List[Dict]:
        """
        合并表格标题和表格主体为单个块（模仿 MinerU 的结构）

        Args:
            elements: DOTS 布局元素列表

        Returns:
            处理后的元素列表，表格标题已合并到表格内
        """
        if not elements:
            return []

        merged_elements = []
        skip_indices = set()  # 记录需要跳过的索引
        i = 0

        while i < len(elements):
            # 如果当前索引已被标记为跳过，继续下一个
            if i in skip_indices:
                i += 1
                continue

            current = elements[i]
            category = current.get('category', '')

            # 检查是否是表格标题
            if category == 'Caption':
                # 查找后续最近的 Table 元素（可能不是紧邻的）
                table_found = False
                search_limit = min(i + 3, len(elements))  # 最多向后查找3个元素

                for j in range(i + 1, search_limit):
                    if j in skip_indices:
                        continue

                    next_element = elements[j]
                    next_category = next_element.get('category', '')

                    # 如果找到表格，合并
                    if next_category == 'Table':
                        # 合并：将标题作为表格的 caption 子块
                        caption_text = current.get('text', '')
                        table_html = next_element.get('text', '')

                        # 直接在合并时注入 caption 到 HTML 中
                        if caption_text and table_html and table_html.startswith('<table'):
                            table_tag_end = table_html.find('>')
                            if table_tag_end != -1:
                                table_html = (table_html[:table_tag_end + 1] +
                                            f'<caption>{caption_text}</caption>' +
                                            table_html[table_tag_end + 1:])

                        table_element = {
                            'category': 'Table',
                            'text': table_html,  # 已包含 caption 的 HTML
                            'bbox': next_element.get('bbox', [0, 0, 0, 0]),
                            'blocks': [
                                {
                                    'type': 'table_caption',
                                    'text': caption_text,
                                    'bbox': current.get('bbox', [0, 0, 0, 0])
                                },
                                {
                                    'type': 'table_body',
                                    'text': table_html,  # 已包含 caption 的 HTML
                                    'bbox': next_element.get('bbox', [0, 0, 0, 0])
                                }
                            ]
                        }
                        merged_elements.append(table_element)

                        # 标记 caption 和 table 为已处理
                        skip_indices.add(i)
                        skip_indices.add(j)

                        table_found = True
                        logger.debug(f"合并 Caption '{current.get('text', '')[:30]}...' (索引 {i}) 和 Table (索引 {j})")
                        break

                    # 如果遇到另一个 Caption 或其他重要结构，停止搜索
                    if next_category in ['Caption', 'Title', 'Section-header']:
                        break

                # 如果没找到对应的表格，Caption 作为普通文本保留
                if not table_found:
                    merged_elements.append(current)
                    logger.debug(f"保留独立 Caption '{current.get('text', '')[:30]}...' (索引 {i})")
            else:
                # 不是 Caption，直接添加
                merged_elements.append(current)

            i += 1

        logger.debug(f"表格合并: {len(elements)} 个元素 -> {len(merged_elements)} 个元素 (跳过 {len(skip_indices)} 个)")
        return merged_elements

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

            # 如果表格包含 caption 和 body 子块（合并后的结构），转换为 MinerU 格式
            if 'blocks' in element:
                # 将子块转换为 PDF 坐标格式（用于坐标映射）
                converted_blocks = []
                for sub_block in element['blocks']:
                    sub_bbox = self._convert_bbox_to_pdf_coords(sub_block.get('bbox', [0, 0, 0, 0])) or [0, 0, 0, 0]
                    converted_blocks.append({
                        'type': sub_block.get('type'),
                        'text': sub_block.get('text', ''),
                        'bbox': sub_bbox
                    })
                block['blocks'] = converted_blocks

        elif category in ['Title', 'Section', 'Section-header'] or category_lower.startswith('heading') or category_lower in {'subtitle', 'subheading'}:
            block['type'] = 'title'

            # 检查文本是否已经包含 markdown 标题标记
            title_match = re.match(r'^(#{1,6})\s+(.*)', text)
            if title_match:
                # 文本已包含 # 标记，提取级别和清理文本
                level = len(title_match.group(1))
                text = title_match.group(2).strip()
            else:
                # 没有 # 标记，根据 category 设置级别
                level = 1
                if category in ['Section', 'Section-header']:
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

        # 转换为字典格式，方便合并处理
        elements_dicts = []
        for element in sorted_elements:
            elements_dicts.append({
                'category': element.category,
                'text': element.text,
                'bbox': element.bbox,
                'page_number': element.page_number,
            })

        # 合并表格标题和表格主体
        merged_elements_dicts = self._merge_table_captions_with_tables(elements_dicts)

        block_pages: List[List[Dict[str, Any]]] = []
        extracted_images: List[str] = []

        current_page_idx = None
        current_page_blocks: List[Dict[str, Any]] = []

        for element_idx, element_dict in enumerate(merged_elements_dicts):
            page_idx = element_dict.get('page_number', 1) - 1
            if current_page_idx is None or page_idx != current_page_idx:
                if current_page_blocks:
                    block_pages.append(current_page_blocks)
                current_page_blocks = []
                current_page_idx = page_idx

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

