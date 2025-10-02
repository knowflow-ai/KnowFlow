#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import tempfile
from flask import request, jsonify
from . import parse_bp
from services.knowledgebases.mineru_parse.fastapi_adapter import get_global_adapter


@parse_bp.route('/api/parse/mineru', methods=['POST'])
def parse_with_mineru():
    """
    MinerU PDF 解析服务

    接收 PDF 文件，使用 MinerU 进行解析，返回 RAGFlow boxes 格式。

    Request:
        - file: PDF 文件（multipart/form-data）
        - from_page: 起始页码（可选，默认 0）
        - to_page: 结束页码（可选，默认 100000）
        - return_format: 返回格式（可选，默认 ragflow_boxes）

    Response:
        {
            "success": true,
            "boxes": [
                {
                    "text": "...",
                    "x0": 0, "x1": 100, "top": 0, "bottom": 20,
                    "page_number": 0,
                    "layout_type": "text"  # text/title/table/figure
                }
            ],
            "page_count": 10,
            "total_blocks": 150
        }
    """
    try:
        # 检查文件是否上传
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400

        # 获取参数
        from_page = int(request.form.get('from_page', 0))
        to_page = int(request.form.get('to_page', 100000))
        return_format = request.form.get('return_format', 'ragflow_boxes')

        # 保存上传的文件到临时目录
        temp_dir = tempfile.mkdtemp()
        temp_pdf_path = os.path.join(temp_dir, file.filename)

        file.save(temp_pdf_path)
        logging.info(f"Saved uploaded file to: {temp_pdf_path}")

        # 使用 MinerU FastAPI 适配器解析
        adapter = get_global_adapter()
        result = adapter.process_file(
            file_path=temp_pdf_path,
            return_middle_json=True,
            return_images=False  # 暂不返回图片，减少数据传输
        )

        # 获取解析结果
        result_doc_id = list(result['results'].keys())[0]
        doc_result = result['results'][result_doc_id]

        # 提取 middle_json
        middle_json_data = doc_result.get('middle_json')
        if isinstance(middle_json_data, str):
            middle_json_data = json.loads(middle_json_data)

        # 转换为 RAGFlow boxes 格式
        boxes = _convert_to_ragflow_boxes(middle_json_data, from_page, to_page)

        # 清理临时文件
        try:
            os.remove(temp_pdf_path)
            os.rmdir(temp_dir)
        except Exception as e:
            logging.warning(f"Failed to cleanup temp files: {e}")

        # 返回结果
        response = {
            'success': True,
            'boxes': boxes,
            'page_count': len(set(box['page_number'] for box in boxes)),
            'total_blocks': len(boxes)
        }

        logging.info(f"MinerU parsed {len(boxes)} blocks from {response['page_count']} pages")
        return jsonify(response), 200

    except Exception as e:
        logging.exception(f"MinerU parsing failed: {e}")
        return jsonify({'error': str(e)}), 500


def _convert_to_ragflow_boxes(middle_json, from_page, to_page):
    """
    将 MinerU middle.json 转换为 RAGFlow boxes 格式

    Args:
        middle_json: MinerU 的 middle.json 数据
        from_page: 起始页码
        to_page: 结束页码

    Returns:
        List[dict]: RAGFlow boxes 格式的列表
    """
    boxes = []

    if not middle_json or 'pdf_info' not in middle_json:
        logging.warning("Invalid middle.json structure")
        return boxes

    pdf_info = middle_json['pdf_info']

    for page_idx, page_data in enumerate(pdf_info):
        # 跳过不在范围内的页
        if page_idx < from_page or page_idx >= to_page:
            continue

        page_number = page_idx

        # 处理布局块（优先使用 para_blocks，其次使用 preproc_blocks）
        # VLM 模式使用 para_blocks，Pipeline 模式使用 preproc_blocks
        blocks_data = page_data.get('para_blocks') or page_data.get('preproc_blocks', [])
        for block in blocks_data:
            box = _convert_block_to_box(block, page_number)
            if box:
                boxes.append(box)

    return boxes


def _convert_block_to_box(block, page_number):
    """
    将 MinerU block 转换为 RAGFlow box

    Args:
        block: MinerU block 数据
        page_number: 页码

    Returns:
        dict: RAGFlow box 格式
    """
    try:
        # 提取文本
        text = ''

        # 方式1: 从 lines/spans 结构提取（VLM 和 Pipeline 模式）
        text_lines = block.get('lines', [])
        if text_lines:
            text = '\n'.join([
                ''.join([span.get('content', span.get('text', '')) for span in line.get('spans', [])])
                for line in text_lines
            ]).strip()

        # 方式2: 直接从 text 字段获取（某些简化格式）
        if not text and 'text' in block:
            text = block['text'].strip()

        # 如果没有文本内容，跳过此块
        if not text:
            return None

        # 提取坐标（72 DPI PDF 坐标）
        bbox = block.get('bbox', [0, 0, 0, 0])
        x0, y0, x1, y1 = bbox

        # 确定布局类型
        block_type = block.get('type', 'text')
        layout_type_map = {
            'text': 'text',
            'title': 'title',
            'table': 'table',
            'image': 'figure',
            'figure': 'figure'
        }
        layout_type = layout_type_map.get(block_type.lower(), 'text')

        box = {
            'text': text,
            'x0': float(x0),
            'x1': float(x1),
            'top': float(y0),
            'bottom': float(y1),
            'page_number': page_number,
            'layout_type': layout_type
        }

        return box

    except Exception as e:
        logging.warning(f"Failed to convert block to box: {e}")
        return None
