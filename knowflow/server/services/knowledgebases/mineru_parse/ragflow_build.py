from ragflow_sdk import RAGFlow
import os
import time
import shutil
import json
from .minio_server import upload_directory_to_minio
from .mineru_test import update_markdown_image_urls
from .utils import split_markdown_to_chunks_configured, should_cleanup_temp_files
from .middle_json_simple import middle_json_to_markdown
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


def add_chunks_with_enhanced_batch_api(doc, chunks, md_file_path, chunk_content_to_index, update_progress, parent_child_data=None, chunks_with_coordinates=None):
    """
    使用增强的batch接口处理分块（支持父子分块和坐标传递）

    Args:
        doc: RAGFlow文档对象
        chunks: 分块内容列表
        md_file_path: markdown文件路径
        chunk_content_to_index: 分块内容到索引的映射
        update_progress: 进度更新回调
        parent_child_data: 父子分块数据（可选）
        chunks_with_coordinates: 包含坐标信息的分块数据（可选，方案A：坐标已在分块时附加）

    Returns:
        int: 成功添加的分块数量
    """
    
    if not chunks:
        update_progress(0.8, "没有chunks需要添加")
        return 0
    
    # 初始进度更新
    update_progress(0.8, "开始批量添加chunks到文档（使用增强batch接口）...")
    
    try:
        # 准备批量数据，包含位置信息（方案A：坐标已在分块时附加）
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

                # 方案A：从chunks_with_coordinates获取坐标（坐标已在分块时附加）
                if chunks_with_coordinates and i < len(chunks_with_coordinates):
                    chunk_with_coord = chunks_with_coordinates[i]
                    if chunk_with_coord:
                        # 检查positions字段（统一分块接口已转换为positions格式）
                        positions = chunk_with_coord.get('positions')
                        if positions:
                            chunk_data["positions"] = positions
                        else:
                            # 向后兼容：检查coordinates字段
                            coords = chunk_with_coord.get('coordinates', [])
                            if coords:
                                # 转换为 positions 格式: [page_idx, x1, x2, y1, y2]
                                positions = [[int(c[0]), c[1], c[2], c[3], c[4]] for c in coords]
                                chunk_data["positions"] = positions

                batch_chunks.append(chunk_data)
        
        if not batch_chunks:
            update_progress(0.95, "没有有效的chunks")
            return 0

        # 统计坐标信息（调试）
        chunks_with_positions = sum(1 for c in batch_chunks if 'positions' in c and c['positions'])
        total_positions = sum(len(c.get('positions', [])) for c in batch_chunks)
        print(f"🔍 [DEBUG] batch_chunks 统计:")
        print(f"   - 总分块数: {len(batch_chunks)}")
        print(f"   - 有坐标分块: {chunks_with_positions}")
        print(f"   - 总坐标数: {total_positions}")
        if batch_chunks:
            first_chunk = batch_chunks[0]
            print(f"   - 第一个分块字段: {list(first_chunk.keys())}")
            if 'positions' in first_chunk:
                print(f"   - 第一个分块坐标数: {len(first_chunk['positions'])}")
                print(f"   - 第一个坐标: {first_chunk['positions'][0]}")

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

        coordinate_map = None
        if use_simple_method:
            # 使用新方法：从 middle.json 生成 markdown（方案A：同时获取coordinate_map）
            markdown_from_middle_path = md_file_path.replace('.md', '_from_middle.md')
            enhanced_text, coordinate_map = middle_json_to_markdown(middle_json_path, markdown_from_middle_path, kb_id=kb_id)
        else:
            # 使用原方法
            enhanced_text = update_markdown_image_urls(md_file_path, kb_id)


        # 传递分块配置给分块函数（方案A：传入coordinate_map）
        if chunking_config:
            chunks = split_markdown_to_chunks_configured(
                enhanced_text,
                chunk_token_num=chunking_config.get('chunk_token_num', 256),
                min_chunk_tokens=chunking_config.get('min_chunk_tokens', 10),
                chunking_config=chunking_config,
                doc_id=doc_id,
                kb_id=kb_id,
                coordinate_map=coordinate_map  # 方案A：传入coordinate_map
            )
        else:
            chunks = split_markdown_to_chunks_configured(
                enhanced_text,
                chunk_token_num=256,
                coordinate_map=coordinate_map  # 方案A：传入coordinate_map
            )

        # 处理分块结果（方案A：chunks 是字典列表，包含 content 和 coordinates）
        chunks_with_coordinates = None
        chunk_contents = []

        # 检查 chunks 格式
        if chunks and isinstance(chunks[0], dict):
            # 方案A：字典格式，包含坐标
            chunks_with_coordinates = chunks
            chunk_contents = [chunk.get('content', '') for chunk in chunks]
        else:
            # 字符串列表（向后兼容）
            chunk_contents = chunks

        # 准备父子分块数据（如果使用了父子分块策略）
        parent_child_data = None
        is_parent_child = (chunking_config and
                          chunking_config.get('strategy') == 'parent_child')

        if is_parent_child:
            # 获取父子分块的详细结果（已包含坐标信息）
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

                # 父子分块：需要同步坐标信息
                if chunks_with_coordinates:
                    # 方案A：chunks 已经是带坐标的字典列表
                    # 将坐标信息同步到 chunks_with_coordinates（如果 parent_child_result.child_chunks 也有坐标）
                    child_chunks = parent_child_result.get('child_chunks', [])
                    if child_chunks and isinstance(child_chunks[0], dict) and 'coordinates' in child_chunks[0]:
                        print(f"✅ [DEBUG] parent_child_result.child_chunks 已包含坐标")
                        # 使用 child_chunks（已包含坐标）
                        chunks_with_coordinates = child_chunks
                        chunk_contents = [chunk.get('content', '') for chunk in child_chunks]
                else:
                    # 使用子分块内容
                    chunk_contents = [chunk['content'] for chunk in parent_child_data['child_chunks']]

        # 统一分块处理 - 优化后统一使用增强的batch接口（支持父子分块和标准分块）
        chunk_content_to_index = {content: i for i, content in enumerate(chunk_contents)}
        # 方案A：chunks_with_coordinates 包含坐标信息
        chunk_count = add_chunks_with_enhanced_batch_api(
            doc, chunk_contents, md_file_path, chunk_content_to_index,
            update_progress, parent_child_data=parent_child_data,
            chunks_with_coordinates=chunks_with_coordinates
        )
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
