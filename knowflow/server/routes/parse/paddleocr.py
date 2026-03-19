#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import tempfile
from flask import request, jsonify
from . import parse_bp
from services.knowledgebases.paddleocr_parse import (
    PaddleOCRClient,
    OCRToMiddleJsonConverter
)
from services.knowledgebases.mineru_parse.middle_json_simple import (
    SimpleMiddleJsonConverter
)


@parse_bp.route('/api/parse/paddleocr', methods=['POST'])
def parse_with_paddleocr():
    """
    PaddleOCR PDF 解析服务

    接收 PDF 文件，使用 PaddleOCR 进行 OCR，返回 RAGFlow boxes 格式。

    PaddleOCR 支持直接识别 PDF（fileType=0），无需转换为图片。

    Request:
        - file: PDF 文件（multipart/form-data）
        - from_page: 起始页码（可选，默认 0，暂未实现分页）
        - to_page: 结束页码（可选，默认 100000，暂未实现分页）
        - kb_id: 知识库ID（可选）

    Response:
        {
            "success": true,
            "boxes": [
                {
                    "text": "...",
                    "x0": 0, "x1": 100, "top": 0, "bottom": 20,
                    "page_number": 0,
                    "layout_type": "text"
                }
            ],
            "markdown": "完整 markdown 文本",
            "coordinate_map": {
                "0": [0, 100, 500, 200, 300],
                ...
            },
            "page_count": 10,
            "total_blocks": 150
        }
    """
    temp_pdf_path = None
    temp_dir = None

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

        # Step 1: 读取 PDF 二进制
        with open(temp_pdf_path, 'rb') as f:
            pdf_binary = f.read()

        # Step 2: 调用 PaddleOCR 直接识别 PDF
        logging.info(f"Calling PaddleOCR for PDF (fileType=0)...")
        ocr_client = PaddleOCRClient()
        ocr_result = ocr_client.recognize_pdf(pdf_binary, timeout=600)

        if not ocr_result:
            logging.error("PaddleOCR failed to recognize PDF")
            return jsonify({
                'error': 'PaddleOCR failed to recognize PDF'
            }), 500

        page_count = ocr_result.get('page_count', 0)
        total_blocks = len(ocr_result.get('blocks', []))
        images = ocr_result.get('images', {})

        logging.info(
            f"PaddleOCR recognized {page_count} pages, "
            f"{total_blocks} blocks, "
            f"{len(images)} images"
        )

        # Step 3: 转换为 pseudo-middle.json
        logging.info("Converting OCR result to pseudo-middle.json...")
        ocr_converter = OCRToMiddleJsonConverter(kb_id=kb_id)
        pseudo_middle_json = ocr_converter.convert(ocr_result)

        # 获取统计信息
        stats = ocr_converter.get_statistics(pseudo_middle_json)
        logging.info(
            f"Converted to pseudo-middle.json: "
            f"{stats['total_pages']} pages, {stats['total_blocks']} blocks"
        )

        # Step 4: 处理图片（如果有）
        if images and kb_id:
            try:
                import base64
                import shutil
                from services.knowledgebases.mineru_parse.minio_server import upload_directory_to_minio

                # 创建临时目录保存图片
                images_dir = tempfile.mkdtemp(prefix='paddleocr_images_')
                logging.info(f"Saving {len(images)} images to temporary directory: {images_dir}")

                # 保存图片到临时目录
                saved_count = 0
                for image_name, image_data in images.items():
                    try:
                        # 提取 base64 数据
                        if image_data.startswith('data:image/'):
                            base64_data = image_data.split(',', 1)[1]
                        else:
                            base64_data = image_data

                        # 解码并保存图片
                        image_bytes = base64.b64decode(base64_data)

                        # 只保留文件名，去掉路径部分（如 imgs/）
                        clean_image_name = os.path.basename(image_name)
                        image_path = os.path.join(images_dir, clean_image_name)

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

                # 清理临时目录
                shutil.rmtree(images_dir)

            except Exception as e:
                logging.warning(f"Failed to process images: {e}")

        # Step 5: 使用 SimpleMiddleJsonConverter 生成两种格式
        logging.info("Generating markdown and coordinate_map...")

        # 5.1 语义块级别（merge_text_lines=True，用于 boxes）
        converter_semantic = SimpleMiddleJsonConverter(
            kb_id=kb_id,
            merge_text_lines=True
        )

        block_pages_semantic = []
        for page_data in pseudo_middle_json['pdf_info']:
            blocks = converter_semantic._extract_blocks_from_page(
                page_data, page_data['page_idx']
            )
            block_pages_semantic.append(blocks)

        markdown_lines_semantic, coordinate_map_semantic = \
            converter_semantic._build_markdown_from_block_pages(
                block_pages_semantic
            )

        # 5.2 逐行级别（merge_text_lines=False，用于 smart chunking）
        converter_line = SimpleMiddleJsonConverter(
            kb_id=kb_id,
            merge_text_lines=False
        )

        block_pages_line = []
        for page_data in pseudo_middle_json['pdf_info']:
            blocks = converter_line._extract_blocks_from_page(
                page_data, page_data['page_idx']
            )
            block_pages_line.append(blocks)

        markdown_lines_line, coordinate_map_line = \
            converter_line._build_markdown_from_block_pages(
                block_pages_line
            )

        # 5.3 生成 boxes（从语义块 markdown 生成）
        boxes = _build_semantic_boxes_from_markdown(
            markdown_lines_semantic,
            coordinate_map_semantic
        )

        # 5.4 使用逐行 markdown 作为最终输出
        markdown_text = '\n'.join(markdown_lines_line)

        # Step 6: 替换 Markdown 中的图片路径为 MinIO URL
        if images and kb_id:
            import re

            def replace_image_path(match):
                """替换图片路径为 MinIO URL"""
                img_path = match.group(1)
                # 如果已经是完整 URL，不处理
                if img_path.startswith(('http://', 'https://', '/minio/')):
                    return match.group(0)
                # 提取图片文件名
                img_name = os.path.basename(img_path)
                # 替换为 MinIO 路径
                new_path = f"/minio/{kb_id}/{img_name}"
                return f'![{match.group(2)}]({new_path})'

            # 替换 Markdown 图片语法 ![alt](path)
            markdown_text = re.sub(
                r'!\[([^\]]*)\]\(([^)]+)\)',
                lambda m: f'![{m.group(1)}](/minio/{kb_id}/{os.path.basename(m.group(2))})',
                markdown_text
            )

            # 替换 HTML img 标签
            markdown_text = re.sub(
                r'<img\s+src="([^"]+)"',
                lambda m: f'<img src="/minio/{kb_id}/{os.path.basename(m.group(1))}"',
                markdown_text
            )

            logging.info(f"Replaced image paths with MinIO URLs")

        logging.info(
            f"Generated {len(boxes)} boxes and {len(coordinate_map_line)} "
            f"coordinate entries"
        )

        # Step 7: 返回结果
        response = {
            'success': True,
            'boxes': boxes,
            'markdown': markdown_text,
            'coordinate_map': coordinate_map_line,
            'page_count': stats['total_pages'],
            'total_blocks': stats['total_blocks'],
            'block_types': stats['block_types']
        }

        # 开发模式：返回 pseudo-middle.json
        from services.config import APP_CONFIG
        if APP_CONFIG.dev_mode:
            response['pseudo_middle_json'] = pseudo_middle_json

        logging.info(
            f"PaddleOCR parsed {len(boxes)} boxes from "
            f"{response['page_count']} pages"
        )
        return jsonify(response), 200

    except Exception as e:
        logging.exception(f"PaddleOCR parsing failed: {e}")
        return jsonify({'error': str(e)}), 500

    finally:
        # 清理临时文件
        try:
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            if temp_dir and os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            logging.warning(f"Failed to cleanup temp files: {e}")


def _build_semantic_boxes_from_markdown(markdown_lines, coordinate_map):
    """
    从格式化的 markdown 生成语义块级别的 boxes（用于 general 分块）

    Args:
        markdown_lines: 格式化的 markdown 行列表（包含 #、表格HTML等）
        coordinate_map: 坐标映射 {line_idx: [page, x0, x1, y0, y1]}

    Returns:
        List[dict]: 语义块级别的 boxes 列表
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
        # 判断块类型（基于 markdown 格式）
        layout_type = 'text'
        stripped = line_text.strip()
        if stripped.startswith('#'):
            layout_type = 'title'
        elif stripped.startswith('<table'):
            layout_type = 'table'
        elif stripped.startswith('<img'):
            layout_type = 'image'
        elif stripped.startswith('-') or stripped.startswith('*'):
            layout_type = 'list'

        boxes.append({
            'text': line_text,
            'x0': float(coords[1]),
            'x1': float(coords[2]),
            'top': float(coords[3]),
            'bottom': float(coords[4]),
            'page_number': coords[0],
            'layout_type': layout_type
        })

    return boxes
