#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片视觉增强模块

在分块完成后，为 chunks 中的图片添加 AI 生成的描述
"""

import logging
import re
import requests
from typing import List, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


def extract_image_references(text: str) -> List[tuple]:
    """
    提取文本中的图片引用

    支持两种格式：
    1. HTML: <img src="/minio/xxx.jpg" ...>
    2. Markdown: ![alt](path)

    Returns:
        [(full_tag, img_path, start_pos, end_pos), ...]
    """
    matches = []

    # HTML <img> 标签（MinerU 格式）
    html_pattern = r'<img\s+src="([^"]+)"[^>]*>'
    for match in re.finditer(html_pattern, text):
        matches.append((match.group(0), match.group(1), match.start(), match.end()))

    # Markdown 格式
    md_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    for match in re.finditer(md_pattern, text):
        matches.append((match.group(0), match.group(2), match.start(), match.end()))

    matches.sort(key=lambda x: x[2])
    return matches


def call_ragflow_vision_api(image_path: str, tenant_id: str) -> Optional[str]:
    """
    调用 RAGFlow 视觉 API 获取图片描述

    Args:
        image_path: 图片路径（MinIO路径）
        tenant_id: 租户ID

    Returns:
        图片描述文本，失败返回 None
    """
    ragflow_base_url = os.getenv('RAGFLOW_BASE_URL', 'http://localhost:9380')
    api_endpoint = f"{ragflow_base_url}/v1/llm/vision/describe"

    try:
        payload = {
            "tenant_id": tenant_id,
            "image_data": image_path
        }

        response = requests.post(api_endpoint, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        if result.get('code') == 0 and 'data' in result:
            description = result['data'].get('description', '')
            logger.info(f"图片描述已生成: {description[:50]}...")
            return description
        else:
            logger.warning(f"RAGFlow 返回错误: {result}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"调用 RAGFlow 视觉 API 失败: {e}")
        return None


def enhance_chunks_with_vision(
    chunks: List[Dict[str, Any]],
    tenant_id: str,
    description_format: str = "[图片描述: {desc}]"
) -> List[Dict[str, Any]]:
    """
    为分块添加图片视觉增强描述

    Args:
        chunks: 分块列表，每个分块是 {"content": str, "coordinates": [...]}
        tenant_id: 租户ID
        description_format: 描述格式模板

    Returns:
        增强后的分块列表
    """
    if not chunks:
        return chunks

    logger.info(f"开始图片视觉增强，共 {len(chunks)} 个分块")

    enhanced_chunks = []
    enhanced_count = 0

    for i, chunk in enumerate(chunks):
        if not isinstance(chunk, dict) or 'content' not in chunk:
            enhanced_chunks.append(chunk)
            continue

        img_refs = extract_image_references(chunk['content'])
        if not img_refs:
            enhanced_chunks.append(chunk)
            continue

        logger.info(f"分块 {i+1} 发现 {len(img_refs)} 个图片")

        # 生成图片描述
        enhanced_content = chunk['content']
        for full_tag, img_path, start, end in reversed(img_refs):
            desc = call_ragflow_vision_api(img_path, tenant_id)
            if desc:
                enhancement = "\n" + description_format.format(desc=desc) + "\n"
                enhanced_content = enhanced_content[:end] + enhancement + enhanced_content[end:]
                enhanced_count += 1

        enhanced_chunk = chunk.copy()
        enhanced_chunk['content'] = enhanced_content
        enhanced_chunks.append(enhanced_chunk)

    logger.info(f"图片视觉增强完成，共增强 {enhanced_count} 个图片")
    return enhanced_chunks
