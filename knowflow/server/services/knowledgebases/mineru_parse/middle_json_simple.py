#!/usr/bin/env python3
"""
简化版：将 middle.json 转换为可以直接替代 OCR markdown 的文档
同时保存坐标映射信息供查询使用
"""

import json
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path


# ==================== 公式分隔符配置（参照 MinerU 官方实现） ====================
# 支持自定义公式分隔符，与 MinerU 保持一致
DEFAULT_LATEX_DELIMITERS = {
    'display': {'left': '$$', 'right': '$$'},      # 行间公式（独立成行）
    'inline': {'left': '$', 'right': '$'}          # 行内公式（嵌入文本中）
}

# 可通过环境变量或配置文件自定义分隔符
def get_latex_delimiters():
    """获取 LaTeX 公式分隔符配置"""
    # TODO: 未来可从配置文件读取
    return DEFAULT_LATEX_DELIMITERS

LATEX_DELIMITERS = get_latex_delimiters()
INLINE_LEFT = LATEX_DELIMITERS['inline']['left']
INLINE_RIGHT = LATEX_DELIMITERS['inline']['right']
DISPLAY_LEFT = LATEX_DELIMITERS['display']['left']
DISPLAY_RIGHT = LATEX_DELIMITERS['display']['right']
# ==============================================================================


class SimpleMiddleJsonConverter:
    """简化的 middle.json 转换器"""

    def __init__(self, kb_id: Optional[str] = None, merge_text_lines: bool = False):
        # 坐标缓存: {md_file_path: {line_number: [page_idx, x1, y1, x2, y2]}}
        self.coordinate_cache = {}
        self.kb_id = kb_id  # 知识库ID，用于生成图片URL
        self.merge_text_lines = merge_text_lines  # 是否合并 text/title 的多行（用于 general 分块）

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
                    caption_line_bboxes = self._extract_image_caption_bboxes(block)

                    text_lines = markdown_text.split('\n')
                    caption_line_idx = 0

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
                elif block.get('type') == 'table' and block.get('blocks'):
                    # 处理表格：table_caption 和 table_body 合并到同一个块
                    # 计算整个表格的 bbox (包含 caption 和 body)
                    table_full_bbox = self._compute_table_full_bbox(block)

                    # 所有行使用同一个 bbox
                    text_lines = markdown_text.split('\n')
                    for line in text_lines:
                        markdown_lines.append(line)
                        if line.strip():
                            coordinate_map[line_counter] = [
                                block['page_idx'],
                                table_full_bbox[0], table_full_bbox[2],
                                table_full_bbox[1], table_full_bbox[3]
                            ]
                        line_counter += 1
                else:
                    # 根据 merge_text_lines 参数决定如何处理 text/title
                    if block.get('type') in ('text', 'title') and self.merge_text_lines:
                        # 整块处理，使用 block 级别的坐标（用于 general 分块）
                        markdown_lines.append(markdown_text)
                        if markdown_text.strip():
                            coordinate_map[line_counter] = [
                                block['page_idx'],
                                block['bbox'][0],
                                block['bbox'][2],
                                block['bbox'][1],
                                block['bbox'][3]
                            ]
                        line_counter += 1
                    else:
                        # 逐行处理（用于 smart 分块或其他类型）
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

    def _merge_bboxes(self, bboxes: List[List]) -> List:
        """合并多个 bbox 为一个包含所有区域的 bbox"""
        if not bboxes:
            return [0, 0, 0, 0]

        xs1 = [bbox[0] for bbox in bboxes]
        ys1 = [bbox[1] for bbox in bboxes]
        xs2 = [bbox[2] for bbox in bboxes]
        ys2 = [bbox[3] for bbox in bboxes]

        return [min(xs1), min(ys1), max(xs2), max(ys2)]

    def _compute_line_bbox_from_spans(self, line: Dict, fallback_bbox: List) -> List:
        """从 spans 计算行的 bbox"""
        spans = line.get('spans', [])
        if not spans:
            return fallback_bbox

        # 优先使用 line 自带的 bbox
        line_bbox = line.get('bbox')
        if line_bbox:
            return line_bbox

        # 从 spans 合并计算
        span_bboxes = [span.get('bbox') for span in spans if span.get('bbox')]
        if span_bboxes:
            return self._merge_bboxes(span_bboxes)

        return fallback_bbox

    def _compute_table_full_bbox(self, table_block: Dict) -> List:
        """计算表格的完整 bbox (包含 caption 和 body)"""
        caption_bbox = None
        body_bbox = None

        for sub_block in table_block.get('blocks', []):
            if sub_block.get('type') == 'table_caption':
                caption_bbox = sub_block.get('bbox')
            elif sub_block.get('type') == 'table_body':
                body_bbox = sub_block.get('bbox')

        # 合并 caption 和 body 的 bbox
        bboxes = [bbox for bbox in [caption_bbox, body_bbox] if bbox]
        if bboxes:
            return self._merge_bboxes(bboxes)

        return table_block.get('bbox', [0, 0, 0, 0])

    def _extract_image_caption_bboxes(self, image_block: Dict) -> List[List]:
        """提取图片 caption 的行级 bbox 列表"""
        caption_line_bboxes = []

        for sub_block in image_block.get('blocks', []):
            if sub_block.get('type') == 'image_caption' and 'lines' in sub_block:
                for line in sub_block['lines']:
                    if not line.get('spans'):
                        continue

                    line_bbox = self._compute_line_bbox_from_spans(
                        line,
                        fallback_bbox=sub_block.get('bbox', image_block['bbox'])
                    )
                    caption_line_bboxes.append(line_bbox)
                break

        return caption_line_bboxes

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
        # 获取块类型
        block_type = block.get('type', 'text')

        # 根据 merge_text_lines 参数决定是否合并 text/title 的多行
        if block_type in ('text', 'title') and self.merge_text_lines:
            # 合并多行（用于 general 分块，避免断句）
            text = self._extract_text_from_lines(block, merge_lines=True)
        else:
            # 保留多行（用于 smart 分块，精确匹配坐标）
            text = self._extract_text(block)

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

        # 对于标题块，保留 level 字段以支持多级标题
        if block_type == 'title' and 'level' in block:
            result['level'] = block['level']

        # 保留原始的 blocks 数组，用于图片块和表格块的精确坐标
        if block_type in ('image', 'table') and 'blocks' in block:
            result['blocks'] = block['blocks']

        # 根据 merge_text_lines 决定是否生成 line_infos
        # merge_text_lines=True: text/title 不生成 line_infos（已合并为整块）
        # merge_text_lines=False: text/title 也生成 line_infos（保留逐行坐标）
        if block_type not in ('image', 'table'):
            if not (block_type in ('text', 'title') and self.merge_text_lines):
                # 列表类型需要特殊处理:每个子块作为独立行
                if block_type == 'list' and 'blocks' in block:
                    line_infos = self._collect_list_line_infos(block, page_idx)
                else:
                    line_infos = self._collect_line_infos(block, page_idx)
                if line_infos:
                    result['line_infos'] = line_infos

        return result

    def _extract_text(self, block: Dict) -> str:
        """提取文本内容"""
        # 处理表格
        if block.get('type') == 'table':
            caption_text = ''
            table_html = ''

            # 提取 table_caption
            if 'blocks' in block:
                for sub_block in block['blocks']:
                    if sub_block.get('type') == 'table_caption':
                        caption_text = self._extract_text_from_lines(sub_block)

            # 提取 HTML 表格 - 支持多种结构
            # 1. 直接从 block 获取 HTML
            if 'html' in block:
                table_html = block['html']
            # 2. 从嵌套 blocks 结构获取 HTML (MinerU 格式)
            elif 'blocks' in block:
                for sub_block in block['blocks']:
                    if sub_block.get('type') == 'table_body' and 'lines' in sub_block:
                        for line in sub_block['lines']:
                            if 'spans' in line:
                                for span in line['spans']:
                                    if 'html' in span:
                                        table_html = span['html']
                                        break
            # 3. 从 lines/spans 直接获取 content (PaddleOCR 格式)
            if not table_html and 'lines' in block:
                for line in block['lines']:
                    if 'spans' in line:
                        for span in line['spans']:
                            # PaddleOCR: HTML 在 content 字段中
                            if span.get('type') == 'table' and 'content' in span:
                                table_html = span['content']
                                break
                            # 也支持 html 字段
                            elif 'html' in span:
                                table_html = span['html']
                                break
                    if table_html:
                        break

            # 如果有标题和表格内容,将标题作为 HTML 注释嵌入表格
            if caption_text and table_html:
                # 在 <table> 标签后插入 <caption>
                if table_html.startswith('<table'):
                    # 找到 <table> 标签的结束位置
                    table_tag_end = table_html.find('>')
                    if table_tag_end != -1:
                        # 在 <table> 后插入 <caption>
                        table_html = (table_html[:table_tag_end + 1] +
                                    f'<caption>{caption_text}</caption>' +
                                    table_html[table_tag_end + 1:])
                return table_html
            elif table_html:
                return table_html
            elif caption_text:
                return caption_text
            else:
                return ''

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
                    # VLM 的列表项文本已经包含了 "-" 符号,不再重复添加
                    items.append(item_text)
            return '\n'.join(items)

        # 普通文本
        return self._extract_text_from_lines(block)

    def _extract_text_from_lines(self, block: Dict, merge_lines: bool = False) -> str:
        """
        从 lines 结构提取文本（支持行内公式和行间公式）

        Args:
            block: 文本块
            merge_lines: 是否合并多行（用于 text/title 类型）
        """
        if 'lines' not in block:
            return block.get('text', '')

        lines = []
        for line in block['lines']:
            if 'spans' in line:
                # 处理 span 级别的内容，包括文本和公式
                line_parts = []
                for span in line['spans']:
                    span_type = span.get('type', 'text')
                    content = span.get('content', '')

                    if not content:
                        continue

                    # 根据 span 类型添加适当的分隔符（参照 MinerU 官方实现）
                    if span_type == 'inline_equation':
                        # 行内公式：$...$
                        line_parts.append(f"{INLINE_LEFT}{content}{INLINE_RIGHT}")
                    elif span_type == 'interline_equation':
                        # 行间公式：\n$$\n...\n$$\n
                        line_parts.append(f"\n{DISPLAY_LEFT}\n{content}\n{DISPLAY_RIGHT}\n")
                    else:
                        # 普通文本
                        line_parts.append(content)

                line_text = ''.join(line_parts)
                if line_text:
                    lines.append(line_text)

        if merge_lines:
            # 对于 text/title 类型，合并多行（PDF 排版导致的自动换行）
            return ''.join(lines)
        else:
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

    def _collect_list_line_infos(self, list_block: Dict, default_page_idx: int) -> List[Dict]:
        """为列表块提取每个子项的坐标信息"""
        line_infos: List[Dict] = []

        for sub_block in list_block.get('blocks', []):
            # 提取子块的文本(已包含 "- " 前缀)
            item_text = self._extract_text_from_lines(sub_block).strip()
            if not item_text:
                continue

            # 使用子块的 bbox 作为该列表项的坐标
            bbox = sub_block.get('bbox', list_block.get('bbox', [0, 0, 0, 0]))

            line_infos.append({
                'text': item_text,
                'bbox': bbox,
                'page_idx': default_page_idx
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

        if not text and block_type not in ('image', 'interline_equation'):
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
            lines = [f'<img src="{path}" style="max-width: 300px;max-height: 500px;" alt="{alt_text}">']
            if text:
                lines.append(text)
            return '\n'.join(lines)
        elif block_type == 'interline_equation':
            # 行间公式（块级）：\n$$\n...\n$$\n（参照 MinerU 官方实现）
            # text 已经通过 _extract_text_from_lines 处理，可能已包含分隔符
            # 但为了确保一致性，检查并添加分隔符
            if text:
                # 如果已经有分隔符，直接返回
                if text.strip().startswith(DISPLAY_LEFT) and text.strip().endswith(DISPLAY_RIGHT):
                    return text
                # 否则添加分隔符
                return f"\n{DISPLAY_LEFT}\n{text.strip()}\n{DISPLAY_RIGHT}\n"
            return ''
        elif block_type == 'list':
            return text  # 已经格式化过了
        else:
            return text



# 全局转换器实例
_converter = SimpleMiddleJsonConverter()


def middle_json_to_markdown(middle_json_path: str, output_md_path: str, kb_id: Optional[str] = None) -> Tuple[str, Dict]:
    """
    简单接口：将 middle.json 转换为 markdown（方案A：同时返回coordinate_map）

    这个 markdown 可以直接替代 OCR 生成的 markdown 使用

    Args:
        middle_json_path: middle.json 文件路径
        output_md_path: 输出 markdown 文件路径
        kb_id: 知识库ID（用于生成 minio 图片路径）

    Returns:
        (markdown内容, 坐标映射字典)
    """
    # 如果有 kb_id，创建新的转换器实例
    if kb_id:
        converter = SimpleMiddleJsonConverter(kb_id=kb_id)
        markdown_content, coordinate_map = converter.convert_to_markdown(middle_json_path, output_md_path, kb_id=kb_id)
    else:
        markdown_content, coordinate_map = _converter.convert_to_markdown(middle_json_path, output_md_path)
    return markdown_content, coordinate_map


