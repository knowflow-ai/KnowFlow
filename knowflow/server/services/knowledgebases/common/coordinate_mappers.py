#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
坐标映射器模块

提供统一的坐标映射接口，支持MinerU坐标系统：
- MinerU: 72 DPI PDF坐标，格式 [page_idx, x1, x2, y1, y2]

注意：DOTS已改用方案A（分块时直接附加坐标），不再需要事后映射。
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class CoordinateMapperInterface(ABC):
    """坐标映射器接口基类"""
    
    @abstractmethod
    def map_chunks_to_coordinates(self, chunks: List[str], elements_data: List[Dict], **kwargs) -> List[List]:
        """
        将文本分块映射到坐标信息
        
        Args:
            chunks: 文本分块列表
            elements_data: 元素数据列表
            
        Returns:
            坐标列表，每个分块对应一个坐标列表
        """
        pass
    
    @abstractmethod 
    def transform_coordinates(self, coordinates: List) -> List:
        """
        转换坐标格式
        
        Args:
            coordinates: 原始坐标
            
        Returns:
            转换后的坐标
        """
        pass


class MinerUCoordinateMapper(CoordinateMapperInterface):
    """MinerU 坐标映射器（保持原有逻辑）"""
    
    def map_chunks_to_coordinates(self, chunks: List[str], mineru_elements: List[Dict], **kwargs) -> List[List]:
        """映射MinerU坐标（复用现有逻辑）"""
        logger.info(f"开始MinerU坐标映射: {len(chunks)}个分块")
        
        try:
            # 直接复用现有的 get_bbox_for_chunk 逻辑
            from ..mineru_parse.utils import get_bbox_for_chunk
            
            coordinates = []
            for i, chunk in enumerate(chunks):
                try:
                    chunk_coords = get_bbox_for_chunk(chunk, mineru_elements)
                    coordinates.append(chunk_coords)
                    
                    if chunk_coords:
                        logger.debug(f"分块{i} 获取到 {len(chunk_coords)} 个MinerU坐标")
                    else:
                        logger.debug(f"分块{i} 未获取到MinerU坐标")
                        
                except Exception as e:
                    logger.warning(f"分块{i} MinerU坐标获取失败: {e}")
                    coordinates.append([])
            
            coords_count = sum(1 for c in coordinates if c)
            logger.info(f"MinerU坐标映射完成: {coords_count}/{len(chunks)} 个分块有坐标")
            
            return coordinates
            
        except ImportError as e:
            logger.warning(f"无法导入MinerU坐标函数: {e}")
            return [[] for _ in chunks]
        except Exception as e:
            logger.error(f"MinerU坐标映射异常: {e}")
            return [[] for _ in chunks]
    
    def transform_coordinates(self, coordinates: List) -> List:
        """MinerU坐标无需转换"""
        return coordinates

class CoordinateMapperFactory:
    """坐标映射器工厂类"""

    @staticmethod
    def create_mapper(coordinate_source: str) -> CoordinateMapperInterface:
        """创建对应的坐标映射器（仅支持MinerU）"""
        if coordinate_source.lower() == 'mineru':
            return MinerUCoordinateMapper()
        else:
            raise ValueError(f"不支持的坐标来源: {coordinate_source}，仅支持 'mineru'")

