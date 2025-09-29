#!/usr/bin/env python3
"""
使用 middle.json 替代 OCR markdown 的简单集成方案

使用方式：
1. 先将 middle.json 转换为 markdown
2. 使用现有的分块函数处理 markdown
3. 分块后查询每个分块的坐标
"""

from typing import List, Dict, Any, Tuple
from .middle_json_simple import middle_json_to_markdown, get_chunk_coordinates


def process_document_with_middle_json(middle_json_path: str,
                                     chunk_method: str = 'smart',
                                     chunk_token_num: int = 256,
                                     min_chunk_tokens: int = 10,
                                     **kwargs) -> Tuple[List[Dict], str]:
    """
    使用 middle.json 处理文档的完整流程

    Args:
        middle_json_path: middle.json 文件路径
        chunk_method: 分块方法 (smart/advanced/parent_child/basic等)
        chunk_token_num: 目标分块大小
        min_chunk_tokens: 最小分块大小
        **kwargs: 其他分块参数

    Returns:
        (分块列表带坐标, markdown内容)
    """

    # 1. 将 middle.json 转换为 markdown（替代OCR markdown）
    output_md_path = middle_json_path.replace('_middle.json', '_from_middle.md')
    markdown_content = middle_json_to_markdown(middle_json_path, output_md_path)

    print(f"✅ 已将 middle.json 转换为 markdown: {output_md_path}")

    # 2. 使用现有的分块函数（无需修改）
    from .utils import split_markdown_to_chunks_configured

    chunking_config = kwargs.get('chunking_config', {})
    chunking_config['strategy'] = chunk_method

    chunks = split_markdown_to_chunks_configured(
        markdown_content,
        chunk_token_num=chunk_token_num,
        min_chunk_tokens=min_chunk_tokens,
        chunking_config=chunking_config,
        **kwargs
    )

    # 3. 为每个分块添加坐标信息
    chunks_with_coords = []

    if isinstance(chunks, dict) and 'parent_chunks' in chunks:
        # 父子分块格式
        result = {
            'parent_chunks': [],
            'child_chunks': [],
            'relationships': chunks.get('relationships', [])
        }

        # 处理父分块
        for parent in chunks['parent_chunks']:
            parent_text = parent.get('content', parent.get('text', ''))
            coords = get_chunk_coordinates(output_md_path, parent_text)
            parent['coordinates'] = coords
            result['parent_chunks'].append(parent)

        # 处理子分块
        for child in chunks['child_chunks']:
            child_text = child.get('content', child.get('text', ''))
            coords = get_chunk_coordinates(output_md_path, child_text)
            child['coordinates'] = coords
            result['child_chunks'].append(child)

        chunks_with_coords = result

    elif isinstance(chunks, list):
        # 普通分块格式
        for chunk in chunks:
            if isinstance(chunk, dict):
                chunk_text = chunk.get('content', chunk.get('text', ''))
            else:
                chunk_text = str(chunk)

            # 查询坐标
            coords = get_chunk_coordinates(output_md_path, chunk_text)

            # 创建带坐标的分块
            if isinstance(chunk, dict):
                chunk['coordinates'] = coords
                chunks_with_coords.append(chunk)
            else:
                chunks_with_coords.append({
                    'content': chunk_text,
                    'coordinates': coords
                })

    print(f"✅ 已为 {len(chunks_with_coords)} 个分块添加坐标信息")

    return chunks_with_coords, markdown_content


def example_usage():
    """使用示例"""

    # 示例1：使用智能分块
    chunks, markdown = process_document_with_middle_json(
        middle_json_path="/path/to/document_middle.json",
        chunk_method='smart',
        chunk_token_num=256
    )

    # 示例2：使用父子分块
    chunks, markdown = process_document_with_middle_json(
        middle_json_path="/path/to/document_middle.json",
        chunk_method='parent_child',
        chunk_token_num=256,
        chunking_config={
            'strategy': 'parent_child',
            'parent_config': {
                'parent_chunk_size': 512,
                'child_chunk_size': 256
            }
        },
        doc_id='doc_001',
        kb_id='kb_001'
    )

    # 示例3：使用高级分块
    chunks, markdown = process_document_with_middle_json(
        middle_json_path="/path/to/document_middle.json",
        chunk_method='advanced',
        chunk_token_num=256,
        overlap_ratio=0.1
    )

    return chunks


if __name__ == "__main__":
    # 测试
    import sys
    if len(sys.argv) > 1:
        middle_json_path = sys.argv[1]
        chunks, markdown = process_document_with_middle_json(
            middle_json_path,
            chunk_method='smart'
        )

        print(f"\n📊 分块结果:")
        for i, chunk in enumerate(chunks[:3], 1):
            if isinstance(chunk, dict):
                print(f"\n分块 {i}:")
                print(f"  内容: {chunk.get('content', '')[:100]}...")
                print(f"  坐标数: {len(chunk.get('coordinates', []))}")
                if chunk.get('coordinates'):
                    coord = chunk['coordinates'][0]
                    print(f"  第一个坐标: 页面{int(coord[0])+1}, [{coord[1]:.0f},{coord[2]:.0f},{coord[3]:.0f},{coord[4]:.0f}]")