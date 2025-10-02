#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import tempfile
import base64
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
        kb_id = request.form.get('kb_id', '')

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
            return_images=True  # 需要返回图片
        )

        # 获取解析结果
        result_doc_id = list(result['results'].keys())[0]
        doc_result = result['results'][result_doc_id]

        # 提取 middle_json
        middle_json_data = doc_result.get('middle_json')
        if isinstance(middle_json_data, str):
            middle_json_data = json.loads(middle_json_data)

        # 转换为 RAGFlow boxes 格式，同时获取 markdown 和 coordinate_map
        boxes, markdown_text, coordinate_map = _convert_to_ragflow_boxes(middle_json_data, from_page, to_page, kb_id)

        # 上传图片到 MinIO（参照 process_pdf.py 逻辑）
        if kb_id and 'images' in doc_result and doc_result['images']:
            try:
                from services.knowledgebases.mineru_parse.minio_server import upload_directory_to_minio

                # 创建临时目录保存图片
                images_dir = tempfile.mkdtemp(prefix='mineru_images_')
                logging.info(f"Saving images to temporary directory: {images_dir}")

                # 保存图片到临时目录（参照 process_pdf.py:_save_images_from_result）
                saved_count = 0
                for image_name, image_data in doc_result['images'].items():
                    try:
                        # 提取 base64 数据
                        if image_data.startswith('data:image/'):
                            base64_data = image_data.split(',', 1)[1]
                        else:
                            base64_data = image_data

                        # 解码并保存图片
                        image_bytes = base64.b64decode(base64_data)
                        image_path = os.path.join(images_dir, image_name)

                        with open(image_path, 'wb') as f:
                            f.write(image_bytes)

                        saved_count += 1
                    except Exception as e:
                        logging.warning(f"Failed to save image {image_name}: {e}")

                logging.info(f"Saved {saved_count} images to {images_dir}")

                # 上传到 MinIO
                if saved_count > 0:
                    logging.info(f"Uploading {saved_count} images to MinIO bucket {kb_id}")
                    upload_directory_to_minio(kb_id, images_dir)
                    logging.info(f"Images uploaded successfully")

            except Exception as e:
                logging.warning(f"Failed to process images: {e}")

        # 清理临时文件
        try:
            os.remove(temp_pdf_path)
            os.rmdir(temp_dir)
        except Exception as e:
            logging.warning(f"Failed to cleanup temp files: {e}")

        # 返回结果
        response = {
            'success': True,
            'boxes': boxes,  # 保持兼容性
            'markdown': markdown_text,  # 新增：完整 markdown
            'coordinate_map': coordinate_map,  # 新增：坐标映射
            'page_count': len(set(box['page_number'] for box in boxes)) if boxes else 0,
            'total_blocks': len(boxes)
        }

        # 开发模式：返回 middle_json
        from services.config import APP_CONFIG
        if APP_CONFIG.dev_mode:
            response['middle_json'] = middle_json_data

        logging.info(f"MinerU parsed {len(boxes)} blocks from {response['page_count']} pages")
        return jsonify(response), 200

    except Exception as e:
        logging.exception(f"MinerU parsing failed: {e}")
        return jsonify({'error': str(e)}), 500


def _convert_to_ragflow_boxes(middle_json, from_page, to_page, kb_id=''):
    """
    将 MinerU middle.json 转换为 markdown + coordinate_map

    使用 SimpleMiddleJsonConverter 生成标准 markdown 和坐标映射。
    boxes 格式仅用于向后兼容。

    Args:
        middle_json: MinerU 的 middle.json 数据
        from_page: 起始页码
        to_page: 结束页码
        kb_id: 知识库ID，用于生成图片路径

    Returns:
        Tuple[List[dict], str, dict]: (boxes列表[兼容], markdown文本, coordinate_map)
    """
    try:
        from services.knowledgebases.mineru_parse.middle_json_simple import SimpleMiddleJsonConverter

        # 创建转换器实例
        converter = SimpleMiddleJsonConverter(kb_id=kb_id)

        # 提取页面范围内的 block_pages
        if not middle_json or 'pdf_info' not in middle_json:
            logging.warning("Invalid middle.json structure")
            return []

        pdf_info = middle_json['pdf_info']
        block_pages = []

        for page_idx, page_data in enumerate(pdf_info):
            # 跳过不在范围内的页
            if page_idx < from_page or page_idx >= to_page:
                continue

            # 提取并处理块（复用 converter._extract_blocks_from_page）
            blocks = converter._extract_blocks_from_page(page_data, page_idx)
            # 按 y 坐标排序
            blocks.sort(key=lambda b: b['bbox'][1] if len(b['bbox']) > 1 else 0)
            block_pages.append(blocks)

        # 生成 markdown 和坐标映射（核心功能）
        markdown_lines, coordinate_map = converter._build_markdown_from_block_pages(block_pages)
        markdown_text = '\n'.join(markdown_lines)

        # 生成 boxes 格式（向后兼容，实际使用 markdown + coordinate_map）
        boxes = _build_boxes_for_compatibility(markdown_lines, coordinate_map)

        return boxes, markdown_text, coordinate_map

    except Exception as e:
        logging.exception(f"Failed to convert middle.json to markdown: {e}")
        return [], '', {}


def _build_boxes_for_compatibility(markdown_lines, coordinate_map):
    """
    从 markdown_lines 和 coordinate_map 生成 boxes 格式（向后兼容）

    Args:
        markdown_lines: markdown 行列表
        coordinate_map: 坐标映射 {line_idx: [page, x0, x1, y0, y1]}

    Returns:
        List[dict]: boxes 列表
    """
    boxes = []
    for line_idx, line_text in enumerate(markdown_lines):
        # 跳过空行
        if not line_text.strip():
            continue

        # 获取该行的坐标
        coords = coordinate_map.get(line_idx)
        if not coords or len(coords) < 5:
            continue

        # coords 格式: [page_idx, x0, x1, y0, y1]
        boxes.append({
            'text': line_text,
            'x0': float(coords[1]),
            'x1': float(coords[2]),
            'top': float(coords[3]),
            'bottom': float(coords[4]),
            'page_number': coords[0],
            'layout_type': 'text'
        })

    return boxes
