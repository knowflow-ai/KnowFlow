"""
PaddleOCR API 客户端

提供调用 PaddleOCR 服务的统一接口
支持图片和 PDF 直接识别
"""

import requests
import base64
import logging
from typing import Optional, Dict, Any, Union, BinaryIO

try:
    from ...config.config_loader import PADDLEOCR_CONFIG
except ImportError:
    from services.config.config_loader import PADDLEOCR_CONFIG


class PaddleOCRClient:
    """PaddleOCR API 客户端 - 优化版"""

    # 默认超时配置
    DEFAULT_TIMEOUT_IMAGE = 120  # 图片默认 2 分钟超时

    def __init__(self, api_url: Optional[str] = None, timeout: Optional[int] = None, max_file_size: Optional[int] = None):
        """
        初始化客户端

        Args:
            api_url: PaddleOCR 服务地址，默认从 settings.yaml 读取
            timeout: 请求超时时间（秒），默认从 settings.yaml 读取
            max_file_size: 最大文件大小（MB），默认从 settings.yaml 读取
        """
        self.api_url = api_url or PADDLEOCR_CONFIG.url
        self.default_timeout = timeout or PADDLEOCR_CONFIG.timeout
        self.max_file_size = (max_file_size or PADDLEOCR_CONFIG.max_file_size) * 1024 * 1024  # 转换为字节
        self.endpoint = f"{self.api_url}/layout-parsing"
        self.logger = logging.getLogger(__name__)

        # 验证连接（缓存结果）
        self._connection_validated = False

    def _validate_connection(self) -> bool:
        """验证服务连接（带缓存）"""
        if self._connection_validated:
            return True

        try:
            # 简单的健康检查
            response = requests.get(self.api_url, timeout=5)
            self._connection_validated = (response.status_code < 500)
            return self._connection_validated
        except Exception as e:
            self.logger.warning(f"PaddleOCR service might be unavailable: {e}")
            return False

    def _validate_input(self, data: bytes, file_type: str) -> bool:
        """
        验证输入数据

        Args:
            data: 文件二进制数据
            file_type: 文件类型 ('pdf' 或 'image')

        Returns:
            是否有效
        """
        if not data:
            self.logger.error(f"Empty {file_type} data")
            return False

        if len(data) > self.max_file_size:
            self.logger.error(
                f"{file_type} too large: {len(data) / 1024 / 1024:.2f}MB > "
                f"{self.max_file_size / 1024 / 1024:.0f}MB"
            )
            return False

        return True

    def _call_api(
        self,
        data: bytes,
        file_type: int,
        timeout: int
    ) -> Optional[Dict[str, Any]]:
        """
        统一的 API 调用方法

        Args:
            data: 文件二进制数据
            file_type: 0=PDF, 1=图像
            timeout: 超时时间（秒）

        Returns:
            API 响应，失败返回 None
        """
        try:
            # 转换为 base64
            base64_data = base64.b64encode(data).decode('utf-8')

            # 构建请求
            request_data = {
                'file': base64_data,
                'fileType': file_type,
                'visualize': False  # 始终禁用可视化以提升性能
            }

            # 记录请求信息
            file_type_name = "PDF" if file_type == 0 else "Image"
            self.logger.info(
                f"Calling PaddleOCR API for {file_type_name} "
                f"(size: {len(data) / 1024:.1f}KB, timeout: {timeout}s)"
            )

            # 发送请求
            response = requests.post(
                self.endpoint,
                json=request_data,
                timeout=timeout
            )

            # 检查 HTTP 状态
            if response.status_code != 200:
                self.logger.error(
                    f"PaddleOCR API HTTP error: {response.status_code}, "
                    f"response: {response.text[:200]}"
                )
                return None

            result = response.json()

            # 检查业务错误码
            error_code = result.get('errorCode', -1)
            if error_code != 0:
                error_msg = result.get('errorMsg', 'Unknown error')
                self.logger.error(
                    f"PaddleOCR API business error: "
                    f"code={error_code}, msg={error_msg}"
                )
                return None

            return result

        except requests.exceptions.Timeout:
            self.logger.error(
                f"PaddleOCR API timeout after {timeout} seconds"
            )
            return None
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error to PaddleOCR service: {e}")
            return None
        except ValueError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            return None
        except Exception as e:
            self.logger.error(
                f"Unexpected error calling PaddleOCR API: {e}",
                exc_info=True
            )
            return None

    def recognize_pdf(
        self,
        pdf_input: Union[bytes, str, BinaryIO],
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        识别 PDF 文件（支持多页）

        Args:
            pdf_input: PDF 数据（bytes）、文件路径（str）或文件对象
            timeout: 请求超时时间（秒）

        Returns:
            {
                "markdown": str,
                "blocks": [...],
                "images": {...},
                "model_settings": {...},
                "page_count": int
            }
            失败返回 None
        """
        # 处理不同的输入类型
        if isinstance(pdf_input, str):
            # 文件路径
            try:
                with open(pdf_input, 'rb') as f:
                    pdf_binary = f.read()
            except Exception as e:
                self.logger.error(f"Failed to read PDF from {pdf_input}: {e}")
                return None
        elif hasattr(pdf_input, 'read'):
            # 文件对象
            pdf_binary = pdf_input.read()
        else:
            # 二进制数据
            pdf_binary = pdf_input

        # 验证输入
        if not self._validate_input(pdf_binary, 'PDF'):
            return None

        # 调用 API
        timeout = timeout or self.default_timeout
        result = self._call_api(pdf_binary, file_type=0, timeout=timeout)
        if not result:
            return None

        # 解析响应
        return self._parse_pdf_response(result)

    def _parse_pdf_response(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析 PDF 识别响应"""
        try:
            layout_results = result.get('result', {}).get('layoutParsingResults', [])
            if not layout_results:
                self.logger.warning("No layout parsing results in response")
                return None

            # 收集所有页面的数据
            all_blocks = []
            all_markdown_parts = []
            all_images = {}

            for page_idx, layout_result in enumerate(layout_results):
                # 提取 markdown
                markdown_data = layout_result.get('markdown', {})
                markdown_text = markdown_data.get('text', '')
                all_markdown_parts.append(markdown_text)

                # 提取图片（带错误处理）
                page_images = markdown_data.get('images', {})
                if page_images:
                    self.logger.debug(f"Page {page_idx}: {len(page_images)} images found")
                    all_images.update(page_images)

                # 提取块数据
                pruned_result = layout_result.get('prunedResult', {})
                blocks = pruned_result.get('parsing_res_list', [])

                # 为每个块添加页码
                for block in blocks:
                    block['page_idx'] = page_idx
                    all_blocks.append(block)

            # 合并 markdown
            full_markdown = '\n\n'.join(all_markdown_parts)

            # 获取模型设置
            first_pruned = layout_results[0].get('prunedResult', {})
            model_settings = first_pruned.get('model_settings', {})

            self.logger.info(
                f"Successfully processed {len(layout_results)} pages, "
                f"{len(all_blocks)} blocks, {len(all_images)} images"
            )

            return {
                'markdown': full_markdown,
                'blocks': all_blocks,
                'images': all_images,
                'model_settings': model_settings,
                'page_count': len(layout_results)
            }

        except Exception as e:
            self.logger.error(f"Failed to parse PDF response: {e}", exc_info=True)
            return None

    def recognize_image(
        self,
        image_input: Union[bytes, str, BinaryIO],
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        识别单张图片

        Args:
            image_input: 图片数据（bytes）、文件路径（str）或文件对象
            timeout: 请求超时时间（秒）

        Returns:
            识别结果，失败返回 None
        """
        # 处理不同的输入类型
        if isinstance(image_input, str):
            # 文件路径
            try:
                with open(image_input, 'rb') as f:
                    image_binary = f.read()
            except Exception as e:
                self.logger.error(f"Failed to read image from {image_input}: {e}")
                return None
        elif hasattr(image_input, 'read'):
            # 文件对象
            image_binary = image_input.read()
        else:
            # 二进制数据
            image_binary = image_input

        # 验证输入
        if not self._validate_input(image_binary, 'image'):
            return None

        # 调用 API
        timeout = timeout or self.DEFAULT_TIMEOUT_IMAGE
        result = self._call_api(image_binary, file_type=1, timeout=timeout)
        if not result:
            return None

        # 解析响应
        return self._parse_image_response(result)

    def _parse_image_response(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析图片识别响应"""
        try:
            layout_results = result.get('result', {}).get('layoutParsingResults', [])
            if not layout_results:
                self.logger.warning("No layout parsing results in response")
                return None

            layout_result = layout_results[0]

            # 提取数据
            markdown_data = layout_result.get('markdown', {})
            pruned_result = layout_result.get('prunedResult', {})

            # 图片尺寸
            data_info = result.get('result', {}).get('dataInfo', {})

            return {
                'markdown': markdown_data.get('text', ''),
                'blocks': pruned_result.get('parsing_res_list', []),
                'images': markdown_data.get('images', {}),
                'model_settings': pruned_result.get('model_settings', {}),
                'width': data_info.get('width', 0),
                'height': data_info.get('height', 0),
                'page_idx': 0
            }

        except Exception as e:
            self.logger.error(f"Failed to parse image response: {e}", exc_info=True)
            return None

    # 保留向后兼容的方法
    def recognize_pdf_from_path(self, pdf_path: str, timeout: int = 600) -> Optional[Dict[str, Any]]:
        """向后兼容：从文件路径识别 PDF"""
        return self.recognize_pdf(pdf_path, timeout)


# 单例模式（可选）
_default_client = None

def get_default_client() -> PaddleOCRClient:
    """获取默认客户端实例（单例）"""
    global _default_client
    if _default_client is None:
        _default_client = PaddleOCRClient()
    return _default_client