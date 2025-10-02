import os
import tempfile
import shutil
import json
import mysql.connector
import traceback
import time 
from database import DB_CONFIG, get_minio_client
from ..config.config_loader import CONFIG


def _get_parser_engine(parser_id: str, parser_config: dict) -> str:
    """根据文档的parser_id和配置选择解析引擎
    
    Args:
        parser_id: 文档的解析方法ID (优先级最高)
        parser_config: 解析器配置字典
        
    Returns:
        str: 解析引擎名称 ('mineru' 或 'dots')
    """
    # 1. 优先使用文档级别设置的解析方法 (最高优先级)
    if parser_id:
        engine = parser_id.lower()
        if engine in ['mineru', 'dots']:
            print(f"[Parser-INFO] 使用文档指定的解析引擎: {engine}")
            return engine
    
    # 2. 检查解析配置中是否指定了引擎
    if parser_config and 'parser_engine' in parser_config:
        engine = parser_config['parser_engine'].lower()
        if engine in ['mineru', 'dots']:
            print(f"[Parser-INFO] 使用配置指定的解析引擎: {engine}")
            return engine
    
    # 3. 使用全局默认配置
    default_engine = getattr(CONFIG, 'default_parser', 'mineru').lower()
    print(f"[Parser-INFO] 使用默认解析引擎: {default_engine}")
    
    # 确保返回有效的引擎名称
    return default_engine if default_engine in ['mineru', 'dots'] else 'mineru'


def _get_db_connection():
    """创建数据库连接"""
    return mysql.connector.connect(**DB_CONFIG)

def _update_document_progress(doc_id, progress=None, message=None, status=None, run=None, chunk_count=None, process_duration=None):
    """更新数据库中文档的进度和状态"""
    conn = None
    cursor = None
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        updates = []
        params = []

        if progress is not None:
            updates.append("progress = %s")
            params.append(float(progress))
        if message is not None:
            updates.append("progress_msg = %s")
            params.append(message)
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if run is not None:
            updates.append("run = %s")
            params.append(run)
        if chunk_count is not None:
             updates.append("chunk_num = %s")
             params.append(chunk_count)
        if process_duration is not None:
            updates.append("process_duration = %s")
            params.append(process_duration)


        if not updates:
            return

        query = f"UPDATE document SET {', '.join(updates)} WHERE id = %s"
        params.append(doc_id)
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        print(f"[Parser-ERROR] 更新文档 {doc_id} 进度失败: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



def perform_parse(doc_id, doc_info, file_info):
    """
    执行文档解析的核心逻辑

    Args:
        doc_id (str): 文档ID.
        doc_info (dict): 包含文档信息的字典 (name, location, type, kb_id, parser_config, created_by).
        file_info (dict): 包含文件信息的字典 (parent_id/bucket_name).

    Returns:
        dict: 包含解析结果的字典 (success, chunk_count).
    """
    temp_pdf_path = None
    temp_image_dir = None
    start_time = time.time()
    
    try:
        kb_id = doc_info['kb_id']
        file_location = doc_info['location']
        # 打印 doc_info
        # 从文件路径中提取原始后缀名
        _, file_extension = os.path.splitext(file_location)
        file_type = doc_info['type'].lower()
        parser_config = json.loads(doc_info['parser_config']) if isinstance(doc_info['parser_config'], str) else doc_info['parser_config']
        bucket_name = file_info['parent_id'] # 文件存储的桶是 parent_id

        # 进度更新回调 (直接调用内部更新函数)
        def update_progress(prog=None, msg=None):
            _update_document_progress(doc_id, progress=prog, message=msg)
            print(f"[Parser-PROGRESS] Doc: {doc_id}, Progress: {prog}, Message: {msg}")


        minio_client = get_minio_client()
        file_content = None # 初始化 file_content
        # 从MinIO下载文件
        try:
            if minio_client.bucket_exists(bucket_name):
                print(f"[Parser-INFO] 从 MinIO 下载文件: {file_location}")
                response = minio_client.get_object(bucket_name, file_location)
                file_content = response.read()
                response.close()
        except Exception as e:
            print(f"[Parser-WARNING] MinIO 下载异常: {e}，尝试从 RAGFlow API获取文件")
       
        # 从 RAGFlow 系统重查询
        if not file_content: # 确保此 if 与 minio_client = ... 在同一缩进级别
            from .utils import get_doc_content     
            file_content = get_doc_content(kb_id, doc_id)

        if not file_content: # 确保此 if 与上一个 if 在同一缩进级别
           raise ValueError(f"[Parser-ERROR] 无法获取文件内容: {file_location}")
        
        chunk_count = 0
        
        # ======== 文件类型分发处理 ========
        is_table_file = file_extension.lower() in ['.xlsx', '.xls', '.csv']

        if is_table_file:
            # --- 表格文件处理 ---
            from .excel_parse import process_excel_entry
            chunk_count = process_excel_entry(
                doc_id=doc_id,
                file_content=file_content,
                kb_id=kb_id,
                parser_config=parser_config,
                doc_info=doc_info,
                update_progress=update_progress
            )
        else:
            # --- 默认文件处理 (PDF, Markdown等) ---
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, f"{doc_id}{file_extension}")
            print(f"[Parser-INFO] 临时文件路径: {temp_file_path}")
            with open(temp_file_path, 'wb') as f:
                f.write(file_content)

            # 初始化进度
            update_progress(0.2, "OCR开始")

            # === 选择解析引擎 ===
            parser_id = doc_info.get('parser_id', 'naive')
            selected_engine = _get_parser_engine(parser_id, parser_config)
            print(f"[Parser-INFO] 选择的解析引擎: {selected_engine}")

            if selected_engine == 'dots':
                # === DOTS OCR 解析路径 ===
                print(f"[Parser-INFO] 使用 DOTS OCR 处理文档")
                from .dots_parse.process_document import process_document_with_dots
                
                chunk_count = process_document_with_dots(
                    doc_id=doc_id,
                    file_path=temp_file_path,
                    kb_id=kb_id,
                    update_progress=update_progress,
                    embedding_config=None,  # DOTS 也通过 RAGFlow batch API 获取嵌入模型
                    parser_config=parser_config  # 传递完整的解析器配置
                )
            
            if selected_engine == 'mineru':
                # === MinerU 解析路径（原有逻辑）===
                from .mineru_parse.process_pdf import process_pdf_entry
                chunk_count = process_pdf_entry(doc_id, temp_file_path, kb_id, update_progress)
        
        # ======== 统一处理完成状态 ========
        process_duration = time.time() - start_time
        
        if is_table_file:
            final_message = "表格解析完成"
        else:
            # 根据使用的解析引擎生成相应的完成消息
            parser_id = doc_info.get('parser_id', 'naive')
            engine_name = _get_parser_engine(parser_id, parser_config).upper()
            final_message = f"{engine_name} 文档解析完成"

        _update_document_progress(doc_id,  progress=1.0, run='3', chunk_count=chunk_count, process_duration=process_duration, message=final_message)
        
        print(f"[Parser-INFO] 文档 {doc_id} 处理完成，生成 {chunk_count} 个块")
        return {"success": True, "chunk_count": chunk_count}
            
    except Exception as e:
        process_duration = time.time() - start_time
        # error_message = f"解析失败: {str(e)}"
        print(f"[Parser-ERROR] 文档 {doc_id} 解析失败: {e}")
        error_message = f"解析失败: {e}"
        traceback.print_exc() # 打印详细错误堆栈
        # 更新文档状态为失败
        _update_document_progress(doc_id, run='4', message=error_message, process_duration=process_duration) # run=4表示失败
        # 不抛出异常，让调用者知道任务已结束（但失败）
        return {"success": False, "error": error_message}

    finally:
        # 清理临时文件 - 根据开发模式和环境变量控制
        from .mineru_parse.utils import should_cleanup_temp_files
        
        cleanup_enabled = should_cleanup_temp_files()
        
        if cleanup_enabled:
            try:
                # 清理通过temp_file_path变量创建的临时文件
                if 'temp_file_path' in locals() and temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    print(f"[Parser-INFO] 已清理临时文件: {temp_file_path}")
                
                # 清理可能的临时PDF文件（向后兼容）
                if temp_pdf_path and os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
                    print(f"[Parser-INFO] 已清理临时PDF文件: {temp_pdf_path}")
                    
                # 清理可能的临时图片目录
                if temp_image_dir and os.path.exists(temp_image_dir):
                    shutil.rmtree(temp_image_dir, ignore_errors=True)
                    print(f"[Parser-INFO] 已清理临时图片目录: {temp_image_dir}")
            except Exception as clean_e:
                print(f"[Parser-WARNING] 清理临时文件失败: {clean_e}")
        else:
            print(f"[Parser-INFO] 配置为保留临时文件（dev模式或CLEANUP_TEMP_FILES=false）")
            if 'temp_file_path' in locals() and temp_file_path:
                print(f"[Parser-INFO] 保留临时文件: {temp_file_path}")
            if temp_pdf_path:
                print(f"[Parser-INFO] 保留临时PDF文件: {temp_pdf_path}")
            if temp_image_dir:
                print(f"[Parser-INFO] 保留临时图片目录: {temp_image_dir}")
