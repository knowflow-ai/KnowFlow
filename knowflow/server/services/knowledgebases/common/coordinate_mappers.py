#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
坐标映射器模块

提供统一的坐标映射接口，支持DOTS和MinerU两种不同的坐标系统：
- DOTS: 200 DPI 图像坐标，格式 [x1, y1, x2, y2]
- MinerU: 72 DPI PDF坐标，格式 [page_idx, x1, x2, y1, y2]
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

class DOTSCoordinateMapper(CoordinateMapperInterface):
    """DOTS 坐标映射器"""
    
    def __init__(self):
        self.dpi_scale_factor = 72.0 / 200.0  # DOTS(200 DPI) -> PDF(72 DPI)
        from ..dots_parse.dots_json_converter import DotsJsonConverter
        self.converter = DotsJsonConverter()

    def map_chunks_to_coordinates(self, chunks: List[str], dots_elements: List[Dict], **kwargs) -> List[List]:
        """
        将 DOTS 元素映射到分块坐标
        
        关键差异处理：
        1. DOTS 使用 200 DPI 图像坐标 -> 转换为 72 DPI PDF坐标
        2. DOTS bbox格式: [x1, y1, x2, y2] -> MinerU格式: [page_idx, x1, x2, y1, y2]
        """
        logger.info(f"开始DOTS坐标映射: {len(chunks)}个分块, {len(dots_elements)}个元素")
        
        coordinates = []
        coordinate_map = kwargs.get('coordinate_map')
        markdown_lines = kwargs.get('markdown_lines')

        if not coordinate_map or not markdown_lines:
            logger.warning("缺少 coordinate_map 或 markdown_lines，无法为 DOTS 分块生成坐标")
            return [[] for _ in chunks]

        logger.info("使用行号坐标映射生成 DOTS 分块坐标")

        for chunk_content in chunks:
            coords = self.converter.map_chunk_to_coordinates(
                chunk_text=chunk_content,
                markdown_lines=markdown_lines,
                coordinate_map=coordinate_map
            )
            coordinates.append(coords)

        coords_count = sum(1 for c in coordinates if c)
        logger.info(f"DOTS坐标映射完成: {coords_count}/{len(chunks)} 个分块有坐标")

        return coordinates

    def _convert_dots_to_mineru_format(self, dots_coords: List[Dict]) -> List[List]:
        """转换DOTS坐标到MinerU格式"""
        mineru_positions = []
        
        for coord in dots_coords:
            bbox = coord.get('bbox')
            page_number = coord.get('page_number')
            
            if not bbox or not page_number or len(bbox) != 4:
                logger.warning(f"无效的DOTS坐标数据: bbox={bbox}, page_number={page_number}")
                continue
            
            try:
                # DPI缩放: DOTS坐标 * (72/200) = PDF坐标
                pdf_x1 = bbox[0] * self.dpi_scale_factor
                pdf_y1 = bbox[1] * self.dpi_scale_factor  
                pdf_x2 = bbox[2] * self.dpi_scale_factor
                pdf_y2 = bbox[3] * self.dpi_scale_factor
                
                # 按照 MinerU 格式: [page_number, bbox[0], bbox[2], bbox[1], bbox[3]]
                mineru_position = [
                    page_number - 1,  # 转换为0开始的页面索引
                    int(pdf_x1),     # x1 (左边界) - DPI缩放后
                    int(pdf_x2),     # x2 (右边界) - DPI缩放后
                    int(pdf_y1),     # y1 (上边界) - DPI缩放后  
                    int(pdf_y2)      # y2 (下边界) - DPI缩放后
                ]
                mineru_positions.append(mineru_position)
                
                logger.debug(f"DOTS坐标转换: 原始={bbox} -> DPI缩放({self.dpi_scale_factor:.3f}) -> MinerU={mineru_position}")
                
            except (ValueError, IndexError) as e:
                logger.warning(f"坐标转换失败: {e}, bbox={bbox}")
                continue
        
        return mineru_positions
    
    def transform_coordinates(self, coordinates: List) -> List:
        """转换DOTS坐标格式"""
        # 在 _convert_dots_to_mineru_format 中已经处理了转换
        return coordinates

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
        """创建对应的坐标映射器"""
        if coordinate_source.lower() == 'dots':
            return DOTSCoordinateMapper()
        elif coordinate_source.lower() == 'mineru':
            return MinerUCoordinateMapper()
        else:
            raise ValueError(f"不支持的坐标来源: {coordinate_source}")

def convert_dots_to_mineru_coordinates(dots_bbox: List, page_number: int) -> List:
    """DOTS坐标转MinerU格式的独立函数（向后兼容）"""
    try:
        mapper = DOTSCoordinateMapper()
        
        # 构造DOTS元素格式
        dots_element = {
            'bbox': dots_bbox,
            'page_number': page_number
        }
        
        # 转换
        result = mapper._convert_dots_to_mineru_format([dots_element])
        return result[0] if result else []
        
    except Exception as e:
        logger.error(f"坐标转换失败: {e}")
        return []
