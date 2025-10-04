#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import tempfile
from io import BytesIO
from flask import request, jsonify
from . import parse_bp
from services.knowledgebases.dots_parse.dots_fastapi_adapter import get_global_adapter
from services.knowledgebases.dots_parse.dots_processor import process_dots_result

@parse_bp.route('/api/parse/dots', methods=['POST'])
def parse_with_dots():
    """
    DOTS PDF 解析服务

    接收 PDF 文件，使用 DOTS 进行解析，返回 RAGFlow boxes 格式。

    Request:
        - file: PDF 文件（multipart/form-data）
        - from_page: 起始页码（可选，默认 0）
        - to_page: 结束页码（可选，默认 100000）
        - kb_id: 知识库 ID（可选）

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
            "markdown": "...",
            "coordinate_map": {...},
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
        kb_id = request.form.get('kb_id', '')

        # 保存上传的文件到临时目录
        temp_dir = tempfile.mkdtemp()
        temp_pdf_path = os.path.join(temp_dir, file.filename)

        file.save(temp_pdf_path)
        logging.info(f"Saved uploaded file to: {temp_pdf_path}")

        # 使用 DOTS 适配器解析
        adapter = get_global_adapter()

        # 将 PDF 转换为图像
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(temp_pdf_path, dpi=200)

            # 处理页面范围
            page_count = len(images)
            from_page = max(0, min(from_page, page_count - 1))
            to_page = min(to_page, page_count)

            # 只处理指定范围的页面
            images = images[from_page:to_page]

            document_results = []
            for page_num, image in enumerate(images):
                # 转换PIL图像为字节
                img_buffer = BytesIO()
                image.save(img_buffer, format='PNG')
                img_bytes = img_buffer.getvalue()

                # 调用DOTS VLLM API解析
                page_result = adapter.parse_image(img_bytes)
                page_result['page_number'] = from_page + page_num + 1
                page_result['source_type'] = 'pdf_page'
                page_result['page_image'] = image
                document_results.append(page_result)

                logging.info(f"Completed page {from_page + page_num + 1} parsing")

        except ImportError:
            return jsonify({'error': 'pdf2image library is required. Install with: pip install pdf2image'}), 500

        # 处理DOTS解析结果
        result = process_dots_result(
            document_results,
            kb_id=kb_id,
            temp_dir=temp_dir,
            chunking_config=None,  # 不分块，只解析
            doc_id=None
        )

        if not result.get('success', False):
            error_msg = result.get('error', 'Unknown error')
            logging.error(f"DOTS parsing failed: {error_msg}")
            return jsonify({'error': error_msg}), 500

        # 从processor获取数据
        processor = result.get('processor')
        if not processor:
            return jsonify({'error': 'No processor found in result'}), 500

        # 获取 markdown 和 coordinate_map
        markdown_text = result.get('markdown_content', '')
        coordinate_map = result.get('coordinate_map', {})

        # 转换为 boxes 格式
        boxes = _convert_dots_elements_to_boxes(processor.elements)

        # 清理临时文件
        try:
            import shutil
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as e:
            logging.warning(f"Failed to cleanup temp files: {e}")

        # 返回结果
        response = {
            'success': True,
            'boxes': boxes,
            'markdown': markdown_text,
            'coordinate_map': coordinate_map,
            'page_count': len(set(e.page_number for e in processor.elements)) if processor.elements else 0,
            'total_blocks': len(boxes)
        }

        # 开发模式：返回 dots_json（需要清理不可序列化的对象）
        from services.config import APP_CONFIG
        if APP_CONFIG.dev_mode and processor.pages_data:
            # 清理 pages_data 中的 PIL 图像对象
            clean_pages_data = []
            for page_data in processor.pages_data:
                clean_page = {k: v for k, v in page_data.items() if k != 'page_image'}
                clean_pages_data.append(clean_page)
            response['dots_json'] = clean_pages_data

        logging.info(f"DOTS parsed {len(boxes)} blocks from {response['page_count']} pages")
        return jsonify(response), 200

    except Exception as e:
        logging.exception(f"DOTS parsing failed: {e}")
        return jsonify({'error': str(e)}), 500


def _convert_dots_elements_to_boxes(elements):
    """
    将 DOTS 元素转换为 RAGFlow boxes 格式

    Args:
        elements: DOTS 元素列表

    Returns:
        List[dict]: RAGFlow boxes 格式的列表
    """
    boxes = []

    for element in elements:
        # DOTS bbox 格式: [x1, y1, x2, y2]
        if not element.bbox or len(element.bbox) < 4:
            continue

        # 映射 DOTS 类别到 layout_type
        layout_type_map = {
            'Text': 'text',
            'Title': 'title',
            'Section-header': 'title',
            'Table': 'table',
            'Picture': 'image',
            'Formula': 'formula',
            'List-item': 'list',
            'Caption': 'text',
            'Footnote': 'text',
            'Page-header': 'text',
            'Page-footer': 'text'
        }

        layout_type = layout_type_map.get(element.category, 'text')

        boxes.append({
            'text': element.text,
            'x0': float(element.bbox[0]),
            'x1': float(element.bbox[2]),
            'top': float(element.bbox[1]),
            'bottom': float(element.bbox[3]),
            'page_number': element.page_number - 1,  # DOTS 页码从 1 开始，转换为从 0 开始
            'layout_type': layout_type
        })

    return boxes
