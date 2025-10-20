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

"""
Parser Utilities - 解析器共享工具

提供 MinerU 相关解析器的共享功能
"""

import logging
import os
import re
import copy
import requests
import tempfile

from deepdoc.parser import MinerUParser
from rag.nlp import rag_tokenizer, tokenize, add_positions


# Gotenberg 配置
GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "http://localhost:3000")

# 支持的 Office 文档扩展名
OFFICE_EXTENSIONS = {
    ".123", ".602", ".abw", ".bib", ".bmp", ".cdr", ".cgm", ".cmx", ".csv", ".cwk", ".dbf", ".dif",
    ".doc", ".docm", ".docx", ".dot", ".dotm", ".dotx", ".dxf", ".emf", ".eps", ".epub", ".fodg",
    ".fodp", ".fods", ".fodt", ".fopd", ".gif", ".htm", ".html", ".hwp", ".jpeg", ".jpg", ".key",
    ".ltx", ".lwp", ".mcw", ".met", ".mml", ".mw", ".numbers", ".odd", ".odg", ".odm", ".odp",
    ".ods", ".odt", ".otg", ".oth", ".otp", ".ots", ".ott", ".pages", ".pbm", ".pcd", ".pct",
    ".pcx", ".pdb", ".pgm", ".png", ".pot", ".potm", ".potx", ".ppm", ".pps", ".ppt", ".pptm",
    ".pptx", ".psd", ".psw", ".pub", ".pwp", ".pxl", ".ras", ".rtf", ".sda", ".sdc", ".sdd",
    ".sdp", ".sdw", ".sgl", ".slk", ".smf", ".stc", ".std", ".sti", ".stw", ".svg", ".svm",
    ".swf", ".sxc", ".sxd", ".sxg", ".sxi", ".sxm", ".sxw", ".tga", ".tif", ".tiff", ".txt",
    ".uof", ".uop", ".uos", ".uot", ".vdx", ".vor", ".vsd", ".vsdm", ".vsdx", ".wb2", ".wk1",
    ".wks", ".wmf", ".wpd", ".wpg", ".wps", ".xbm", ".xhtml", ".xls", ".xlsb", ".xlsm", ".xlsx",
    ".xlt", ".xltm", ".xltx", ".xlw", ".xml", ".xpm", ".zabw"
}


def _convert_url_to_pdf(url_string, output_pdf_path, timeout=None):
    """
    使用 Gotenberg 将 URL 转换为 PDF

    Args:
        url_string: URL 地址
        output_pdf_path: 输出 PDF 路径
        timeout: 超时时间（秒）

    Returns:
        bool: 转换是否成功
    """
    endpoint = f"{GOTENBERG_URL}/forms/chromium/convert/url"
    logging.info(f"Converting URL to PDF: {url_string} -> {output_pdf_path}")

    try:
        response = requests.post(
            endpoint,
            data={"url": url_string},
            stream=True
        )
        response.raise_for_status()

        with open(output_pdf_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logging.info(f"Successfully converted URL to PDF: {output_pdf_path}")
        return True

    except requests.exceptions.RequestException as e:
        logging.error(f"Gotenberg URL conversion failed for {url_string}. Error: {e}")
        return False


def _convert_office_to_pdf(office_file_path, output_pdf_path, timeout=None):
    """
    使用 Gotenberg 将 Office 文档转换为 PDF

    Args:
        office_file_path: Office 文档路径
        output_pdf_path: 输出 PDF 路径
        timeout: 超时时间（秒）

    Returns:
        bool: 转换是否成功
    """
    endpoint = f"{GOTENBERG_URL}/forms/libreoffice/convert"
    logging.info(f"Converting Office document to PDF: {office_file_path} -> {output_pdf_path}")

    if not os.path.exists(office_file_path):
        logging.error(f"Office file not found: {office_file_path}")
        return False

    try:
        with open(office_file_path, 'rb') as f:
            files = {"files": (os.path.basename(office_file_path), f)}
            response = requests.post(
                endpoint,
                files=files,
                stream=True
            )
            response.raise_for_status()

        with open(output_pdf_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logging.info(f"Successfully converted Office document to PDF: {output_pdf_path}")
        return True

    except requests.exceptions.RequestException as e:
        logging.error(f"Gotenberg Office conversion failed for {office_file_path}. Error: {e}")
        return False
    except FileNotFoundError:
        logging.error(f"Office file not found (during open): {office_file_path}")
        return False


def _generate_safe_temp_filename(original_input, base_temp_dir, prefix="conv", suffix=".pdf"):
    """
    生成安全的临时文件名

    Args:
        original_input: 原始输入（文件路径或 URL）
        base_temp_dir: 临时目录
        prefix: 文件前缀
        suffix: 文件后缀

    Returns:
        str: 临时文件路径
    """
    base_name = os.path.basename(original_input)

    if original_input.startswith("http"):  # URL
        name_part = base_name.split('?')[0]
        safe_base = re.sub(r'[^a-zA-Z0-9_.-]', '_', name_part)[:50]
        if not safe_base or safe_base.endswith(('.htm', '.html', '.php', '.asp', '.aspx', '')):
            safe_base = "webpage"
    else:  # 本地文件
        name_part = os.path.splitext(base_name)[0]
        safe_base = re.sub(r'[^a-zA-Z0-9_.-]', '_', name_part)[:50]

    return os.path.join(base_temp_dir, f"{prefix}_{safe_base}{suffix}")


def ensure_pdf(file_input, binary=None):
    """
    确保输入是 PDF 文件。如果是 URL 或 Office 文档，尝试转换为 PDF

    Args:
        file_input: 文件路径或 URL
        binary: 二进制内容（如果提供，则忽略 file_input 的路径，将其作为文件名）

    Returns:
        tuple: (pdf_path, temp_pdf_path, binary_content)
            - pdf_path: 用于解析的 PDF 路径
            - temp_pdf_path: 需要清理的临时 PDF 路径（如果有）
            - binary_content: PDF 二进制内容（如果原本有 binary）
    """
    logging.info(f"Ensuring PDF for input: {file_input}")

    # 如果已经提供了 binary，检查文件名是否为 PDF
    if binary:
        if re.search(r"\.pdf$", file_input, re.IGNORECASE):
            # 已经是 PDF binary
            return file_input, None, binary
        else:
            # 需要将 binary 写入临时文件，然后转换
            temp_dir = tempfile.mkdtemp(prefix="ragflow_convert_")
            original_file = os.path.join(temp_dir, os.path.basename(file_input))

            with open(original_file, 'wb') as f:
                f.write(binary)

            file_ext = os.path.splitext(file_input)[1].lower()
            if file_ext in OFFICE_EXTENSIONS:
                temp_pdf_path = _generate_safe_temp_filename(file_input, temp_dir, prefix="office")
                if _convert_office_to_pdf(original_file, temp_pdf_path):
                    # 读取转换后的 PDF
                    with open(temp_pdf_path, 'rb') as f:
                        pdf_binary = f.read()
                    # 清理原始文件
                    os.remove(original_file)
                    return temp_pdf_path, temp_pdf_path, pdf_binary
                else:
                    # 清理临时目录
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise RuntimeError(f"Failed to convert {file_input} to PDF")
            else:
                # 不支持的文件类型
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise NotImplementedError(f"Unsupported file type: {file_ext}")

    # 没有 binary，处理文件路径或 URL
    file_ext = os.path.splitext(file_input)[1].lower()

    if file_input.startswith("http://") or file_input.startswith("https://"):
        # URL 转换
        temp_dir = tempfile.mkdtemp(prefix="ragflow_convert_")
        temp_pdf_path = _generate_safe_temp_filename(file_input, temp_dir, prefix="url")

        if _convert_url_to_pdf(file_input, temp_pdf_path):
            return temp_pdf_path, temp_pdf_path, None
        else:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to convert URL to PDF: {file_input}")

    elif file_ext in OFFICE_EXTENSIONS:
        # Office 文档转换
        if not os.path.exists(file_input):
            raise FileNotFoundError(f"Source file not found: {file_input}")

        temp_dir = tempfile.mkdtemp(prefix="ragflow_convert_")
        temp_pdf_path = _generate_safe_temp_filename(file_input, temp_dir, prefix="office")

        if _convert_office_to_pdf(file_input, temp_pdf_path):
            return temp_pdf_path, temp_pdf_path, None
        else:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to convert {file_input} to PDF")

    elif file_ext == ".pdf":
        # 已经是 PDF
        if not os.path.exists(file_input):
            raise FileNotFoundError(f"Source PDF file not found: {file_input}")
        return file_input, None, None

    else:
        raise NotImplementedError(f"Unsupported file type: {file_ext}")


def extract_text_and_coordinates(sections):
    """
    从 MinerU sections 中提取纯文本和坐标映射

    Args:
        sections: [(text_with_tags, position_tag), ...]
        每个 section 对应 markdown 的一行，格式: @@page\tx0\tx1\ty0\ty1##text

    Returns:
        (markdown_text, coordinate_map)
        coordinate_map: {line_number: [page, x1, x2, y1, y2]}
    """
    lines = []
    coordinate_map = {}

    pattern = r'@@(\d+)\t([\d.]+)\t([\d.]+)\t([\d.]+)\t([\d.]+)##'

    for line_idx, (text_with_tag, _) in enumerate(sections):
        # 提取位置标签
        match = re.search(pattern, text_with_tag)

        # 移除位置标签，获取纯文本
        clean_text = re.sub(pattern, '', text_with_tag)
        lines.append(clean_text)

        # 记录坐标（如果有的话）
        if match and clean_text.strip():
            page_num = int(match.group(1))
            x0 = float(match.group(2))
            x1 = float(match.group(3))
            top = float(match.group(4))
            bottom = float(match.group(5))

            coordinate_map[line_idx] = [page_num, x0, x1, top, bottom]

    markdown_text = '\n'.join(lines)
    return markdown_text, coordinate_map


def call_chunking_service(markdown_text, coordinate_map, chunking_config, doc_id, kb_id, tenant_id):
    """
    调用 KnowFlow Server 的通用分块服务

    Args:
        markdown_text: markdown 文本
        coordinate_map: 坐标映射
        chunking_config: 分块配置（可以包含 enable_vision_enhancement 等配置）
        doc_id: 文档ID
        kb_id: 知识库ID
        tenant_id: 租户ID

    Returns:
        List[dict]: [{"content": str, "positions": [[page, x1, x2, y1, y2], ...], "id": str (optional)}, ...]
    """
    knowflow_server_url = os.getenv('KNOWFLOW_API_URL', 'http://localhost:5000')
    api_url = f"{knowflow_server_url}/api/parse/smart_chunk"

    # 准备请求数据
    request_data = {
        'markdown_text': markdown_text,
        'chunking_config': chunking_config,
        'doc_id': doc_id,
        'kb_id': kb_id,
        'tenant_id': tenant_id
    }

    # 添加坐标映射（如果有）
    if coordinate_map:
        # 将键转换为字符串（JSON 要求）
        request_data['coordinate_map'] = {str(k): v for k, v in coordinate_map.items()}

    # 添加图片视觉增强配置（从 chunking_config 中提取）
    if isinstance(chunking_config, dict):
        # 读取图片增强配置，如果配置中明确指定了值则使用，否则默认为 False
        if 'enable_vision_enhancement' in chunking_config:
            enable_vision = chunking_config['enable_vision_enhancement']
            request_data['enable_vision_enhancement'] = enable_vision

            if enable_vision:
                # 只有启用时才传递额外配置
                if 'vision_description_format' in chunking_config:
                    request_data['vision_description_format'] = chunking_config['vision_description_format']
                if 'vision_batch_size' in chunking_config:
                    request_data['vision_batch_size'] = chunking_config['vision_batch_size']
                logging.info("图片视觉增强已启用")
            else:
                logging.info("图片视觉增强已禁用")

    try:
        response = requests.post(
            api_url,
            json=request_data
        )

        if response.status_code != 200:
            error_msg = f"Chunking API error: {response.status_code} - {response.text}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

        result = response.json()

        if not result.get('success'):
            error_msg = f"Chunking failed: {result.get('error', 'Unknown error')}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

        chunks = result.get('chunks', [])
        logging.info(f"Chunking service returned {len(chunks)} chunks")

        return chunks

    except requests.exceptions.Timeout:
        raise RuntimeError("Chunking service timeout")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Cannot connect to KnowFlow Server at {knowflow_server_url}: {e}")
    except Exception as e:
        logging.exception(f"Chunking service failed: {e}")
        raise


def parse_pdf_with_mineru(filename, binary, from_page, to_page, kb_id, callback):
    """
    使用 MinerU 解析 PDF

    Args:
        filename: 文件名
        binary: 二进制内容
        from_page: 起始页
        to_page: 结束页
        kb_id: 知识库ID
        callback: 回调函数

    Returns:
        (sections, tables): MinerU 解析结果
    """
    callback(0.1, "Start to parse.")
    logging.info("Using MinerU parser")
    callback(0.2, "Parsing with MinerU...")

    pdf_parser = MinerUParser()
    sections, tables = pdf_parser(
        filename if not binary else binary,
        from_page=from_page,
        to_page=to_page,
        kb_id=kb_id
    )

    callback(0.5, "MinerU parsing finished.")
    return sections, tables


def prepare_base_doc(filename):
    """
    准备基础文档字典

    Args:
        filename: 文件名

    Returns:
        dict: 基础文档字典，包含 docnm_kwd, title_tks 等
    """
    doc = {
        "docnm_kwd": filename,
        "title_tks": rag_tokenizer.tokenize(re.sub(r"\.[a-zA-Z]+$", "", filename))
    }
    doc["title_sm_tks"] = rag_tokenizer.fine_grained_tokenize(doc["title_tks"])
    return doc


def convert_chunks_to_ragflow_format(chunks_with_positions, base_doc, lang, callback):
    """
    将分块结果转换为 RAGFlow 格式

    Args:
        chunks_with_positions: 带坐标的分块列表
        base_doc: 基础文档字典
        lang: 语言
        callback: 回调函数

    Returns:
        List[dict]: RAGFlow 格式的分块列表
    """
    is_english = lang.lower() == "english"
    res = []

    for chunk_data in chunks_with_positions:
        d = copy.deepcopy(base_doc)

        # 提取文本和坐标
        chunk_text = chunk_data.get('content', '')
        positions = chunk_data.get('positions', [])

        if not chunk_text.strip():
            continue

        # 如果有预设 ID（父子分块），保留它
        if 'id' in chunk_data:
            d['_id_override'] = chunk_data['id']

        # 添加坐标信息
        if positions:
            add_positions(d, positions)

        # Tokenize
        tokenize(d, chunk_text, is_english)
        res.append(d)

    return res


def mineru_chunk_pipeline(
    filename, binary, from_page, to_page, lang, callback,
    strategy, parser_config, doc_id, kb_id, tenant_id,
    strategy_name=""
):
    """
    MinerU 解析器的通用分块流程

    Args:
        filename: 文件名
        binary: 二进制内容
        from_page: 起始页
        to_page: 结束页
        lang: 语言
        callback: 回调函数
        strategy: 分块策略名称
        parser_config: 解析器配置
        doc_id: 文档ID
        kb_id: 知识库ID
        tenant_id: 租户ID
        strategy_name: 策略显示名称（用于日志）

    Returns:
        List[dict]: RAGFlow 格式的分块列表
    """
    temp_pdf_to_cleanup = None

    try:
        # 确保输入是 PDF（如果不是则转换）
        pdf_path, temp_pdf_to_cleanup, pdf_binary = ensure_pdf(filename, binary)

        # 准备基础文档（使用原始文件名）
        doc = prepare_base_doc(filename)

        # MinerU 解析（使用转换后的 PDF）
        sections, tables = parse_pdf_with_mineru(
            pdf_path, pdf_binary, from_page, to_page, kb_id, callback
        )

        # 提取文本和坐标
        markdown_text, coordinate_map = extract_text_and_coordinates(sections)

        callback(0.6, f"Calling {strategy_name} chunking service...")

        # 调用分块服务
        try:
            chunks_with_positions = call_chunking_service(
                markdown_text, coordinate_map, parser_config,
                doc_id, kb_id, tenant_id
            )
            callback(0.9, f"{strategy_name} chunking completed.")
        except Exception as e:
            logging.error(f"{strategy_name} chunking service failed: {e}")
            callback(0.9, f"{strategy_name} chunking failed: {e}")
            raise

        # 转换为 RAGFlow 格式
        res = convert_chunks_to_ragflow_format(chunks_with_positions, doc, lang, callback)

        logging.info(f"{strategy_name} chunking completed: {len(res)} chunks created")
        callback(1.0, f"Completed: {len(res)} chunks")

        return res

    finally:
        # 清理临时 PDF 文件
        if temp_pdf_to_cleanup and os.path.exists(temp_pdf_to_cleanup):
            try:
                import shutil
                temp_dir = os.path.dirname(temp_pdf_to_cleanup)
                if temp_dir and os.path.exists(temp_dir) and temp_dir.startswith(tempfile.gettempdir()):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logging.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logging.warning(f"Failed to cleanup temporary files: {e}")
