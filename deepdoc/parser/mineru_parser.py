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
            'KNOWFLOW_SERVER_URL',
            'http://localhost:5000'
        )
        self.timeout = int(os.getenv('MINERU_PARSE_TIMEOUT', '300'))  # 5分钟超时

    def __call__(
        self,
        filename,
        from_page=0,
        to_page=100000,
        **kwargs
    ) -> Tuple[List[Tuple[str, str]], List]:
        """
        解析 PDF 文件

        Args:
            filename: PDF 文件路径或二进制数据
            from_page: 起始页码
            to_page: 结束页码
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
                'return_format': 'ragflow_boxes',  # 返回 RAGFlow boxes 格式
            }

            # 传递 kb_id（用于生成图片相对路径）
            kb_id = kwargs.get('kb_id') or kwargs.get('knowledgebase_id') or ''
            data['kb_id'] = kb_id  # 总是传递，即使为空

            logging.info(f"Calling MinerU API: {api_url}")
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

            boxes = result.get('boxes', [])

            # 转换为 RAGFlow 格式: [(text_with_tag, position_tag), ...]
            lines = []
            for box in boxes:
                text = box.get('text', '').strip()
                if not text:
                    continue

                # text 已经在 API 中完成格式化（标题有 #，列表有 -）

                # 生成 position_tag
                # 格式: @@page-seq\tleft\tright\ttop\tbottom##
                page_num = box.get('page_number', 0)
                x0 = box.get('x0', 0)
                x1 = box.get('x1', 0)
                top = box.get('top', 0)
                bottom = box.get('bottom', 0)

                position_tag = f"@@{page_num}\t{x0:.1f}\t{x1:.1f}\t{top:.1f}\t{bottom:.1f}##"

                # 将位置标签嵌入到文本中，供 smart.py 提取坐标
                text_with_tag = f"{position_tag}{text}"

                lines.append((text_with_tag, position_tag))

            logging.info(f"MinerU parsed {len(lines)} text blocks from PDF")
            return lines, []

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
        import re
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
        import re
        return re.sub(r"@@[^#]+##", "", txt)
