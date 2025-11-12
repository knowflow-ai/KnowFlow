"""
PDF 转图片工具

将 PDF 文件转换为图片列表，用于 PaddleOCR 识别
"""

import logging
import os
from typing import List, Optional
from io import BytesIO

try:
    from pdf2image import convert_from_path, convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logging.warning(
        "pdf2image not installed. "
        "Install with: pip install pdf2image"
    )

from PIL import Image


def convert_pdf_to_images(
    pdf_input,
    from_page: int = 1,
    to_page: Optional[int] = None,
    dpi: int = 200,
    fmt: str = 'PNG'
) -> List[bytes]:
    """
    将 PDF 转换为图片列表

    Args:
        pdf_input: PDF 文件路径或二进制数据
        from_page: 起始页码（1-based）
        to_page: 结束页码（1-based，None 表示到最后一页）
        dpi: 图片分辨率（PaddleOCR 推荐 200）
        fmt: 图片格式（PNG/JPEG）

    Returns:
        图片二进制数据列表（0-based index）

    Raises:
        ImportError: pdf2image 未安装
        Exception: 转换失败
    """
    if not PDF2IMAGE_AVAILABLE:
        raise ImportError(
            "pdf2image is required for PDF conversion. "
            "Install with: pip install pdf2image"
        )

    logger = logging.getLogger(__name__)

    try:
        # 根据输入类型选择转换方法
        if isinstance(pdf_input, str):
            logger.info(
                f"Converting PDF from path: {pdf_input} "
                f"(pages {from_page}-{to_page or 'end'}, {dpi} DPI)"
            )
            images = convert_from_path(
                pdf_input,
                first_page=from_page,
                last_page=to_page,
                dpi=dpi,
                fmt=fmt
            )
        elif isinstance(pdf_input, bytes):
            logger.info(
                f"Converting PDF from bytes "
                f"(pages {from_page}-{to_page or 'end'}, {dpi} DPI)"
            )
            images = convert_from_bytes(
                pdf_input,
                first_page=from_page,
                last_page=to_page,
                dpi=dpi,
                fmt=fmt
            )
        else:
            raise ValueError(
                f"Invalid pdf_input type: {type(pdf_input)}. "
                "Expected str or bytes"
            )

        logger.info(f"Converted {len(images)} pages to images")

        # 转换为二进制数据
        image_binaries = []
        for i, img in enumerate(images):
            buffer = BytesIO()
            img.save(buffer, format=fmt)
            image_binaries.append(buffer.getvalue())
            logger.debug(
                f"Page {i}: {img.size[0]}x{img.size[1]}, "
                f"{len(image_binaries[-1])} bytes"
            )

        return image_binaries

    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}", exc_info=True)
        raise


def get_pdf_page_count(pdf_input) -> int:
    """
    获取 PDF 页数

    Args:
        pdf_input: PDF 文件路径或二进制数据

    Returns:
        页数

    Raises:
        ImportError: pdf2image 未安装
        Exception: 获取失败
    """
    if not PDF2IMAGE_AVAILABLE:
        raise ImportError(
            "pdf2image is required. "
            "Install with: pip install pdf2image"
        )

    try:
        # 只转换第一页来获取总页数
        # pdf2image 会在日志中输出总页数，或者通过异常获取
        if isinstance(pdf_input, str):
            from pdf2image.pdf2image import pdfinfo_from_path
            info = pdfinfo_from_path(pdf_input)
        else:
            from pdf2image.pdf2image import pdfinfo_from_bytes
            info = pdfinfo_from_bytes(pdf_input)

        return info.get('Pages', 0)

    except Exception as e:
        logging.error(f"Failed to get PDF page count: {e}", exc_info=True)
        raise


def save_images_to_dir(
    images: List[bytes],
    output_dir: str,
    prefix: str = 'page',
    fmt: str = 'PNG'
) -> List[str]:
    """
    将图片保存到目录

    Args:
        images: 图片二进制数据列表
        output_dir: 输出目录
        prefix: 文件名前缀
        fmt: 图片格式

    Returns:
        保存的文件路径列表
    """
    os.makedirs(output_dir, exist_ok=True)

    file_paths = []
    for i, image_binary in enumerate(images):
        file_path = os.path.join(
            output_dir,
            f"{prefix}_{i+1:04d}.{fmt.lower()}"
        )

        with open(file_path, 'wb') as f:
            f.write(image_binary)

        file_paths.append(file_path)

    logging.info(f"Saved {len(file_paths)} images to {output_dir}")
    return file_paths
