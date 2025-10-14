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


def call_ragflow_vision_api_batch(image_paths: List[str], tenant_id: str) -> Dict[str, Optional[str]]:
    """
    批量调用 RAGFlow 视觉 API 获取图片描述

    Args:
        image_paths: 图片路径列表（MinIO路径）
        tenant_id: 租户ID

    Returns:
        {image_path: description} 字典，失败的图片描述为 None
    """
    if not image_paths:
        return {}

    ragflow_base_url = os.getenv('RAGFLOW_BASE_URL', 'http://localhost:9380')
    api_endpoint = f"{ragflow_base_url}/v1/llm/vision/describe_batch"

    try:
        payload = {
            "tenant_id": tenant_id,
            "images": [{"image_data": path} for path in image_paths]
        }

        response = requests.post(api_endpoint, json=payload, timeout=90)
        response.raise_for_status()

        result = response.json()
        if result.get('code') == 0 and 'data' in result:
            descriptions = result['data'].get('descriptions', [])

            # 构建路径到描述的映射
            result_dict = {}
            for i, path in enumerate(image_paths):
                if i < len(descriptions):
                    result_dict[path] = descriptions[i]
                    logger.info(f"图片描述已生成 [{i+1}/{len(image_paths)}]: {descriptions[i][:50] if descriptions[i] else 'None'}...")
                else:
                    result_dict[path] = None
                    logger.warning(f"图片 {path} 未返回描述")

            return result_dict
        else:
            logger.warning(f"RAGFlow 批量API返回错误: {result}")
            return {path: None for path in image_paths}

    except requests.exceptions.RequestException as e:
        logger.error(f"调用 RAGFlow 批量视觉 API 失败: {e}")
        return {path: None for path in image_paths}


def enhance_chunks_with_vision(
    chunks: List[Dict[str, Any]],
    tenant_id: str,
    description_format: str = "[图片描述: {desc}]",
    batch_size: int = None
) -> List[Dict[str, Any]]:
    """
    为分块添加图片视觉增强描述（批量处理）

    Args:
        chunks: 分块列表，每个分块是 {"content": str, "coordinates": [...]}
        tenant_id: 租户ID
        description_format: 描述格式模板
        batch_size: 批量处理大小，默认从环境变量读取，设为1则单条发送

    Returns:
        增强后的分块列表
    """
    if not chunks:
        return chunks

    # 从环境变量或参数获取批量大小
    if batch_size is None:
        batch_size = int(os.getenv('VISION_BATCH_SIZE', '3'))

    logger.info(f"开始图片视觉增强，共 {len(chunks)} 个分块，批量大小: {batch_size}")

    # 第一步：收集所有需要处理的图片
    chunk_images = []  # [(chunk_index, img_refs), ...]
    all_image_paths = []

    for i, chunk in enumerate(chunks):
        if not isinstance(chunk, dict) or 'content' not in chunk:
            continue

        img_refs = extract_image_references(chunk['content'])
        if img_refs:
            chunk_images.append((i, img_refs))
            for _, img_path, _, _ in img_refs:
                if img_path not in all_image_paths:
                    all_image_paths.append(img_path)

    if not all_image_paths:
        logger.info("未发现需要处理的图片")
        return chunks

    logger.info(f"共发现 {len(all_image_paths)} 个唯一图片")

    # 第二步：批量获取所有图片描述
    all_descriptions = {}

    for i in range(0, len(all_image_paths), batch_size):
        batch = all_image_paths[i:i + batch_size]
        logger.info(f"处理批次 {i//batch_size + 1}/{(len(all_image_paths) + batch_size - 1)//batch_size}，包含 {len(batch)} 个图片")
        batch_results = call_ragflow_vision_api_batch(batch, tenant_id)
        all_descriptions.update(batch_results)

    # 第三步：将描述应用到对应的分块
    enhanced_chunks = []
    enhanced_count = 0

    for i, chunk in enumerate(chunks):
        # 查找该分块是否有图片
        chunk_img_refs = None
        for chunk_idx, img_refs in chunk_images:
            if chunk_idx == i:
                chunk_img_refs = img_refs
                break

        if chunk_img_refs is None:
            enhanced_chunks.append(chunk)
            continue

        # 应用图片描述
        enhanced_content = chunk['content']
        for full_tag, img_path, start, end in reversed(chunk_img_refs):
            desc = all_descriptions.get(img_path)
            if desc:
                enhancement = "\n" + description_format.format(desc=desc) + "\n"
                enhanced_content = enhanced_content[:end] + enhancement + enhanced_content[end:]
                enhanced_count += 1

        enhanced_chunk = chunk.copy()
        enhanced_chunk['content'] = enhanced_content
        enhanced_chunks.append(enhanced_chunk)

    logger.info(f"图片视觉增强完成，共增强 {enhanced_count} 个图片")
    return enhanced_chunks
