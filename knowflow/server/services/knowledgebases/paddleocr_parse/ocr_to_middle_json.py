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

        self.logger.debug(
            f"Converting {page_count} pages with {len(blocks)} total blocks"
        )

        # 按页码分组块
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

            # 转换块列表
            para_blocks = []
            for block in page_blocks:
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
        block_content = block.get('block_content', '').strip()
        block_bbox = block.get('block_bbox', [0, 0, 0, 0])
        block_id = block.get('block_id', 0)
        block_order = block.get('block_order', 0)

        if not block_content:
            self.logger.debug(
                f"Skipping empty block {block_id} "
                f"(label={block_label})"
            )
            return None

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

        # 标题块添加 level
        if block_type == 'title':
            para_block['level'] = self._infer_title_level(
                block_content, block_bbox
            )

        return para_block

    def _map_block_label_to_type(self, block_label: str) -> str:
        """
        映射 PaddleOCR block_label 到 middle.json type

        PaddleOCR labels:
        - paragraph_title
        - text
        - table
        - image
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
            'list': 'list',
            # 其他可能的类型
            'title': 'title',
            'para': 'text',
            'paragraph': 'text',
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

    def _infer_title_level(self, content: str, bbox: List[float]) -> int:
        """
        推断标题级别

        启发式规则:
        1. 内容以 "# " 开头 -> 解析 markdown
        2. 内容长度 < 20 字符 -> 可能是高级标题
        3. bbox 高度较大 -> 可能是高级标题

        Args:
            content: 标题内容
            bbox: 标题坐标

        Returns:
            标题级别 (1-6)
        """
        # 如果内容已经是 markdown 标题格式
        if content.startswith('#'):
            level = 0
            for char in content:
                if char == '#':
                    level += 1
                else:
                    break
            return min(level, 6)

        # 根据长度和高度启发式推断
        content_length = len(content.strip())
        bbox_height = bbox[3] - bbox[1] if len(bbox) >= 4 else 20

        if content_length <= 10 and bbox_height > 30:
            return 1  # 一级标题
        elif content_length <= 20 and bbox_height > 25:
            return 2  # 二级标题
        elif content_length <= 30:
            return 3  # 三级标题
        else:
            return 4  # 四级及以下

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
