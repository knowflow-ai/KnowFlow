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


def _find_caption_line_end(content: str, img_tag_end: int) -> int:
    """
    查找图片标签后 caption 行的结束位置

    根据 middle_json_simple.py:573 的生成逻辑：
    - alt 属性是 caption 的单行版本（换行替换为空格）
    - 如果有 caption，会在下一行重复 caption 文本

    利用 alt 属性来判断下一行是否是 caption，比简单的空行检测更准确。

    Args:
        content: 分块内容文本
        img_tag_end: 图片标签的结束位置

    Returns:
        应该插入图片描述的位置
    """
    # 向前查找图片标签的开始位置，提取 alt 属性
    img_tag_start = content.rfind('<img', 0, img_tag_end)
    if img_tag_start == -1:
        return img_tag_end

    img_tag = content[img_tag_start:img_tag_end]

    # 提取 alt 属性值
    alt_match = re.search(r'alt="([^"]*)"', img_tag)
    if not alt_match:
        # 没有 alt 属性，无法判断
        return img_tag_end

    alt_text = alt_match.group(1)

    # 如果 alt 是默认值（如 "图片"），认为没有有效 caption
    if not alt_text or alt_text == '图片':
        return img_tag_end

    # 检查下一行
    remaining = content[img_tag_end:]
    if not remaining.startswith('\n'):
        return img_tag_end

    # 只允许一个换行符，如果有多个换行符（空行），则没有 caption
    if len(remaining) > 1 and remaining[1] == '\n':
        return img_tag_end

    # 查找第一行的结束位置
    line_end = remaining.find('\n', 1)
    if line_end == -1:
        # caption 行到文档末尾
        next_line = remaining[1:].strip()
    else:
        # caption 行结束位置
        next_line = remaining[1:line_end].strip()

    # 将 alt_text 规范化：因为 alt 中换行被替换为空格
    # 比较时也将下一行的多余空格规范化
    alt_normalized = ' '.join(alt_text.split())
    next_line_normalized = ' '.join(next_line.split())

    # 判断下一行是否与 alt 文本匹配
    if alt_normalized == next_line_normalized:
        caption_end = img_tag_end + (line_end if line_end != -1 else len(remaining))
        logger.debug(f"检测到图片 caption (通过 alt 匹配): {next_line[:50]}...")
        return caption_end

    # 下一行不是 caption
    return img_tag_end


def call_ragflow_vision_api_batch(
    image_paths: List[str],
    tenant_id: str,
    image_contexts: Dict[str, str] = None
) -> Dict[str, Optional[str]]:
    """
    批量调用 RAGFlow 视觉 API 获取图片描述

    Args:
        image_paths: 图片路径列表（MinIO路径）
        tenant_id: 租户ID
        image_contexts: 图片路径到上下文信息的映射 {image_path: context_summary}

    Returns:
        {image_path: description} 字典，失败的图片描述为 None
    """
    if not image_paths:
        return {}

    ragflow_base_url = os.getenv('RAGFLOW_BASE_URL', 'http://localhost:9380')
    api_endpoint = f"{ragflow_base_url}/v1/llm/vision/describe_batch"

    try:
        # 构建请求payload，包含上下文信息
        images_payload = []
        for path in image_paths:
            img_item = {"image_data": path}
            # 如果有上下文，添加到请求中
            if image_contexts and path in image_contexts:
                img_item["context"] = image_contexts[path]
                logger.debug(f"图片 {path} 包含上下文信息: {image_contexts[path][:100]}...")
            images_payload.append(img_item)

        payload = {
            "tenant_id": tenant_id,
            "images": images_payload
        }

        response = requests.post(api_endpoint, json=payload)
        response.raise_for_status()

        result = response.json()
        if result.get('code') == 0 and 'data' in result:
            descriptions = result['data'].get('descriptions', [])

            # 构建路径到描述的映射
            result_dict = {}
            for i, path in enumerate(image_paths):
                if i < len(descriptions):
                    result_dict[path] = descriptions[i]
                    logger.debug(f"图片描述已生成 [{i+1}/{len(image_paths)}]: {descriptions[i][:50] if descriptions[i] else 'None'}...")
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
    batch_size: int = None,
    markdown_content: str = None
) -> List[Dict[str, Any]]:
    """
    为分块添加图片视觉增强描述（批量处理）

    Args:
        chunks: 分块列表，每个分块是 {"content": str, "coordinates": [...]}
        tenant_id: 租户ID
        description_format: 描述格式模板
        batch_size: 批量处理大小，默认从环境变量读取，设为1则单条发送
        markdown_content: 完整的 Markdown 文档内容，用于提取上下文

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
    chunk_images = {}  # {chunk_index: img_refs}
    image_to_tag = {}  # {img_path: full_tag}

    for i, chunk in enumerate(chunks):
        if not isinstance(chunk, dict) or 'content' not in chunk:
            continue

        img_refs = extract_image_references(chunk['content'])
        if img_refs:
            chunk_images[i] = img_refs
            for full_tag, img_path, _, _ in img_refs:
                if img_path not in image_to_tag:
                    image_to_tag[img_path] = full_tag

    if not image_to_tag:
        logger.info("未发现需要处理的图片")
        return chunks

    logger.info(f"共发现 {len(image_to_tag)} 个唯一图片")

    # 第二步：提取图片上下文信息
    image_contexts = {}
    if markdown_content:
        try:
            from .image_context_extractor import ImageContextExtractor
            extractor = ImageContextExtractor(markdown_content)

            # 为每个图片提取上下文
            for img_path, full_tag in image_to_tag.items():
                context_info = extractor.extract_context_for_image(full_tag, img_path)
                if context_info['context_summary']:
                    image_contexts[img_path] = context_info['context_summary']
                    logger.debug(f"图片 {img_path} 上下文提取成功")

            logger.info(f"成功提取 {len(image_contexts)} 个图片的上下文信息")
        except Exception as e:
            logger.error(f"提取图片上下文失败: {e}")
            image_contexts = {}
    else:
        logger.warning("未提供 markdown_content，将不使用上下文增强")

    # 第三步：批量获取所有图片描述
    all_descriptions = {}
    all_image_paths = list(image_to_tag.keys())

    for i in range(0, len(all_image_paths), batch_size):
        batch = all_image_paths[i:i + batch_size]
        logger.info(f"处理批次 {i//batch_size + 1}/{(len(all_image_paths) + batch_size - 1)//batch_size}，包含 {len(batch)} 个图片")

        # 获取当前批次的图片上下文
        batch_contexts = {path: image_contexts[path] for path in batch if path in image_contexts}

        batch_results = call_ragflow_vision_api_batch(batch, tenant_id, batch_contexts)
        all_descriptions.update(batch_results)

    # 第四步：将描述应用到对应的分块
    enhanced_chunks = []
    enhanced_count = 0

    for i, chunk in enumerate(chunks):
        # 查找该分块是否有图片
        chunk_img_refs = chunk_images.get(i)
        if chunk_img_refs is None:
            enhanced_chunks.append(chunk)
            continue

        # 应用图片描述
        enhanced_content = chunk['content']
        for full_tag, img_path, start, end in reversed(chunk_img_refs):
            desc = all_descriptions.get(img_path)
            if desc:
                # 查找正确的插入位置（如果有 caption，插入到 caption 之后）
                insert_pos = _find_caption_line_end(enhanced_content, end)

                # 使用 HTML <br> 标签实现换行（MathMarkdown 支持 HTML）
                enhancement = "<br>\n" + description_format.format(desc=desc) + "\n"
                enhanced_content = enhanced_content[:insert_pos] + enhancement + enhanced_content[insert_pos:]
                enhanced_count += 1

        enhanced_chunk = chunk.copy()
        enhanced_chunk['content'] = enhanced_content
        enhanced_chunks.append(enhanced_chunk)

    logger.info(f"图片视觉增强完成，共增强 {enhanced_count} 个图片")
    return enhanced_chunks
