from ragflow_sdk import RAGFlow
import os
import time
import shutil
import json
from dotenv import load_dotenv
from .minio_server import upload_directory_to_minio
from .mineru_test import update_markdown_image_urls
from .utils import split_markdown_to_chunks_configured, get_bbox_for_chunk, should_cleanup_temp_files
from .middle_json_simple import middle_json_to_markdown, get_chunk_coordinates
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
                        print(f"📍 chunk {original_index}: DOTS坐标 ({len(chunk_with_coord['positions'])} 个位置) + 索引排序 (page=1, top={original_index})")
                        position_found = True
                
                # 如果没有直接坐标，尝试获取坐标
                if not position_found:
                    # 优先使用新的简化方法
                    if coord_lookup_path:
                        try:
                            print(f"🔍 [DEBUG] 使用新方法查询坐标，路径: {coord_lookup_path}")
                            print(f"🔍 [DEBUG] 查询文本: {chunk.strip()[:50]}...")
                            # 使用新方法查询坐标
                            coords = get_chunk_coordinates(coord_lookup_path, chunk.strip())
                            print(f"🔍 [DEBUG] 查询结果: {len(coords) if coords else 0} 个坐标")
                            if coords:
                                # 转换坐标格式为 RAGFlow 需要的格式
                                positions = [[int(c[0]), c[1], c[2], c[3], c[4]] for c in coords]
                                chunk_data["positions"] = positions
                                print(f"📍 chunk {original_index}: 使用新方法找到精确坐标 ({len(positions)} 个位置) + 索引排序 (page=1, top={original_index})")
                                position_found = True
                            else:
                                print(f"📍 chunk {original_index}: 新方法未找到坐标，使用索引排序 (page=1, top={original_index})")
                        except Exception as e:
                            import traceback
                            print(f"📍 chunk {original_index}: 新方法查询异常 {e}，使用索引排序 (page=1, top={original_index})")
                            traceback.print_exc()

                    # 如果新方法没有找到，尝试旧方法（兼容性）
                    elif md_file_path is not None:
                        try:
                            position_int_temp = get_bbox_for_chunk(md_file_path, chunk.strip())
                            if position_int_temp is not None:
                                # 有完整位置信息时，仅添加positions，不覆盖排序字段
                                chunk_data["positions"] = position_int_temp
                                print(f"📍 chunk {original_index}: 使用旧方法找到坐标 ({len(position_int_temp)} 个位置) + 索引排序 (page=1, top={original_index})")
                                position_found = True
                            else:
                                print(f"📍 chunk {original_index}: 旧方法未找到坐标，使用索引排序 (page=1, top={original_index})")
                        except Exception as pos_e:
                            print(f"📍 chunk {original_index}: 旧方法坐标获取异常，使用索引排序 (page=1, top={original_index})")
                
                # 如果都没有找到坐标
                if not position_found:
                    if md_file_path is None and chunks_with_coordinates is None:
                        print(f"📍 chunk {original_index}: 无MD文件和坐标数据，使用索引排序 (page=1, top={original_index})")
                    elif chunks_with_coordinates is None:
                        print(f"📍 chunk {original_index}: 无坐标数据，使用索引排序 (page=1, top={original_index})")
                    else:
                        print(f"📍 chunk {original_index}: 坐标数据为空，使用索引排序 (page=1, top={original_index})")
                
                batch_chunks.append(chunk_data)
        
        if not batch_chunks:
            update_progress(0.95, "没有有效的chunks")
            return 0
        
        print(f"📦 准备调用增强的batch接口处理 {len(batch_chunks)} 个有效chunks")
        
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
            print(f"🔗 [INFO] 添加父子分块数据到batch请求: {len(parent_child_data.get('parent_chunks', []))} 父分块, {len(parent_child_data.get('relationships', []))} 映射关系")
        
        # 调用增强的batch接口
        api_url = f"{base_url}/datasets/{doc.dataset_id}/documents/{doc.id}/chunks/batch"
        print(f"🔗 发送增强batch请求到: {api_url}")
        
        response = requests.post(api_url, json=request_data, headers=headers)
        
        print(f"📥 增强batch接口响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get("code") == 0:
                    # 批量添加成功
                    data = result.get("data", {})
                    added = data.get("total_added", 0)
                    failed = data.get("total_failed", 0)
                    
                    print(f"✅ 增强batch接口处理完成: 成功 {added} 个，失败 {failed} 个")
                    
                    if parent_child_data:
                        print(f"🔗 父子分块处理也已完成")
                    
                    update_progress(0.95, f"batch处理完成: 成功 {added}/{len(batch_chunks)} chunks")
                    return added
                else:
                    # 批量添加失败
                    error_msg = result.get("message", "Unknown error")
                    print(f"❌ 增强batch接口失败: {error_msg}")
                    update_progress(0.95, f"batch处理失败: {error_msg}")
                    return 0
            except json.JSONDecodeError:
                print(f"❌ 增强batch接口响应解析失败")
                update_progress(0.95, "响应解析失败")
                return 0
        else:
            print(f"❌ 增强batch接口HTTP错误: {response.status_code}")
            update_progress(0.95, f"HTTP错误: {response.status_code}")
            return 0
        
    except Exception as e:
        update_progress(0.95, f"增强batch处理异常: {str(e)}")
        print(f"❌ 增强batch处理异常: {e}")
        import traceback
        traceback.print_exc()
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
            print(f"✅ 检测到 middle.json，使用新的简化方法处理")
            print(f"📂 middle.json 路径: {middle_json_path}")
            # 使用新方法：从 middle.json 生成 markdown
            markdown_from_middle_path = md_file_path.replace('.md', '_from_middle.md')
            print(f"📝 生成 markdown 路径: {markdown_from_middle_path}")
            # 直接传入 kb_id，让 middle_json_to_markdown 处理图片路径
            enhanced_text = middle_json_to_markdown(middle_json_path, markdown_from_middle_path, kb_id=kb_id)
            print(f"📄 生成的 markdown 长度: {len(enhanced_text)} 字符")
            # 检查坐标文件是否生成
            coord_file_path = markdown_from_middle_path.replace('.md', '_coords.json')
            if os.path.exists(coord_file_path):
                print(f"✅ 坐标文件已生成: {coord_file_path}")
                import json
                with open(coord_file_path, 'r') as f:
                    coords_data = json.load(f)
                    print(f"📍 坐标映射数量: {len(coords_data)}")
            else:
                print(f"❌ 坐标文件未生成: {coord_file_path}")
            # 图片URL已在 middle_json_to_markdown 中处理，不需要再更新
            # 保存用于坐标查询的路径
            coord_lookup_path = markdown_from_middle_path
        else:
            # 使用原方法
            enhanced_text = update_markdown_image_urls(md_file_path, kb_id)
            coord_lookup_path = None

        # 保存原始markdown到本地用于调试
        try:
            debug_md_path = f"/tmp/debug_markdown_{doc_id}_{kb_id}.md"
            with open(debug_md_path, 'w', encoding='utf-8') as f:
                f.write(enhanced_text)
            print(f"🔍 [DEBUG] 原始markdown已保存到: {debug_md_path}")
        except Exception as e:
            pass
        
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
                print(f"🎯 [INFO] 检测到父子分块策略，将使用增强的batch接口处理")
                print(f"  👨 父分块数: {parent_child_result.get('total_parents', 0)}")
                print(f"  👶 子分块数: {parent_child_result.get('total_children', 0)}")
                
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
        import traceback
        traceback.print_exc()

        try:
            update_progress(1.0, f"处理过程中发生异常: {str(e)}")
        except Exception as progress_e:
            pass
        
        raise
