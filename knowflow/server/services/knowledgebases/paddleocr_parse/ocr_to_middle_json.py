"""
OCR 结果转 middle.json

将 PaddleOCR 的识别结果转换为 pseudo-middle.json 格式，
以便复用 MinerU 的 SimpleMiddleJsonConverter
"""

import logging
from typing import List, Dict, Any, Optional


class OCRToMiddleJsonConverter:
    """
    将 PaddleOCR 结果转换为 pseudo-middle.json 格式

    PaddleOCR 只提供块级结构，缺少行级细节。
    我们创建一个"伪 middle.json"，每个块对应一个"伪行"。
    """

    def __init__(self, kb_id: Optional[str] = None):
        """
        初始化转换器

        Args:
            kb_id: 知识库ID（用于图片 URL）
        """
        self.kb_id = kb_id
        self.logger = logging.getLogger(__name__)
        # PaddleOCR 使用 144 DPI，需要转换为 72 DPI PDF 坐标
        self.dpi_scale_factor = 72.0 / 144.0  # 0.5

    def convert(self, ocr_result: Dict[str, Any]) -> dict:
        """
        转换 OCR 结果为 pseudo-middle.json

        Args:
            ocr_result: PaddleOCR 完整结果
                {
                    "markdown": str,
                    "blocks": [
                        {
                            "block_label": str,
                            "block_content": str,
                            "block_bbox": [x0, y0, x1, y1],
                            "page_idx": int,  # 已添加页码
                            ...
                        },
                        ...
                    ],
                    "page_count": int,
                    ...
                }

        Returns:
            pseudo-middle.json:
            {
                "pdf_info": [
                    {
                        "page_idx": 0,
                        "para_blocks": [...]
                    },
                    ...
                ]
            }
        """
        blocks = ocr_result.get('blocks', [])
        page_count = ocr_result.get('page_count', 1)
        images = ocr_result.get('images', {})  # 获取图片数据

        self.logger.debug(
            f"Converting {page_count} pages with {len(blocks)} total blocks "
            f"and {len(images)} images"
        )

        # 保存图片数据供后续匹配使用
        self.images = images

        # 按页码分组块，保持原始顺序
        pages_blocks = {}
        for block in blocks:
            page_idx = block.get('page_idx', 0)
            if page_idx not in pages_blocks:
                pages_blocks[page_idx] = []
            pages_blocks[page_idx].append(block)

        # 转换每一页
        pdf_info = []
        for page_idx in sorted(pages_blocks.keys()):
            page_blocks = pages_blocks[page_idx]

            # 预处理：合并 figure_title 和 table/image（模仿 MinerU 的 caption 机制）
            processed_blocks = self._merge_captions_with_content(page_blocks)

            # 转换块列表
            para_blocks = []
            for block in processed_blocks:
                para_block = self._convert_block_to_para_block(
                    block, page_idx
                )
                if para_block:
                    para_blocks.append(para_block)

            pdf_info.append({
                'page_idx': page_idx,
                'para_blocks': para_blocks
            })

        self.logger.info(
            f"Converted {len(pdf_info)} pages to pseudo-middle.json"
        )

        return {'pdf_info': pdf_info}

    def _merge_captions_with_content(self, blocks: List[Dict]) -> List[Dict]:
        """
        合并 figure_title 和紧随其后的 table/image 块

        模仿 MinerU 的设计：
        - figure_title 块作为 caption 嵌入到 table/image 块的 blocks 数组中
        - 最终结构：table/image 块包含 [caption_block, body_block]

        Args:
            blocks: 同一页的所有块列表

        Returns:
            处理后的块列表
        """
        result = []
        i = 0

        while i < len(blocks):
            current_block = blocks[i]
            current_label = current_block.get('block_label', '')

            # 检查是否是 figure_title 且下一个块是 table/image
            if current_label == 'figure_title' and i + 1 < len(blocks):
                next_block = blocks[i + 1]
                next_label = next_block.get('block_label', '')

                # 如果下一个块是 table 或 image，进行合并
                if next_label in ('table', 'chart_box'):
                    self.logger.debug(
                        f"Merging figure_title (block {current_block.get('block_id')}) "
                        f"with {next_label} (block {next_block.get('block_id')})"
                    )

                    # 将 caption 信息添加到 next_block
                    next_block['_caption_block'] = current_block
                    result.append(next_block)
                    i += 2  # 跳过 caption 和 content 块
                    continue

            # 正常添加块
            result.append(current_block)
            i += 1

        self.logger.debug(
            f"Caption merging: {len(blocks)} blocks -> {len(result)} blocks"
        )

        return result

    def _convert_block_to_para_block(
        self,
        block: Dict[str, Any],
        page_idx: int
    ) -> Optional[dict]:
        """
        将 PaddleOCR block 转换为 para_block

        PaddleOCR block 格式:
        {
            "block_label": "paragraph_title" | "text" | "table" | "image",
            "block_content": str,
            "block_bbox": [x0, y0, x1, y1],
            "block_id": int,
            "block_order": int
        }

        pseudo-middle.json para_block 格式:
        {
            "type": "text" | "title" | "table" | "image",
            "bbox": [x0, y0, x1, y1],
            "lines": [
                {
                    "bbox": [x0, y0, x1, y1],
                    "spans": [
                        {
                            "type": "text",
                            "content": str,
                            "bbox": [x0, y0, x1, y1]
                        }
                    ]
                }
            ],
            "_paddleocr_block": {
                "block_label": str,
                "block_id": int,
                "block_order": int
            }
        }
        """
        block_label = block.get('block_label', 'text')

        # 过滤掉页眉、页脚、页码、侧边栏、页眉图片等非内容块
        skip_labels = ['header', 'footer', 'number', 'aside_text', 'header_image']
        if block_label in skip_labels:
            self.logger.debug(f"Skipping {block_label} block")
            return None

        block_content = block.get('block_content', '').strip()
        block_bbox_raw = block.get('block_bbox', [0, 0, 0, 0])
        block_id = block.get('block_id', 0)
        block_order = block.get('block_order', 0)

        # 转换 bbox 坐标：144 DPI -> 72 DPI
        block_bbox = self._convert_bbox_to_pdf_coords(block_bbox_raw)

        # 映射块类型到 middle.json 类型
        block_type = self._map_block_label_to_type(block_label)

        # 特殊处理图片块
        if block_type == 'image':
            # 构建预期的图片键名
            img_key = f"imgs/img_in_{block_label}_box_{block_bbox_raw[0]}_{block_bbox_raw[1]}_{block_bbox_raw[2]}_{block_bbox_raw[3]}.jpg"

            # 创建图片 para_block
            para_block = {
                'type': 'image',
                'bbox': block_bbox,
                'image_path': img_key,
                'lines': [{
                    'spans': [{
                        'type': 'text',
                        'content': ''  # 图片块不需要文本内容
                    }]
                }]
            }

            # 如果有 caption，创建 MinerU 风格的嵌套结构
            if '_caption_block' in block:
                caption_block = block['_caption_block']
                caption_content = caption_block.get('block_content', '')
                caption_bbox = self._convert_bbox_to_pdf_coords(
                    caption_block.get('block_bbox', block_bbox_raw)
                )

                # 创建 blocks 数组：[image_caption, image_body]
                para_block['blocks'] = [
                    {
                        'type': 'image_caption',
                        'bbox': caption_bbox,
                        'lines': self._create_pseudo_lines(
                            caption_content, caption_bbox, 'text'
                        )
                    },
                    {
                        'type': 'image_body',
                        'bbox': block_bbox,
                        'image_path': img_key
                    }
                ]

                # 添加 paddleocr_block 信息（用于追踪）
                para_block['_paddleocr_block'] = {
                    'block_label': block_label,
                    'block_id': block_id,
                    'block_order': block_order,
                    'caption_block_id': caption_block.get('block_id')
                }

            # 如果有图片数据，添加到块中
            if hasattr(self, 'images') and self.images and img_key in self.images:
                para_block['_image_data'] = self.images[img_key]

            return para_block

        # 检查是否为空内容（但图片块允许为空）
        if not block_content and block_label not in ('chart_box',):
            self.logger.debug(
                f"Skipping empty block {block_id} "
                f"(label={block_label})"
            )
            return None

        # 转换 bbox 坐标：144 DPI -> 72 DPI
        block_bbox = self._convert_bbox_to_pdf_coords(block_bbox_raw)

        # 映射块类型到 middle.json 类型
        block_type = self._map_block_label_to_type(block_label)

        # 创建 para_block
        para_block = {
            'type': block_type,
            'bbox': block_bbox,
            'lines': self._create_pseudo_lines(
                block_content, block_bbox, block_type
            ),
            '_paddleocr_block': {
                'block_label': block_label,
                'block_id': block_id,
                'block_order': block_order
            }
        }

        # 如果是表格且有 caption，创建 MinerU 风格的嵌套结构
        if block_type == 'table' and '_caption_block' in block:
            caption_block = block['_caption_block']
            caption_content = caption_block.get('block_content', '')
            caption_bbox = self._convert_bbox_to_pdf_coords(
                caption_block.get('block_bbox', block_bbox_raw)
            )

            # 创建 blocks 数组：[table_caption, table_body]
            para_block['blocks'] = [
                {
                    'type': 'table_caption',
                    'bbox': caption_bbox,
                    'lines': self._create_pseudo_lines(
                        caption_content, caption_bbox, 'text'
                    )
                },
                {
                    'type': 'table_body',
                    'bbox': block_bbox,
                    'lines': self._create_pseudo_lines(
                        block_content, block_bbox, block_type
                    )
                }
            ]

            # 保留合并信息（用于调试和追踪）
            para_block['_paddleocr_block']['caption_block_id'] = caption_block.get('block_id')

        # 标题块添加 level
        if block_type == 'title':
            para_block['level'] = self._infer_title_level(
                block_content, block_label
            )

        return para_block

    def _map_block_label_to_type(self, block_label: str) -> str:
        """
        映射 PaddleOCR block_label 到 middle.json type

        PaddleOCR labels:
        - paragraph_title
        - text
        - table
        - image, header_image, chart, figure
        - list (可能)

        middle.json types:
        - title
        - text
        - table
        - image
        - list
        """
        label_to_type = {
            'paragraph_title': 'title',
            'text': 'text',
            'table': 'table',
            'image': 'image',
            'chart': 'image',          # 图表
            'chart_box': 'image',      # 图表框（PaddleOCR 特定）
            'figure': 'image',         # 图形
            'list': 'list',
            # 其他可能的类型
            'title': 'title',
            'para': 'text',
            'paragraph': 'text',
            'doc_title': 'title',      # 文档标题
            'abstract': 'text',        # 摘要
            'reference_content': 'text', # 参考文献
            'figure_title': 'text',    # 图片标题作为文本
            'footnote': 'text',        # 脚注保留为文本,
        }

        return label_to_type.get(block_label.lower(), 'text')

    def _create_pseudo_lines(
        self,
        content: str,
        bbox: List[float],
        block_type: str
    ) -> List[dict]:
        """
        创建伪行结构

        由于 PaddleOCR 不提供行级数据，我们为每个块创建一个"伪行"，
        使用块级坐标。

        对于多行内容，我们也只创建一个行，将所有内容放在一起。
        这样可以简化逻辑，坐标映射时所有行都会使用相同的块级坐标。

        Args:
            content: 块内容
            bbox: 块坐标
            block_type: 块类型

        Returns:
            lines 列表
        """
        # 特殊处理：表格和图片
        if block_type in ('table', 'image'):
            # 对于表格和图片，保持内容完整（包括 HTML）
            return [{
                'bbox': bbox,
                'spans': [{
                    'type': block_type,
                    'content': content,
                    'bbox': bbox
                }]
            }]

        # 对于文本和标题，创建单个伪行
        # 注意：即使内容包含多行，我们也只创建一个 line
        # 这样 coordinate_map 中所有行都会映射到同一个块级坐标
        return [{
            'bbox': bbox,
            'spans': [{
                'type': 'text',
                'content': content,
                'bbox': bbox
            }]
        }]

    def _infer_title_level(self, content: str, block_label: str) -> int:
        """
        推断标题级别 - 基于 PaddleOCR 返回的 block_label

        PaddleOCR 的 block_label 层级映射:
        - doc_title: 文档标题 -> H1
        - paragraph_title: 段落/章节标题 -> H2
        - title: 通用标题 -> H3
        - 其他: 默认 H3

        Args:
            content: 标题内容
            block_label: PaddleOCR 返回的块标签

        Returns:
            标题级别 (1-6)
        """
        # 如果内容已经是 markdown 标题格式，优先使用
        if content.startswith('#'):
            level = 0
            for char in content:
                if char == '#':
                    level += 1
                else:
                    break
            return min(level, 6)

        # 基于 block_label 直接映射
        label_to_level = {
            'doc_title': 1,        # 文档主标题
            'paragraph_title': 2,  # 章节标题
            'title': 3,           # 通用标题
            # 其他可能的标题类型
            'section_title': 2,   # 节标题
            'subsection_title': 3, # 子节标题
            'heading': 3,         # 标题
            'subheading': 4,      # 子标题
        }

        # 返回对应的级别，默认为 3
        return label_to_level.get(block_label.lower(), 3)

    def get_statistics(self, middle_json: dict) -> Dict[str, Any]:
        """
        获取转换统计信息

        Args:
            middle_json: pseudo-middle.json

        Returns:
            统计信息
        """
        pdf_info = middle_json.get('pdf_info', [])

        total_pages = len(pdf_info)
        total_blocks = sum(
            len(page.get('para_blocks', []))
            for page in pdf_info
        )

        block_types = {}
        for page in pdf_info:
            for block in page.get('para_blocks', []):
                block_type = block.get('type', 'unknown')
                block_types[block_type] = block_types.get(block_type, 0) + 1

        return {
            'total_pages': total_pages,
            'total_blocks': total_blocks,
            'block_types': block_types
        }

    def _convert_bbox_to_pdf_coords(self, bbox: List[Any]) -> List[int]:
        """
        将 PaddleOCR 144 DPI 坐标转换为 72 DPI PDF 坐标

        PaddleOCR 使用 144 DPI (2x 72 DPI)，需要除以 2

        Args:
            bbox: [x0, y0, x1, y1] 格式的坐标（144 DPI）

        Returns:
            [x0, y0, x1, y1] 格式的坐标（72 DPI）
        """
        if not bbox or len(bbox) != 4:
            return [0, 0, 0, 0]

        try:
            scale = self.dpi_scale_factor  # 0.5
            x0, y0, x1, y1 = [float(v) for v in bbox]
            pdf_x0 = int(round(x0 * scale))
            pdf_y0 = int(round(y0 * scale))
            pdf_x1 = int(round(x1 * scale))
            pdf_y1 = int(round(y1 * scale))
            return [pdf_x0, pdf_y0, pdf_x1, pdf_y1]
        except (TypeError, ValueError) as e:
            self.logger.warning(f"Failed to convert bbox {bbox}: {e}")
            return [0, 0, 0, 0]
