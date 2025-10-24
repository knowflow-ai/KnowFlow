#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片上下文提取模块

从 Markdown 文档中提取图片的上下文信息，包括：
1. 图片的 caption（图片标签/标题）
2. 图片所在的标题
3. 图片前面的相关段落
"""

import logging
import re
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ImageContextExtractor:
    """图片上下文提取器"""

    def __init__(self, markdown_content: str):
        """
        初始化提取器

        Args:
            markdown_content: 完整的 Markdown 文档内容
        """
        self.content = markdown_content
        self.lines = markdown_content.split('\n')

    def extract_context_for_image(
        self,
        image_tag: str,
        image_path: str,
        max_paragraphs: int = 2
    ) -> Dict[str, Optional[str]]:
        """
        提取单个图片的上下文信息

        Args:
            image_tag: 图片标签（HTML 或 Markdown 格式）
            image_path: 图片路径
            max_paragraphs: 最多提取的段落数（默认2个）

        Returns:
            {
                'caption': 图片标签,
                'heading': 所在标题,
                'paragraphs': [段落列表],
                'context_summary': 上下文摘要文本
            }
        """
        # 查找图片在文档中的位置
        img_line_idx = self._find_image_line(image_tag, image_path)
        if img_line_idx is None:
            logger.warning(f"未找到图片在文档中的位置: {image_path}")
            return {
                'caption': None,
                'heading': None,
                'paragraphs': [],
                'context_summary': None
            }

        # 提取 caption
        caption = self._extract_caption(img_line_idx)

        # 提取所在标题
        heading = self._extract_heading(img_line_idx)

        # 提取前面的段落
        paragraphs = self._extract_preceding_paragraphs(
            img_line_idx,
            caption,
            max_paragraphs
        )

        # 生成上下文摘要
        context_summary = self._build_context_summary(caption, heading, paragraphs)

        return {
            'caption': caption,
            'heading': heading,
            'paragraphs': paragraphs,
            'context_summary': context_summary
        }

    def _find_image_line(self, image_tag: str, image_path: str) -> Optional[int]:
        """查找图片所在的行号"""
        # 直接查找完整标签
        for i, line in enumerate(self.lines):
            if image_tag in line:
                return i

        # 如果找不到完整标签，尝试查找路径
        for i, line in enumerate(self.lines):
            if image_path in line:
                return i

        return None

    def _extract_caption(self, img_line_idx: int) -> Optional[str]:
        """
        提取图片的 caption

        支持以下格式：
        1. HTML: <img src="path" alt="caption">
        2. Markdown: ![caption](path)
        3. 下一行的文本（如：图1: xxx）
        """
        line = self.lines[img_line_idx]

        # Markdown 格式: ![caption](path)
        md_match = re.search(r'!\[([^\]]*)\]', line)
        if md_match and md_match.group(1).strip():
            return md_match.group(1).strip()

        # HTML 格式: <img alt="caption" ...>
        html_match = re.search(r'alt="([^"]*)"', line)
        if html_match and html_match.group(1).strip():
            return html_match.group(1).strip()

        # 检查下一行是否是 caption（例如：图1: xxx）
        if img_line_idx + 1 < len(self.lines):
            next_line = self.lines[img_line_idx + 1].strip()
            if re.match(r'^(图|Figure|Fig\.?)\s*\d+[:：]', next_line):
                return next_line

        return None

    def _extract_heading(self, img_line_idx: int) -> Optional[str]:
        """
        提取图片所在的标题

        向前查找最近的 Markdown 标题（# 开头）
        """
        for i in range(img_line_idx - 1, -1, -1):
            line = self.lines[i].strip()
            if line.startswith('#'):
                # 移除 # 符号并返回标题文本
                heading = re.sub(r'^#+\s*', '', line).strip()
                return heading

        return None

    def _extract_preceding_paragraphs(
        self,
        img_line_idx: int,
        caption: Optional[str],
        max_paragraphs: int
    ) -> List[str]:
        """
        提取图片前面的段落

        规则：
        1. 向前查找，遇到标题或文档开头停止
        2. 如果第一个段落包含 "如图x" 且匹配 caption，只返回一个段落
        3. 否则最多返回 max_paragraphs 个段落
        """
        paragraphs = []
        current_paragraph = []

        # 向前扫描
        for i in range(img_line_idx - 1, -1, -1):
            line = self.lines[i].strip()

            # 遇到标题，停止
            if line.startswith('#'):
                break

            # 空行表示段落分隔
            if not line:
                if current_paragraph:
                    paragraph_text = ' '.join(current_paragraph)
                    paragraphs.insert(0, paragraph_text)
                    current_paragraph = []

                    # 如果已经收集到足够的段落，停止
                    if len(paragraphs) >= max_paragraphs:
                        break
            else:
                # 跳过图片标签和表格
                if not self._is_special_line(line):
                    current_paragraph.insert(0, line)

        # 添加最后一个段落
        if current_paragraph and len(paragraphs) < max_paragraphs:
            paragraph_text = ' '.join(current_paragraph)
            paragraphs.insert(0, paragraph_text)

        # 应用特殊规则：检查是否匹配 caption
        if paragraphs and caption:
            # 检查第一个段落是否匹配
            if self._paragraph_references_caption(paragraphs[0], caption):
                logger.info(f"第一个段落匹配 caption，仅返回第一个段落")
                return paragraphs[:1]

            # 检查第二个段落是否匹配
            if len(paragraphs) > 1 and self._paragraph_references_caption(paragraphs[1], caption):
                logger.info(f"第二个段落匹配 caption，仅返回第二个段落")
                return [paragraphs[1]]  # 只返回第二个段落

        # 都不匹配，返回最多 max_paragraphs 个段落
        return paragraphs[:max_paragraphs]

    def _is_special_line(self, line: str) -> bool:
        """判断是否是特殊行（图片、表格等）"""
        # 图片标签
        if line.startswith('!') or '<img' in line:
            return True
        # 表格行
        if line.startswith('|') or re.match(r'^[-:]+$', line):
            return True
        return False

    def _paragraph_references_caption(self, paragraph: str, caption: str) -> bool:
        """
        检查段落是否引用了图片 caption

        检测模式：
        - "如图X"
        - "见图X"
        - "图X所示"
        - caption 中的关键数字
        """
        # 提取 caption 中的数字
        caption_numbers = re.findall(r'\d+', caption)

        # 检测引用模式
        reference_patterns = [
            r'如图\s*' + r'|'.join(caption_numbers),
            r'见图\s*' + r'|'.join(caption_numbers),
            r'图\s*' + r'|'.join(caption_numbers) + r'\s*所示',
            r'Figure\s*' + r'|'.join(caption_numbers),
            r'Fig\.?\s*' + r'|'.join(caption_numbers),
        ]

        for pattern in reference_patterns:
            if re.search(pattern, paragraph, re.IGNORECASE):
                return True

        return False

    def _build_context_summary(
        self,
        caption: Optional[str],
        heading: Optional[str],
        paragraphs: List[str]
    ) -> str:
        """构建上下文摘要文本"""
        parts = []

        if heading:
            parts.append(f"所在章节：{heading}")

        if caption:
            parts.append(f"图片标题：{caption}")

        if paragraphs:
            context_text = '\n'.join(f"相关段落{i+1}：{p}" for i, p in enumerate(paragraphs))
            parts.append(context_text)

        return '\n\n'.join(parts) if parts else None
