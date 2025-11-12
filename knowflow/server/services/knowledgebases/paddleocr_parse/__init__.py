"""
PaddleOCR 解析服务

提供 PaddleOCR OCR 能力，并转换为与 MinerU 兼容的格式
"""

from .paddleocr_client import PaddleOCRClient
from .ocr_to_middle_json import OCRToMiddleJsonConverter

__all__ = [
    'PaddleOCRClient',
    'OCRToMiddleJsonConverter',
]
