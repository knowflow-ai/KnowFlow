#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOTS OCR 结果处理器

使用 DOTS 官方方法将 OCR 结果转换为 RAGFlow 兼容的格式，支持:
- 布局元素提取和分类
- 官方 Markdown 转换（自动去除页眉页脚）
- 智能分块生成和坐标映射
"""

import json
import logging
import os
import tempfile
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

from .dots_json_converter import DotsJsonConverter

logger = logging.getLogger(__name__)

class DOTSLayoutElement:
    """DOTS布局元素类"""
    
    def __init__(self, element_data: Dict[str, Any]):
        """初始化布局元素
        
        Args:
            element_data: DOTS返回的单个布局元素数据
        """
        self.bbox = element_data.get('bbox', [0, 0, 0, 0])
        self.category = element_data.get('category', 'Text')
        self.text = element_data.get('text', '')
        self.confidence = element_data.get('confidence', 1.0)
        self.page_number = element_data.get('page_number', 1)  # 添加页面编号
        
        # 计算元素面积和位置信息
        if len(self.bbox) == 4 and all(isinstance(coord, (int, float)) for coord in self.bbox):
            # 确保坐标是数值类型
            self.x1, self.y1, self.x2, self.y2 = [float(coord) for coord in self.bbox]
            self.width = abs(self.x2 - self.x1)
            self.height = abs(self.y2 - self.y1)
            self.area = self.width * self.height
            self.center_x = (self.x1 + self.x2) / 2
            self.center_y = (self.y1 + self.y2) / 2
            
            # 确保坐标顺序正确 (x1 <= x2, y1 <= y2)
            if self.x1 > self.x2:
                self.x1, self.x2 = self.x2, self.x1
            if self.y1 > self.y2:
                self.y1, self.y2 = self.y2, self.y1
            
            # 更新bbox以保持一致性
            self.bbox = [self.x1, self.y1, self.x2, self.y2]
        else:
            logger.warning(f"无效的DOTS bbox数据: {self.bbox}")
            self.width = self.height = self.area = 0
            self.center_x = self.center_y = 0
            self.x1 = self.y1 = self.x2 = self.y2 = 0
    
    
    def __repr__(self):
        return f"DOTSLayoutElement(category={self.category}, bbox={self.bbox}, text='{self.text[:50]}...')"

class DOTSProcessor:
    """DOTS OCR结果处理器"""
    
    def __init__(self, kb_id: Optional[str] = None):
        """初始化处理器"""
        self.kb_id = kb_id
        self.elements = []
        self.pages_data = []
        self.converter = DotsJsonConverter(kb_id=kb_id)
        self.coordinate_map: Dict[int, List[int]] = {}
        self.markdown_content: str = ""
        self.markdown_lines: List[str] = []
    
    def process_page_result(self, page_result: Dict[str, Any]) -> List[DOTSLayoutElement]:
        """处理单页的DOTS解析结果
        
        Args:
            page_result: DOTS适配器返回的页面解析结果
            
        Returns:
            list: DOTSLayoutElement对象列表
        """
        elements = []
        
        if not page_result.get('success', False):
            logger.warning(f"页面解析失败: {page_result.get('error', 'Unknown error')}")
            return elements
        
        layout_elements = page_result.get('layout_elements', [])
        
        for element_data in layout_elements:
            try:
                element = DOTSLayoutElement(element_data)
                elements.append(element)
            except Exception as e:
                logger.warning(f"处理布局元素失败: {e}, 元素数据: {element_data}")
        
        logger.info(f"成功处理 {len(elements)} 个布局元素")
        return elements
    
    def process_document_results(self, document_results: List[Dict[str, Any]]) -> List[DOTSLayoutElement]:
        """处理整个文档的DOTS解析结果
        
        Args:
            document_results: 所有页面的解析结果列表
            
        Returns:
            list: 所有页面的DOTSLayoutElement对象列表
        """
        all_elements = []
        
        for i, page_result in enumerate(document_results):
            logger.info(f"处理第 {i+1}/{len(document_results)} 页结果")
            
            page_elements = self.process_page_result(page_result)
            
            # 为每个元素添加页面信息
            for element in page_elements:
                element.page_number = page_result.get('page_number', i + 1)
                all_elements.append(element)
        
        self.elements = all_elements
        self.pages_data = document_results
        
        logger.info(f"文档处理完成，共 {len(all_elements)} 个元素，{len(document_results)} 页")
        return all_elements
    
    def to_markdown(self, output_dir: str = None) -> tuple:
        """将所有元素转换为Markdown格式的文档，并保留坐标映射
        
        Args:
            output_dir: 图片输出目录，可选
            
        Returns:
            tuple: (markdown_text, extracted_images_list)
        """
        if not self.elements or not self.pages_data:
            return "", []
        
        try:
            markdown_content, coordinate_map, extracted_images = self.converter.convert_pages_to_markdown_with_coordinates(
                pages_data=self.pages_data,
                output_dir=output_dir
            )

            # 持久化关键信息，供后续坐标映射使用
            self.coordinate_map = coordinate_map or {}
            self.update_markdown_cache(markdown_content)

            return markdown_content, coordinate_map, extracted_images

        except Exception as e:
            logger.error(f"DOTS markdown 转换失败: {e}")
            return "", {}, []

    def update_markdown_cache(self, markdown_content: Optional[str]):
        """更新缓存的 markdown 内容和行列表"""
        self.markdown_content = markdown_content or ""
        self.markdown_lines = self.markdown_content.split('\n') if self.markdown_content else []
    
    
    def generate_chunks_unified(self, chunking_config: Optional[dict] = None,
                               doc_id: str = None,
                               kb_id: str = None,
                               output_dir: str = None) -> Dict[str, Any]:
        """统一的分块生成方法 - 完全复用MinerU分块策略
        
        Args:
            chunking_config: 完整分块配置（包含strategy、chunk_token_num等）
            doc_id: 文档ID（父子分块需要）
            kb_id: 知识库ID（父子分块需要）
            output_dir: 图片输出目录（可选）
            
        Returns:
            dict: 包含分块数据和提取图片的字典
        """
        if not self.elements:
            return {'success': False, 'chunks': [], 'extracted_images': []}
        
        try:
            # 1. 生成完整的Markdown文档
            markdown_content, coordinate_map, extracted_images = self.to_markdown(output_dir=output_dir)
            if not markdown_content.strip():
                logger.warning("完整Markdown内容为空")
                return {'success': False, 'chunks': [], 'extracted_images': []}
            
            logger.info(f"DOTS统一分块开始: 文档长度={len(markdown_content)} 字符")
            
            # 2. 准备DOTS元素数据用于坐标映射
            dots_elements = self._prepare_dots_elements_for_unified_mapping()
            
            # 3. 调用统一分块接口（完全复用MinerU逻辑）
            from ..common.chunking_interface import UnifiedChunkingInterface
            
            # 使用默认配置如果没有提供
            if not chunking_config:
                chunking_config = {
                    'strategy': 'smart',
                    'chunk_token_num': 256,
                    'min_chunk_tokens': 10
                }
            
            logger.info(f"DOTS调用统一分块接口: strategy={chunking_config.get('strategy')}")
            
            result = UnifiedChunkingInterface.chunk_with_coordinates(
                markdown_content=markdown_content,
                elements_data=dots_elements,
                chunking_config=chunking_config,
                coordinate_source='dots',
                doc_id=doc_id,
                kb_id=kb_id,
                coordinate_map=coordinate_map,
                markdown_lines=self.markdown_lines
            )
            
            # 4. 添加DOTS特有信息
            result.update({
                'success': True,
                'extracted_images': extracted_images,
                'elements_count': len(self.elements),
                'pages_count': len(set(e.page_number for e in self.elements)),
                'markdown_content': markdown_content,
                'processor': self
            })
            
            logger.info(f"DOTS统一分块完成: strategy={result.get('chunking_strategy')}, "
                       f"chunks={result.get('total_chunks', 0)}, "
                       f"parent_child={result.get('is_parent_child', False)}")
            
            return result
            
        except Exception as e:
            logger.error(f"DOTS统一分块失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'chunks': [],
                'extracted_images': []
            }
    
    def _prepare_dots_elements_for_unified_mapping(self) -> List[Dict[str, Any]]:
        """准备DOTS元素数据，转换为统一格式"""
        elements_data = []
        
        # 按页面和位置排序元素
        sorted_elements = sorted(self.elements, key=lambda e: (e.page_number, e.center_y, e.center_x))
        
        for i, element in enumerate(sorted_elements):
            # 验证坐标数据有效性
            if element.bbox and len(element.bbox) == 4:
                element_data = {
                    'text': element.text,
                    'bbox': element.bbox,  # DOTS格式 [x1, y1, x2, y2]
                    'page_number': element.page_number,
                    'category': element.category,
                    'confidence': element.confidence,
                    'source_type': 'dots',
                    'index': i
                }
                elements_data.append(element_data)
                logger.debug(f"DOTS元素 {i}: page={element.page_number}, bbox={element.bbox}, text='{element.text[:30]}...'")
            else:
                logger.warning(f"跳过无效DOTS元素 {i}: bbox={element.bbox}")
        
        logger.info(f"准备了 {len(elements_data)} 个有效DOTS元素用于统一坐标映射")
        return elements_data
    
    
    def generate_chunks_from_markdown(self, markdown_content: str, 
                                     chunking_config: Optional[dict] = None,
                                     doc_id: str = None,
                                     kb_id: str = None,
                                     enable_coordinates: bool = True) -> Dict[str, Any]:
        """基于已处理的markdown内容生成分块（使用统一分块接口）
        
        Args:
            markdown_content: 已处理的markdown内容（图片URL已更新）
            chunking_config: 完整分块配置
            doc_id: 文档ID（父子分块需要）
            kb_id: 知识库ID（父子分块需要）
            enable_coordinates: 是否启用坐标映射
            
        Returns:
            dict: 包含分块数据的字典
        """
        if not self.elements or not markdown_content.strip():
            return {'success': False, 'chunks': []}
        
        logger.info(f"DOTS基于已处理markdown进行统一分块，文档长度: {len(markdown_content)} 字符")
        
        try:
            # 更新缓存的markdown信息，确保坐标映射与最新内容保持一致
            self.update_markdown_cache(markdown_content)

            # 准备DOTS元素数据（向后兼容）
            dots_elements = self._prepare_dots_elements_for_unified_mapping()
            
            # 调用统一分块接口
            from ..common.chunking_interface import UnifiedChunkingInterface
            
            # 使用默认配置如果没有提供
            if not chunking_config:
                chunking_config = {
                    'strategy': 'smart',
                    'chunk_token_num': 256,
                    'min_chunk_tokens': 10
                }
            
            result = UnifiedChunkingInterface.chunk_with_coordinates(
                markdown_content=markdown_content,
                elements_data=dots_elements if enable_coordinates else [],
                chunking_config=chunking_config,
                coordinate_source='dots',
                doc_id=doc_id,
                kb_id=kb_id,
                coordinate_map=self.coordinate_map if enable_coordinates else None,
                markdown_lines=self.markdown_lines if enable_coordinates else None
            )
            
            result['success'] = True
            logger.info(f"DOTS markdown统一分块完成: strategy={result.get('chunking_strategy')}, "
                       f"chunks={result.get('total_chunks', 0)}, "
                       f"parent_child={result.get('is_parent_child', False)}")
            
            return result
            
        except Exception as e:
            logger.error(f"DOTS markdown统一分块失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'chunks': []
            }
        
    
    
    
    
    
    
    
    
    
    
    def save_debug_info(self, output_dir: str):
        """保存调试信息到文件
        
        Args:
            output_dir: 输出目录路径
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 保存Markdown文档
        markdown_content, _, _ = self.to_markdown()
        with open(output_path / 'dots_output.md', 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # 保存原始JSON数据
        with open(output_path / 'dots_raw_data.json', 'w', encoding='utf-8') as f:
            json.dump(self.pages_data, f, ensure_ascii=False, indent=2)
        
        # 保存元素统计信息
        stats = {
            'total_elements': len(self.elements),
            'pages_count': len(set(e.page_number for e in self.elements)),
            'categories': {},
            'elements_summary': []
        }
        
        for element in self.elements:
            # 统计类别
            category = element.category
            if category not in stats['categories']:
                stats['categories'][category] = 0
            stats['categories'][category] += 1
            
            # 元素摘要
            stats['elements_summary'].append({
                'page': element.page_number,
                'category': element.category,
                'bbox': element.bbox,
                'text_preview': element.text[:100] if element.text else ''
            })
        
        with open(output_path / 'dots_stats.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"调试信息已保存到: {output_path}")

def process_dots_result(document_results: List[Dict[str, Any]], 
                       kb_id: str = None,
                       temp_dir: str = None,
                       chunking_config: Optional[dict] = None,
                       doc_id: str = None,
                       debug_output_dir: Optional[str] = None) -> Dict[str, Any]:
    """处理DOTS文档解析结果的便捷函数（使用统一分块接口）
    
    Args:
        document_results: DOTS适配器返回的文档解析结果
        kb_id: 知识库ID
        temp_dir: 临时目录
        chunking_config: 完整的分块配置（包含策略和参数）
        doc_id: 文档ID（父子分块需要）
        debug_output_dir: 调试信息输出目录，可选
        
    Returns:
        dict: 包含处理结果的字典
    """
    processor = DOTSProcessor(kb_id=kb_id)
    
    # 处理解析结果
    elements = processor.process_document_results(document_results)
    
    # 第一步：生成包含相对路径图片的markdown和提取图片
    image_output_dir = None
    if temp_dir and kb_id:
        image_output_dir = os.path.join(temp_dir, 'images')
    
    # 生成markdown并提取图片
    if image_output_dir:
        markdown_content, coordinate_map, extracted_images = processor.to_markdown(output_dir=image_output_dir)
    else:
        markdown_content, coordinate_map, extracted_images = processor.to_markdown()
    
    # 第二步：如果有图片，先处理图片上传和URL更新，然后再进行分块
    if extracted_images and kb_id and temp_dir:
        try:
            # 复用MinerU的图片处理逻辑
            from ..mineru_parse.minio_server import upload_directory_to_minio
            from ..mineru_parse.mineru_test import update_markdown_image_urls
            
            # 检查图片目录是否存在
            if os.path.exists(image_output_dir):
                # 上传图片到MinIO
                success = upload_directory_to_minio(kb_id, image_output_dir)
                
                if success:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_file:
                        tmp_file.write(markdown_content)
                        tmp_md_path = tmp_file.name
                    
                    # 更新markdown中的图片URL
                    updated_markdown = update_markdown_image_urls(tmp_md_path, kb_id)
                    
                    if updated_markdown:
                        markdown_content = updated_markdown
                        processor.update_markdown_cache(markdown_content)
                        logger.info(f"已更新 {len(extracted_images)} 个图片URL为MinIO格式")
                    
                    # 清理临时文件
                    os.unlink(tmp_md_path)
                else:
                    logger.warning("图片上传失败，使用原始markdown")
            else:
                logger.warning(f"图片输出目录不存在: {image_output_dir}")
                
        except Exception as e:
            logger.warning(f"图片处理失败，使用原始markdown: {e}")
            import traceback
            logger.debug(f"图片处理异常详情: {traceback.format_exc()}")
    
    # 第三步：基于处理后的markdown（已包含正确的图片URL）进行统一分块
    result = processor.generate_chunks_from_markdown(
        markdown_content=markdown_content,
        chunking_config=chunking_config,
        doc_id=doc_id,
        kb_id=kb_id,
        enable_coordinates=True
    )
    
    if not result.get('success', False):
        logger.error(f"DOTS统一分块失败: {result.get('error', 'Unknown error')}")
        return {
            'success': False,
            'error': result.get('error', 'Chunking failed'),
            'chunks': [],
            'extracted_images': extracted_images
        }
    
    chunks = result['chunks']
    
    # 图片处理已在分块之前完成，这里只记录结果
    logger.info(f"DOTS统一分块生成完成: {len(chunks)} 个分块, 包含图片: {len(extracted_images)} 个")
    
    # 保存调试信息（如果指定了输出目录）
    if debug_output_dir:
        processor.save_debug_info(debug_output_dir)
    
    # 从统一分块结果中获取详细信息
    chunking_strategy_used = result.get('chunking_strategy', 'smart')
    is_parent_child = result.get('is_parent_child', False)
    
    logger.info(f"DOTS统一处理完成: {len(elements)}个元素, {len(chunks)}个分块, "
               f"策略={chunking_strategy_used}, 父子分块={is_parent_child}")
    
    # 构建返回结果，包含统一分块的所有信息
    final_result = {
        'success': True,
        'elements_count': len(elements),
        'pages_count': len(set(e.page_number for e in elements)),
        'markdown_content': markdown_content,
        'chunks': chunks,
        'extracted_images': extracted_images,
        'chunking_strategy': chunking_strategy_used,
        'processor': processor,  # 返回处理器实例以便进一步操作
        'coordinate_map': coordinate_map,

        # 统一分块接口的额外信息
        'coordinate_source': result.get('coordinate_source', 'dots'),
        'has_coordinates': result.get('has_coordinates', False),
        'total_chunks': result.get('total_chunks', len(chunks))
    }
    
    # 如果是父子分块，添加父子分块详细信息
    if is_parent_child:
        final_result.update({
            'is_parent_child': True,
            'parent_chunks': result.get('parent_chunks', []),
            'child_chunks': result.get('child_chunks', []),
            'relationships': result.get('relationships', []),
            'total_parents': result.get('total_parents', 0),
            'total_children': result.get('total_children', 0)
        })
        logger.info(f"DOTS父子分块详情: {final_result['total_parents']}父块, {final_result['total_children']}子块")
    
    return final_result
