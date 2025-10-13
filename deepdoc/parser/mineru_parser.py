#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import logging
import os
import re
import json
from io import BytesIO
from typing import List, Tuple
import requests


class MinerUParser:
    """
    MinerU PDF 解析器

    通过 HTTP 调用 KnowFlow Server 的 MinerU 服务进行 PDF 解析。
    返回格式与 PlainParser 保持一致，供 RAGFlow 分块方法使用。
    """

    def __init__(self):
        self.knowflow_server_url = os.getenv(
            'KNOWFLOW_API_URL',
            'http://localhost:5000'
        )
        self.timeout = int(os.getenv('MINERU_FASTAPI_TIMEOUT', '60000'))  

    def __call__(
        self,
        filename,
        from_page=0,
        to_page=100000,
        chunk_level='line',
        **kwargs
    ) -> Tuple[List[Tuple[str, str]], List]:
        """
        解析 PDF 文件

        Args:
            filename: PDF 文件路径或二进制数据
            from_page: 起始页码
            to_page: 结束页码
            chunk_level: 分块级别
                - 'semantic': 语义块级别（text/title 块不断句，用于 general 分块）
                - 'line': 逐行级别（保留所有行，用于 smart 分块）
            **kwargs: 额外参数

        Returns:
            Tuple[List[Tuple[str, str]], List]:
                - 第一项: [(text, position_tag), ...] 文本内容和坐标标签
                - 第二项: [] 空列表（保持接口一致性）
        """
        try:
            # 准备文件数据
            if isinstance(filename, str):
                with open(filename, 'rb') as f:
                    binary_data = f.read()
                file_name = os.path.basename(filename)
            else:
                binary_data = filename if isinstance(filename, bytes) else filename.read()
                file_name = kwargs.get('file_name', 'document.pdf')

            # 调用 KnowFlow Server MinerU API
            api_url = f"{self.knowflow_server_url}/api/parse/mineru"

            files = {'file': (file_name, BytesIO(binary_data), 'application/pdf')}
            data = {
                'from_page': from_page,
                'to_page': to_page,
            }

            # 传递 kb_id（用于生成图片相对路径）
            kb_id = kwargs.get('kb_id') or kwargs.get('knowledgebase_id') or ''
            data['kb_id'] = kb_id  # 总是传递，即使为空

            logging.info(f"Calling MinerU API: {api_url} (chunk_level={chunk_level})")
            response = requests.post(
                api_url,
                files=files,
                data=data,
                timeout=self.timeout
            )

            if response.status_code != 200:
                error_msg = f"MinerU API error: {response.status_code} - {response.text}"
                logging.error(error_msg)
                raise RuntimeError(error_msg)

            result = response.json()

            # 提取解析结果
            if 'error' in result:
                raise RuntimeError(f"MinerU parsing failed: {result['error']}")

            # API 返回 boxes（语义块）、markdown 和 coordinate_map
            boxes = result.get('boxes', [])
            markdown_text = result.get('markdown', '')
            coordinate_map = result.get('coordinate_map', {})

            if not boxes and not markdown_text:
                raise RuntimeError("MinerU API did not return valid data")

            # 开发模式：保存调试文件（如果 API 返回了 middle_json 说明开启了 dev_mode）
            dev_mode = 'middle_json' in result
            if dev_mode:
                # 获取项目根目录（deepdoc/parser/ -> ../../）
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                debug_dir = os.path.join(project_root, 'tmp', 'mineru_debug')
                os.makedirs(debug_dir, exist_ok=True)

                import time
                timestamp = int(time.time())

                # 保存 middle_json（如果 API 返回了）
                if 'middle_json' in result:
                    middle_json_file = os.path.join(debug_dir, f'{timestamp}_{file_name}_middle.json')
                    with open(middle_json_file, 'w', encoding='utf-8') as f:
                        json.dump(result['middle_json'], f, ensure_ascii=False, indent=2)
                    logging.info(f"[DEV] Saved middle.json to: {middle_json_file}")

                # 保存生成的 markdown
                markdown_file = os.path.join(debug_dir, f'{timestamp}_{file_name}_markdown.md')
                with open(markdown_file, 'w', encoding='utf-8') as f:
                    f.write(markdown_text)
                logging.info(f"[DEV] Saved markdown to: {markdown_file}")

                # 保存 coordinate_map
                if coordinate_map:
                    coord_file = os.path.join(debug_dir, f'{timestamp}_{file_name}_coordinate_map.json')
                    with open(coord_file, 'w', encoding='utf-8') as f:
                        json.dump(coordinate_map, f, ensure_ascii=False, indent=2)
                    logging.info(f"[DEV] Saved coordinate_map to: {coord_file}")

            # 转换为 RAGFlow 格式: [(text_with_tag, position_tag), ...]
            sections = []
            tables = []

            if chunk_level == 'semantic':
                # 语义块级别：使用 boxes（直接从 preproc_blocks 提取）
                # 将表格和文本分离，避免表格被 naive_merge 割裂
                logging.info("Using semantic blocks (preproc_blocks) from MinerU")

                for box in boxes:
                    text = box.get('text', '').strip()
                    if not text:
                        continue

                    page_num = box.get('page_number', 0)
                    x0 = box.get('x0', 0.0)
                    x1 = box.get('x1', 0.0)
                    top = box.get('top', 0.0)
                    bottom = box.get('bottom', 0.0)
                    layout_type = box.get('layout_type', 'text')

                    # 分离表格和图片（参照 DeepDOC pdf_parser.py:636-667）
                    if layout_type in ('table', 'image'):
                        # 表格/图片格式: ((img, html), [[page, x0, x1, top, bottom]])
                        # img 设为 None，html 为表格的文本内容
                        # 坐标是列表的列表，因为表格可能跨多个区域
                        coord = [page_num, x0, x1, top, bottom]
                        tables.append(((None, text), [coord]))
                    else:
                        # 文本/标题/列表：作为普通 section
                        # 末尾添加换行符，避免 naive_merge 拼接时连在一起
                        position_tag = f"@@{page_num}\t{x0:.1f}\t{x1:.1f}\t{top:.1f}\t{bottom:.1f}##"
                        text_with_tag = f"{position_tag}{text}\n"
                        # 返回 layout_type 作为 layoutno，用于 paper/book 等方法的标题识别
                        sections.append((text_with_tag, layout_type))

                logging.info(f"MinerU parsed {len(sections)} text sections and {len(tables)} tables from PDF")
                return sections, tables

            else:
                # 逐行级别：使用 markdown + coordinate_map（用于 smart 分块）
                logging.info("Using line-based markdown from MinerU")
                markdown_lines = markdown_text.split('\n')

                for line_idx, text in enumerate(markdown_lines):
                    coords = coordinate_map.get(str(line_idx)) or coordinate_map.get(line_idx)

                    if coords and len(coords) >= 5:
                        page_num, x0, x1, y0, y1 = coords[0], coords[1], coords[2], coords[3], coords[4]
                        position_tag = f"@@{page_num}\t{x0:.1f}\t{x1:.1f}\t{y0:.1f}\t{y1:.1f}##"
                    else:
                        position_tag = "@@0\t0.0\t0.0\t0.0\t0.0##"

                    # markdown 已经包含换行结构，保持原样
                    text_with_tag = f"{position_tag}{text}"
                    sections.append((text_with_tag, position_tag))

                logging.info(f"MinerU parsed {len(sections)} lines from PDF")
                return sections, []

        except requests.exceptions.Timeout:
            logging.error(f"MinerU API timeout after {self.timeout}s")
            raise RuntimeError(f"MinerU parsing timeout (>{self.timeout}s)")
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Cannot connect to KnowFlow Server: {e}")
            raise RuntimeError(f"Cannot connect to KnowFlow Server at {self.knowflow_server_url}")
        except Exception as e:
            logging.exception(f"MinerU parsing failed: {e}")
            raise

    def crop(self, ck, need_position):
        """
        从 chunk 文本中提取位置信息

        Args:
            ck: chunk 文本（可能包含位置标签）
            need_position: 是否需要返回位置信息

        Returns:
            (image, positions): 图片对象（None）和位置列表
        """
        if not need_position:
            return None, []

        # 提取所有位置标签
        pattern = r'@@(\d+)\t([\d.]+)\t([\d.]+)\t([\d.]+)\t([\d.]+)##'
        matches = re.findall(pattern, ck)

        positions = []
        for match in matches:
            page_num, x0, x1, top, bottom = match
            # 格式: [page_num, x0, x1, top, bottom]
            positions.append([
                int(page_num),
                float(x0),
                float(x1),
                float(top),
                float(bottom)
            ])

        # MinerU 不提供图片裁剪功能
        return None, positions if positions else [[0, 0, 0, 0, 0]]

    @staticmethod
    def remove_tag(txt):
        """移除位置标签"""
        return re.sub(r"@@[^#]+##", "", txt)
