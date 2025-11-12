"""
PaddleOCR API 客户端

提供调用 PaddleOCR 服务的统一接口
支持图片和 PDF 直接识别
"""

import requests
import base64
import logging
from typing import Optional, Dict, Any


class PaddleOCRClient:
    """PaddleOCR API 客户端"""

    def __init__(self, api_url: str = "http://8.134.177.47:15003"):
        """
        初始化客户端

        Args:
            api_url: PaddleOCR 服务地址
        """
        self.api_url = api_url
        self.endpoint = f"{api_url}/layout-parsing"
        self.logger = logging.getLogger(__name__)

    def recognize_pdf(
        self,
        pdf_binary: bytes,
        timeout: int = 600
    ) -> Optional[Dict[str, Any]]:
        """
        识别 PDF 文件（支持多页）

        Args:
            pdf_binary: PDF 二进制数据
            timeout: 请求超时时间（秒），默认 10 分钟

        Returns:
            {
                "markdown": str,
                "blocks": [
                    {
                        "block_label": str,
                        "block_content": str,
                        "block_bbox": [x0, y0, x1, y1],
                        "block_id": int,
                        "block_order": int
                    },
                    ...
                ],
                "images": {},
                "model_settings": {...},
                "page_count": int  # PDF 页数
            }
            失败返回 None
        """
        try:
            # 转换为 base64
            base64_data = base64.b64encode(pdf_binary).decode('utf-8')

            # 调用 API
            self.logger.info(f"Calling PaddleOCR API for PDF: {self.endpoint}")
            response = requests.post(
                self.endpoint,
                json={
                    'file': base64_data,
                    'fileType': 0  # 0 = PDF
                },
                timeout=timeout
            )

            if response.status_code != 200:
                self.logger.error(
                    f"PaddleOCR API returned status {response.status_code}"
                )
                return None

            result = response.json()

            # 检查错误码
            if result.get('errorCode') != 0:
                self.logger.error(
                    f"PaddleOCR API error: {result.get('errorMsg')}"
                )
                return None

            # 提取数据
            layout_results = result.get('result', {}).get(
                'layoutParsingResults', []
            )
            if not layout_results:
                self.logger.error("No layoutParsingResults in response")
                return None

            # PaddleOCR 对 PDF 返回多页结果
            all_blocks = []
            all_markdown_parts = []
            all_images = {}  # 收集所有页面的图片

            for page_idx, layout_result in enumerate(layout_results):
                # 提取 markdown 文本
                markdown_data = layout_result.get('markdown', {})
                markdown_text = markdown_data.get('text', '')
                all_markdown_parts.append(markdown_text)

                # 提取图片
                page_images = markdown_data.get('images', {})
                if page_images:
                    self.logger.info(f"Page {page_idx} has {len(page_images)} images")
                    for img_name in list(page_images.keys())[:2]:
                        self.logger.info(f"  - Image: {img_name}")
                    all_images.update(page_images)
                else:
                    self.logger.debug(f"Page {page_idx} has no images")

                # 提取结构化数据
                pruned_result = layout_result.get('prunedResult', {})
                blocks = pruned_result.get('parsing_res_list', [])

                # 为每个块添加页码
                for block in blocks:
                    block['page_idx'] = page_idx
                    all_blocks.append(block)

            # 合并所有页面的 markdown
            full_markdown = '\n\n'.join(all_markdown_parts)

            # 获取模型设置（从第一页）
            first_pruned = layout_results[0].get('prunedResult', {})
            model_settings = first_pruned.get('model_settings', {})

            self.logger.info(
                f"PaddleOCR recognized {len(layout_results)} pages, "
                f"{len(all_blocks)} total blocks, "
                f"{len(all_images)} images"
            )

            return {
                'markdown': full_markdown,
                'blocks': all_blocks,
                'images': all_images,  # 返回实际的图片数据
                'model_settings': model_settings,
                'page_count': len(layout_results)
            }

        except requests.exceptions.Timeout:
            self.logger.error(f"PaddleOCR API timeout")
            return None
        except Exception as e:
            self.logger.error(f"PaddleOCR API error: {e}", exc_info=True)
            return None

    def recognize_pdf_from_path(
        self,
        pdf_path: str,
        timeout: int = 600
    ) -> Optional[Dict[str, Any]]:
        """
        识别 PDF 文件

        Args:
            pdf_path: PDF 文件路径
            timeout: 请求超时时间（秒）

        Returns:
            识别结果，失败返回 None
        """
        try:
            with open(pdf_path, 'rb') as f:
                pdf_binary = f.read()
            return self.recognize_pdf(pdf_binary, timeout)
        except Exception as e:
            self.logger.error(
                f"Failed to read PDF from {pdf_path}: {e}",
                exc_info=True
            )
            return None

    def recognize_image(
        self,
        image_binary: bytes,
        timeout: int = 120
    ) -> Optional[Dict[str, Any]]:
        """
        识别单张图片

        Args:
            image_binary: 图片二进制数据
            timeout: 请求超时时间（秒）

        Returns:
            识别结果，失败返回 None
        """
        try:
            # 转换为 base64
            base64_data = base64.b64encode(image_binary).decode('utf-8')

            # 调用 API
            self.logger.debug(f"Calling PaddleOCR API for image: {self.endpoint}")
            response = requests.post(
                self.endpoint,
                json={
                    'file': base64_data,
                    'fileType': 1  # 1 = 图像
                },
                timeout=timeout
            )

            if response.status_code != 200:
                self.logger.error(
                    f"PaddleOCR API returned status {response.status_code}"
                )
                return None

            result = response.json()

            # 检查错误码
            if result.get('errorCode') != 0:
                self.logger.error(
                    f"PaddleOCR API error: {result.get('errorMsg')}"
                )
                return None

            # 提取数据
            layout_results = result.get('result', {}).get(
                'layoutParsingResults', []
            )
            if not layout_results:
                self.logger.error("No layoutParsingResults in response")
                return None

            layout_result = layout_results[0]

            # 提取 markdown 文本
            markdown_data = layout_result.get('markdown', {})
            markdown_text = markdown_data.get('text', '')

            # 提取结构化数据
            pruned_result = layout_result.get('prunedResult', {})
            blocks = pruned_result.get('parsing_res_list', [])
            model_settings = pruned_result.get('model_settings', {})

            # 提取图片尺寸
            data_info = result.get('result', {}).get('dataInfo', {})
            width = data_info.get('width', 0)
            height = data_info.get('height', 0)

            return {
                'markdown': markdown_text,
                'blocks': blocks,
                'images': markdown_data.get('images', {}),
                'model_settings': model_settings,
                'width': width,
                'height': height,
                'page_idx': 0  # 单张图片视为第 0 页
            }

        except requests.exceptions.Timeout:
            self.logger.error(f"PaddleOCR API timeout")
            return None
        except Exception as e:
            self.logger.error(f"PaddleOCR API error: {e}", exc_info=True)
            return None
