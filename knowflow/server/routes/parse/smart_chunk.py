#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
from flask import request, jsonify
from . import parse_bp
from services.knowledgebases.mineru_parse.utils import split_markdown_to_chunks_configured
from services.knowledgebases.common.image_vision_enhancer import enhance_chunks_with_vision


@parse_bp.route('/api/parse/smart_chunk', methods=['POST'])
def smart_chunk():
    """
    智能分块服务

    提供基于 middle.json 的智能分块功能，供 RAGFlow 调用。

    Request (JSON):
        {
            "markdown_text": "...",  # markdown 文本
            "coordinate_map": {       # 坐标映射 (可选)
                "0": [page, x1, x2, y1, y2],
                ...
            },
            "chunking_config": {      # 分块配置
                "strategy": "smart",  # smart/advanced/parent_child/basic
                "chunk_token_num": 256,
                "min_chunk_tokens": 10,
                ...
            }
        }

    Response (JSON):
        {
            "success": true,
            "chunks": [
                {
                    "content": "chunk text",
                    "positions": [[page, x1, x2, y1, y2], ...]  # 坐标列表
                },
                ...
            ],
            "total_chunks": 10,
            "strategy_used": "smart"
        }
    """
    try:
        # 解析请求
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        markdown_text = data.get('markdown_text', '')
        if not markdown_text:
            return jsonify({'error': 'markdown_text is required'}), 400

        # 获取坐标映射（可选）
        coordinate_map = data.get('coordinate_map')
        if coordinate_map and isinstance(coordinate_map, dict):
            # 将键转换为整数（JSON 键默认是字符串）
            coordinate_map = {int(k): v for k, v in coordinate_map.items()}

        # 获取分块配置
        chunking_config = data.get('chunking_config', {})
        if not isinstance(chunking_config, dict):
            chunking_config = {}

        # 设置默认值
        strategy = chunking_config.get('strategy', 'smart')
        chunk_token_num = chunking_config.get('chunk_token_num', 256)
        min_chunk_tokens = chunking_config.get('min_chunk_tokens', 10)

        logging.info(f"Smart chunking: strategy={strategy}, chunk_token_num={chunk_token_num}")

        # 调用智能分块函数（基于原始 markdown，完成坐标映射）
        chunks = split_markdown_to_chunks_configured(
            markdown_text,
            chunk_token_num=chunk_token_num,
            min_chunk_tokens=min_chunk_tokens,
            coordinate_map=coordinate_map,
            chunking_config=chunking_config,
            doc_id=data.get('doc_id', 'unknown'),
            kb_id=data.get('kb_id', 'unknown'),
            tenant_id=data.get('tenant_id', 'unknown')
        )

        # 图片视觉增强（在分块和坐标映射之后进行，不影响坐标）
        if data.get('enable_vision_enhancement', False):
            chunks = enhance_chunks_with_vision(
                chunks,
                tenant_id=data.get('tenant_id', 'unknown'),
                description_format=data.get('vision_description_format', '[图片描述]: {desc}'),
                batch_size=data.get('vision_batch_size')  # 支持配置批量大小
            )
            logging.info("图片视觉增强处理完成")
        else:
            logging.info("图片视觉增强已跳过（未启用）")

        # 处理返回结果
        def process_chunk(chunk):
            if isinstance(chunk, dict):
                result = {
                    'content': chunk.get('content', ''),
                    'positions': chunk.get('coordinates', chunk.get('positions', []))
                }
                if 'id' in chunk:
                    result['id'] = chunk['id']
                return result
            else:
                return {'content': str(chunk), 'positions': []}

        result_chunks = [process_chunk(chunk) for chunk in chunks] if isinstance(chunks, list) else []

        # 返回结果
        response = {
            'success': True,
            'chunks': result_chunks,
            'total_chunks': len(result_chunks),
            'strategy_used': strategy
        }

        logging.info(f"Smart chunking completed: {len(result_chunks)} chunks")
        return jsonify(response), 200

    except Exception as e:
        logging.exception(f"Smart chunking failed: {e}")
        return jsonify({'error': str(e)}), 500
