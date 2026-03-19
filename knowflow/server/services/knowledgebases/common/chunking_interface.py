#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一分块接口模块

提供统一的分块策略接口，支持不同的坐标来源（DOTS/MinerU），
完全复用MinerU的所有分块策略，包括父子分块功能。
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class UnifiedChunkingInterface:
    """统一的分块策略接口"""
    
    @staticmethod
    def chunk_with_coordinates(markdown_content: str,
                              elements_data: List[Dict],
                              chunking_config: Optional[dict] = None,
                              coordinate_source: str = 'mineru',
                              doc_id: str = None,
                              kb_id: str = None,
                              coordinate_map: Optional[Dict] = None,
                              markdown_lines: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        统一的分块接口，支持不同坐标来源
        
        Args:
            markdown_content: 待分块的Markdown内容
            elements_data: 元素数据（DOTS或MinerU格式）
            chunking_config: 分块配置
            coordinate_source: 坐标来源 ('dots' or 'mineru')
            doc_id: 文档ID（父子分块需要）
            kb_id: 知识库ID（父子分块需要）
            coordinate_map: 行号到坐标的映射（DOTS场景）
            markdown_lines: Markdown 行列表（DOTS场景）
            
        Returns:
            包含分块结果和坐标信息的字典
        """
        try:
            logger.info(f"开始统一分块处理: 来源={coordinate_source}, 内容长度={len(markdown_content)}")
            
            # 1. 调用MinerU分块策略（完全复用，方案A：传入coordinate_map）
            chunks_result = UnifiedChunkingInterface._call_mineru_chunking(
                markdown_content, chunking_config, doc_id, kb_id, coordinate_map
            )
            
            # 2. 根据坐标来源选择映射方法
            if coordinate_source == 'dots':
                coordinates_result = UnifiedChunkingInterface._map_dots_coordinates(
                    chunks_result,
                    elements_data,
                    coordinate_map=coordinate_map,
                    markdown_lines=markdown_lines
                )
            else:
                coordinates_result = UnifiedChunkingInterface._map_mineru_coordinates(
                    chunks_result, elements_data
                )
            
            # 3. 合并结果
            final_result = UnifiedChunkingInterface._merge_chunks_with_coordinates(
                chunks_result, coordinates_result, chunking_config
            )
            
            logger.info(f"统一分块完成: 策略={final_result.get('chunking_strategy')}, "
                       f"分块数={final_result.get('total_chunks', 0)}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"统一分块处理失败: {e}")
            raise
    
    @staticmethod
    def _call_mineru_chunking(markdown_content: str,
                             chunking_config: Optional[dict],
                             doc_id: str,
                             kb_id: str,
                             coordinate_map: Optional[Dict] = None) -> Dict[str, Any]:
        """调用MinerU分块策略"""
        try:
            # 导入MinerU分块函数
            from ..mineru_parse.utils import split_markdown_to_chunks_configured

            # 准备分块参数
            chunk_token_num = 256
            min_chunk_tokens = 10
            strategy = 'smart'

            if chunking_config:
                chunk_token_num = chunking_config.get('chunk_token_num', 256)
                min_chunk_tokens = chunking_config.get('min_chunk_tokens', 10)
                strategy = chunking_config.get('strategy', 'smart')

            logger.info(f"调用MinerU分块: strategy={strategy}, chunk_size={chunk_token_num}, has_coordinate_map={coordinate_map is not None}")

            # 调用MinerU统一分块接口（方案A：直接传入coordinate_map）
            chunks = split_markdown_to_chunks_configured(
                markdown_content,
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                chunking_config=chunking_config,
                doc_id=doc_id,
                kb_id=kb_id,
                coordinate_map=coordinate_map
            )
            
            # 检查是否为父子分块
            is_parent_child = (chunking_config and 
                              chunking_config.get('strategy') == 'parent_child')
            
            result = {
                'chunks': chunks,
                'chunking_strategy': strategy,
                'is_parent_child': is_parent_child,
                'chunk_token_num': chunk_token_num,
                'min_chunk_tokens': min_chunk_tokens
            }
            
            # 如果是父子分块，获取详细结果
            if is_parent_child:
                from ..mineru_parse.utils import get_last_parent_child_result
                parent_child_result = get_last_parent_child_result()
                
                if parent_child_result:
                    result.update({
                        'parent_chunks': parent_child_result.get('parent_chunks', []),
                        'child_chunks': parent_child_result.get('child_chunks', []),
                        'relationships': parent_child_result.get('relationships', []),
                        'total_parents': parent_child_result.get('total_parents', 0),
                        'total_children': parent_child_result.get('total_children', 0)
                    })
                    logger.info(f"获取父子分块结果: {result['total_parents']}父块, {result['total_children']}子块")
            
            return result
            
        except Exception as e:
            logger.error(f"调用MinerU分块失败: {e}")
            raise
    
    @staticmethod
    def _map_dots_coordinates(chunks_result: Dict[str, Any],
                              dots_elements: List[Dict],
                              coordinate_map: Optional[Dict] = None,
                              markdown_lines: Optional[List[str]] = None) -> Dict[str, Any]:
        """映射DOTS坐标（从chunks中提取已附加的坐标）"""
        try:
            chunks = chunks_result['chunks']

            if not chunks:
                return {
                    'coordinates': [],
                    'coordinate_source': 'dots',
                    'has_coordinates': False
                }

            # 提取已附加的坐标
            coordinates = []
            coords_count = 0

            for chunk in chunks:
                if isinstance(chunk, dict) and 'coordinates' in chunk:
                    chunk_coords = chunk.get('coordinates', [])
                    if chunk_coords:
                        # 转换为positions格式: [page_idx, x1, x2, y1, y2]
                        positions = [[int(c[0]), c[1], c[2], c[3], c[4]] for c in chunk_coords]
                        coordinates.append(positions)
                        coords_count += 1
                    else:
                        coordinates.append([])
                else:
                    coordinates.append([])

            logger.info(f"DOTS坐标提取完成: {coords_count}/{len(chunks)} 个分块有坐标")
            return {
                'coordinates': coordinates,
                'coordinate_source': 'dots',
                'has_coordinates': coords_count > 0
            }

        except Exception as e:
            logger.error(f"DOTS坐标提取失败: {e}")
            return {
                'coordinates': [],
                'coordinate_source': 'dots',
                'has_coordinates': False
            }
    
    @staticmethod
    def _map_mineru_coordinates(chunks_result: Dict[str, Any], 
                               mineru_elements: List[Dict]) -> Dict[str, Any]:
        """映射MinerU坐标（保持原有逻辑）"""
        try:
            from .coordinate_mappers import MinerUCoordinateMapper
            
            mapper = MinerUCoordinateMapper()
            chunks = chunks_result['chunks']
            
            coordinates = mapper.map_chunks_to_coordinates(chunks, mineru_elements)
            
            return {
                'coordinates': coordinates,
                'coordinate_source': 'mineru',
                'has_coordinates': len([c for c in coordinates if c]) > 0
            }
            
        except Exception as e:
            logger.error(f"MinerU坐标映射失败: {e}")
            return {
                'coordinates': [],
                'coordinate_source': 'mineru', 
                'has_coordinates': False
            }
    
    @staticmethod
    def _merge_chunks_with_coordinates(chunks_result: Dict[str, Any], 
                                     coordinates_result: Dict[str, Any],
                                     chunking_config: Optional[dict]) -> Dict[str, Any]:
        """合并分块结果和坐标信息"""
        
        # 基础结果
        final_result = {
            'success': True,
            'chunking_strategy': chunks_result.get('chunking_strategy', 'smart'),
            'coordinate_source': coordinates_result.get('coordinate_source', 'unknown'),
            'has_coordinates': coordinates_result.get('has_coordinates', False)
        }
        
        # 处理普通分块或子分块
        chunks = chunks_result['chunks']
        coordinates = coordinates_result['coordinates']
        
        # 为分块添加坐标信息
        chunks_with_coords = []
        for i, chunk_content in enumerate(chunks):
            # 处理字典格式：{'content': '...', 'coordinates': [...]}
            if isinstance(chunk_content, dict):
                content = chunk_content.get('content', '')
                existing_coords = chunk_content.get('coordinates', [])

                chunk_data = {
                    'id': i,
                    'content': content.strip() if isinstance(content, str) else str(content),
                    'chunking_strategy': chunks_result.get('chunking_strategy')
                }

                # 转换coordinates为positions格式
                if existing_coords:
                    positions = [[int(c[0]), c[1], c[2], c[3], c[4]] for c in existing_coords]
                    chunk_data['positions'] = positions
                    chunk_data['has_coordinates'] = True
                elif i < len(coordinates) and coordinates[i]:
                    chunk_data['positions'] = coordinates[i]
                    chunk_data['has_coordinates'] = True
                else:
                    chunk_data['has_coordinates'] = False
            else:
                # 字符串格式（向后兼容）
                chunk_data = {
                    'id': i,
                    'content': chunk_content.strip() if isinstance(chunk_content, str) else str(chunk_content),
                    'chunking_strategy': chunks_result.get('chunking_strategy')
                }

                if i < len(coordinates) and coordinates[i]:
                    chunk_data['positions'] = coordinates[i]
                    chunk_data['has_coordinates'] = True
                else:
                    chunk_data['has_coordinates'] = False

            chunks_with_coords.append(chunk_data)

        final_result['chunks'] = chunks_with_coords
        final_result['total_chunks'] = len(chunks_with_coords)
        
        # 如果是父子分块，添加父子分块信息并处理坐标
        if chunks_result.get('is_parent_child'):
            child_chunks = chunks_result.get('child_chunks', [])
            coordinates = coordinates_result['coordinates']
            
            # 为子分块添加坐标信息
            child_chunks_with_coords = []
            for i, child_chunk in enumerate(child_chunks):
                if hasattr(child_chunk, '__dict__'):
                    # ChunkInfo对象
                    child_chunk_dict = {
                        'id': child_chunk.id if hasattr(child_chunk, 'id') else f"child_{i}",
                        'content': child_chunk.content if hasattr(child_chunk, 'content') else str(child_chunk),
                        'token_count': child_chunk.token_count if hasattr(child_chunk, 'token_count') else 0,
                        'char_count': child_chunk.char_count if hasattr(child_chunk, 'char_count') else 0,
                        'order': child_chunk.order if hasattr(child_chunk, 'order') else i,
                        'metadata': child_chunk.metadata if hasattr(child_chunk, 'metadata') else {}
                    }
                elif isinstance(child_chunk, dict):
                    child_chunk_dict = child_chunk.copy()
                    # 转换coordinates为positions格式
                    existing_coords = child_chunk_dict.pop('coordinates', None)
                    if existing_coords:
                        positions = [[int(c[0]), c[1], c[2], c[3], c[4]] for c in existing_coords]
                        child_chunk_dict['positions'] = positions
                        child_chunk_dict['has_coordinates'] = True
                else:
                    child_chunk_dict = {'id': f"child_{i}", 'content': str(child_chunk)}

                # 如果还没有坐标，尝试从coordinates数组添加
                if 'positions' not in child_chunk_dict:
                    if i < len(coordinates) and coordinates[i]:
                        child_chunk_dict['positions'] = coordinates[i]
                        child_chunk_dict['has_coordinates'] = True
                    else:
                        child_chunk_dict['has_coordinates'] = False

                child_chunks_with_coords.append(child_chunk_dict)
            
            final_result.update({
                'is_parent_child': True,
                'parent_chunks': chunks_result.get('parent_chunks', []),
                'child_chunks': child_chunks_with_coords,
                'relationships': chunks_result.get('relationships', []),
                'total_parents': chunks_result.get('total_parents', 0),
                'total_children': chunks_result.get('total_children', 0)
            })

            coords_count = sum(1 for c in child_chunks_with_coords if c.get('has_coordinates', False))
            logger.info(f"父子分块合并完成: {final_result['total_parents']}父块, "
                       f"{final_result['total_children']}子块, {coords_count}个有坐标")
        
        return final_result
