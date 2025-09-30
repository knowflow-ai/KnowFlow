from ragflow_sdk import RAGFlow
import os
import time
import shutil
import json
from .minio_server import upload_directory_to_minio
from .mineru_test import update_markdown_image_urls
from .utils import split_markdown_to_chunks_configured, should_cleanup_temp_files
from .middle_json_simple import middle_json_to_markdown, get_chunk_coordinates, reset_chunking_session
from ..utils import _get_kb_tenant_id, _get_tenant_api_key, _validate_base_url
from database import get_db_connection


# 性能优化配置参数
CHUNK_PROCESSING_CONFIG = {
    'enable_performance_stats': False,     # 是否启用性能统计
}

def _upload_images(kb_id, image_dir, update_progress):
    update_progress(0.7, "上传图片到MinIO...")
    print(f"第4步：上传图片到MinIO...")
    upload_directory_to_minio(kb_id, image_dir)

def get_ragflow_doc(doc_id, kb_id):
    """获取RAGFlow文档对象和dataset对象"""
    # 首先获取知识库的tenant_id
    tenant_id = _get_kb_tenant_id(kb_id)
    if not tenant_id:
        raise Exception(f"无法获取知识库 {kb_id} 的tenant_id")
    
    # 根据tenant_id获取对应的API key
    api_key = _get_tenant_api_key(tenant_id)
    if not api_key:
        raise Exception(f"无法获取tenant {tenant_id} 的API key")
    
    base_url = _validate_base_url()
    rag_object = RAGFlow(api_key=api_key, base_url=base_url)
    datasets = rag_object.list_datasets(id=kb_id)
    if not datasets:
        raise Exception(f"未找到知识库 {kb_id}")
    dataset = datasets[0]
    docs = dataset.list_documents(id=doc_id)
    if not docs:
        raise Exception(f"未找到文档 {doc_id}")
    return docs[0], dataset  # 返回doc和dataset元组

def _get_document_chunking_config(doc_id):
    """从数据库获取文档的分块配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT parser_config FROM document WHERE id = %s", (doc_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            parser_config = json.loads(result[0])
            chunking_config = parser_config.get('chunking_config')
            if chunking_config:
                return chunking_config
        
        return None
        
    except Exception as e:
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def add_chunks_with_enhanced_batch_api(doc, chunks, md_file_path, chunk_content_to_index, update_progress, parent_child_data=None, chunks_with_coordinates=None, coord_lookup_path=None):
    """
    使用增强的batch接口处理分块（支持父子分块和坐标传递）
    
    Args:
        doc: RAGFlow文档对象
        chunks: 分块内容列表
        md_file_path: markdown文件路径
        chunk_content_to_index: 分块内容到索引的映射
        update_progress: 进度更新回调
        parent_child_data: 父子分块数据（可选）
        chunks_with_coordinates: 包含坐标信息的分块数据（可选，用于DOTS等没有md文件的情况）
    
    Returns:
        int: 成功添加的分块数量
    """
    
    if not chunks:
        update_progress(0.8, "没有chunks需要添加")
        return 0
    
    # 初始进度更新
    update_progress(0.8, "开始批量添加chunks到文档（使用增强batch接口）...")
    
    try:
        # 重置分块会话，确保重复文本（如页眉）能正确按顺序匹配
        if coord_lookup_path:
            reset_chunking_session(coord_lookup_path)

        # 准备批量数据，包含位置信息
        batch_chunks = []
        for i, chunk in enumerate(chunks):
            if chunk and chunk.strip():
                chunk_data = {
                    "content": chunk.strip(),
                    "important_keywords": [],  # 可以根据需要添加关键词提取
                    "questions": []  # 可以根据需要添加问题生成
                }
                
                # 获取chunk的原始索引（确保排序正确性）
                original_index = chunk_content_to_index.get(chunk.strip(), i)
                
                # 统一排序机制：固定page_num_int=1，top_int=原始索引
                chunk_data["page_num_int"] = [1]  # 固定为1，保证所有chunks都在同一"页"
                chunk_data["top_int"] = original_index  # 使用原始索引保证顺序
                
                # 尝试获取精确位置信息（作为额外的位置数据，不影响排序）
                position_found = False
                
                # 优先从chunks_with_coordinates获取坐标（DOTS等情况）
                if chunks_with_coordinates and i < len(chunks_with_coordinates):
                    chunk_with_coord = chunks_with_coordinates[i]
                    if chunk_with_coord and chunk_with_coord.get('positions'):
                        chunk_data["positions"] = chunk_with_coord['positions']
                        position_found = True
                
                # 如果没有直接坐标，尝试获取坐标
                if not position_found:
                    if coord_lookup_path:
                        try:
                            coords = get_chunk_coordinates(coord_lookup_path, chunk.strip())
                            if coords:
                                positions = [[int(c[0]), c[1], c[2], c[3], c[4]] for c in coords]
                                chunk_data["positions"] = positions
                                position_found = True
                        except Exception:
                            pass
                
                # 如果都没有找到坐标
                if not position_found:
                    pass
                
                batch_chunks.append(chunk_data)
        
        if not batch_chunks:
            update_progress(0.95, "没有有效的chunks")
            return 0
        
        # 调用增强的batch接口
        import requests
        import json
        
        # 获取API基本信息
        base_url = doc.rag.api_url
        headers = doc.rag.authorization_header
        
        # 构建请求数据
        request_data = {
            "chunks": batch_chunks,
            "batch_size": 20
        }
        
        # 如果有父子分块数据，添加到请求中
        if parent_child_data:
            request_data["parent_child_data"] = parent_child_data
        
        # 调用增强的batch接口
        api_url = f"{base_url}/datasets/{doc.dataset_id}/documents/{doc.id}/chunks/batch"
        
        response = requests.post(api_url, json=request_data, headers=headers)
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get("code") == 0:
                    # 批量添加成功
                    data = result.get("data", {})
                    added = data.get("total_added", 0)
                    failed = data.get("total_failed", 0)
                    
                    update_progress(0.95, f"batch处理完成: 成功 {added}/{len(batch_chunks)} chunks")
                    return added
                else:
                    # 批量添加失败
                    error_msg = result.get("message", "Unknown error")
                    update_progress(0.95, f"batch处理失败: {error_msg}")
                    return 0
            except json.JSONDecodeError:
                update_progress(0.95, "响应解析失败")
                return 0
        else:
            update_progress(0.95, f"HTTP错误: {response.status_code}")
            return 0
        
    except Exception as e:
        update_progress(0.95, f"增强batch处理异常: {str(e)}")
        return 0



def _cleanup_temp_files(md_file_path):
    """清理临时文件"""
    if not should_cleanup_temp_files():
        return
    
    try:
        temp_dir = os.path.dirname(os.path.abspath(md_file_path))
        shutil.rmtree(temp_dir)
    except Exception as e:
        pass

def create_ragflow_resources(doc_id, kb_id, md_file_path, image_dir, update_progress):
    """
    使用增强文本创建RAGFlow知识库和聊天助手
    """
    try:
        doc, dataset = get_ragflow_doc(doc_id, kb_id)

        _upload_images(kb_id, image_dir, update_progress)

        # 获取文档的分块配置
        chunking_config = _get_document_chunking_config(doc_id)

        # 检查是否有 middle.json 文件
        middle_json_path = md_file_path.replace('.md', '_middle.json')
        use_simple_method = os.path.exists(middle_json_path)

        if use_simple_method:
            # 使用新方法：从 middle.json 生成 markdown
            markdown_from_middle_path = md_file_path.replace('.md', '_from_middle.md')
            enhanced_text = middle_json_to_markdown(middle_json_path, markdown_from_middle_path, kb_id=kb_id)
            # 坐标查询基于新生成的 markdown
            coord_lookup_path = markdown_from_middle_path
        else:
            # 使用原方法
            enhanced_text = update_markdown_image_urls(md_file_path, kb_id)
            coord_lookup_path = None
        
        
        # 传递分块配置给分块函数
        if chunking_config:
            chunks = split_markdown_to_chunks_configured(
                enhanced_text, 
                chunk_token_num=chunking_config.get('chunk_token_num', 256),
                min_chunk_tokens=chunking_config.get('min_chunk_tokens', 10),
                chunking_config=chunking_config,
                doc_id=doc_id,
                kb_id=kb_id
            )
        else:
            chunks = split_markdown_to_chunks_configured(enhanced_text, chunk_token_num=256)

        # 准备父子分块数据（如果使用了父子分块策略）
        parent_child_data = None
        is_parent_child = (chunking_config and 
                          chunking_config.get('strategy') == 'parent_child')
        
        if is_parent_child:
            # 获取父子分块的详细结果
            from .utils import get_last_parent_child_result
            parent_child_result = get_last_parent_child_result()
            
            if parent_child_result:
                # 准备父子分块数据
                parent_child_data = {
                    'doc_id': doc_id,
                    'kb_id': kb_id,
                    'parent_chunks': parent_child_result.get('parent_chunks', []),
                    'child_chunks': parent_child_result.get('child_chunks', []),
                    'relationships': parent_child_result.get('relationships', [])
                }
                
                # 对于父子分块，使用子分块内容
                chunks = [chunk['content'] for chunk in parent_child_data['child_chunks']]
        
        # 统一分块处理 - 优化后统一使用增强的batch接口（支持父子分块和标准分块）
        chunk_content_to_index = {chunk: i for i, chunk in enumerate(chunks)}
        # 传递坐标查询路径（如果使用新方法）
        chunk_count = add_chunks_with_enhanced_batch_api(doc, chunks, md_file_path, chunk_content_to_index, update_progress, parent_child_data=parent_child_data, coord_lookup_path=coord_lookup_path)
        # 根据环境变量决定是否清理临时文件
        _cleanup_temp_files(md_file_path)

        # 确保进度更新到100%
        update_progress(1.0, f"处理完成！成功处理 {chunk_count} 个chunks")
        return chunk_count

    except Exception as e:
        try:
            update_progress(1.0, f"处理过程中发生异常: {str(e)}")
        except Exception:
            pass
        raise
