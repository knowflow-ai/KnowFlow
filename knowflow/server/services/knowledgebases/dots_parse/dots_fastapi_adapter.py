#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOTS OCR FastAPI 适配器

提供与远程DOTS OCR服务的通信功能，支持:
- 基于VLLM API的OCR解析
- 多种图像格式支持
- 结构化JSON输出处理
- 连接状态检测
"""

import requests
import json
import base64
import logging
from typing import Dict, List, Any, Optional, Union
from io import BytesIO
from PIL import Image

# 从配置系统导入DOTS配置
from ...config.config_loader import DOTS_CONFIG

logger = logging.getLogger(__name__)

class DOTSFastAPIAdapter:
    """DOTS OCR FastAPI 客户端适配器"""
    
    def __init__(self, base_url: str = None, model_name: str = None):
        """初始化DOTS客户端适配器

        Args:
            base_url: DOTS服务基础URL，默认从配置读取
            model_name: 模型名称，默认从配置读取
        """
        self.base_url = base_url or DOTS_CONFIG.vllm.url
        self.model_name = model_name or DOTS_CONFIG.vllm.model_name
        
        # VLLM生成参数
        self.temperature = DOTS_CONFIG.vllm.temperature
        self.top_p = DOTS_CONFIG.vllm.top_p
        self.max_completion_tokens = DOTS_CONFIG.vllm.max_completion_tokens
        
        # 确保base_url格式正确
        self.base_url = self.base_url.rstrip('/')
        self.chat_url = f"{self.base_url}/v1/chat/completions"
        self.models_url = f"{self.base_url}/v1/models"
        
        logger.info(f"初始化 DOTS 适配器: {self.base_url}, 模型: {self.model_name}")
    
    def test_connection(self) -> Dict[str, Any]:
        """测试与DOTS服务的连接
        
        Returns:
            dict: 包含连接状态和信息的字典
        """
        # 优先测试chat completions端点，因为models端点可能不可用
        logger.info(f"测试DOTS服务连接: {self.chat_url}")
        
        try:
            # 发送一个简单的测试请求到chat completions端点
            test_payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "<|img|><|imgpad|><|endofimg|>connection test"
                            }
                        ]
                    }
                ],
                "max_tokens": 1,
                "temperature": 0.1
            }
            
            response = requests.post(
                self.chat_url,
                json=test_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            logger.info(f"DOTS chat API 响应状态: {response.status_code}")
            
            if response.status_code == 200:
                logger.info("DOTS服务连接成功 - chat API 正常工作")
                return {
                    'status': 'success',
                    'message': 'DOTS服务连接正常',
                    'method': 'chat_completions_test'
                }
            else:
                logger.error(f"DOTS chat API 响应异常: {response.status_code}, 内容: {response.text[:300]}")
                
                # 如果chat API失败，尝试models端点作为备用
                try:
                    models_response = requests.get(self.models_url, timeout=10)
                    if models_response.status_code == 200:
                        models_data = models_response.json()
                        available_models = []
                        if 'data' in models_data:
                            available_models = [m.get('id', '') for m in models_data['data']]
                        
                        return {
                            'status': 'success',
                            'message': 'DOTS服务连接正常(通过models端点)',
                            'available_models': available_models,
                            'method': 'models_endpoint'
                        }
                except:
                    pass
                
                return {
                    'status': 'error',
                    'message': f'DOTS服务响应异常: {response.status_code}',
                    'response': response.text[:200]
                }
                
        except requests.exceptions.ConnectTimeout:
            logger.error("DOTS服务连接超时")
            return {
                'status': 'error',
                'message': 'DOTS服务连接超时'
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"DOTS服务连接失败: {e}")
            return {
                'status': 'error',
                'message': 'DOTS服务连接失败，请检查服务地址和网络'
            }
        except Exception as e:
            logger.error(f"连接测试异常: {e}")
            return {
                'status': 'error',
                'message': f'连接测试异常: {str(e)}'
            }
    
    def _image_to_base64(self, image: Union[Image.Image, bytes], format: str = 'PNG') -> str:
        """将图像转换为base64格式
        
        Args:
            image: PIL图像对象或字节数据
            format: 图像格式，默认PNG
            
        Returns:
            str: base64编码的图像URL
        """
        if isinstance(image, bytes):
            # 如果已经是字节数据，直接编码为图像格式
            img_base64 = base64.b64encode(image).decode('utf-8')
            return f"data:image/{format.lower()};base64,{img_base64}"
        else:
            # PIL图像对象转换
            buffer = BytesIO()
            image.save(buffer, format=format)
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/{format.lower()};base64,{img_base64}"
    
    def _create_ocr_prompt(self) -> str:
        """创建OCR解析的标准提示词
        
        Returns:
            str: 标准化的OCR提示词
        """
        return """Please output the layout information from the image, including each layout element's bbox, its category, and the corresponding text content within the bbox.

1. Bbox format: [x1, y1, x2, y2]

2. Layout Categories: The possible categories are ['Caption', 'Footnote', 'Formula', 'List-item', 'Page-footer', 'Page-header', 'Picture', 'Section-header', 'Table', 'Text', 'Title'].

3. Text Extraction & Formatting Rules:
    - Picture: For the 'Picture' category, the text field should be omitted.
    - Formula: Format its text as LaTeX.
    - Table: Format its text as HTML.
    - All Others (Text, Title, etc.): Format their text as Markdown.

4. Constraints:
    - The output text must be the original text from the image, with no translation.
    - All layout elements must be sorted according to human reading order.

5. Final Output: The entire output must be a single JSON object."""
    
    def parse_image(self, image: Union[Image.Image, bytes], custom_prompt: str = None) -> Dict[str, Any]:
        """解析单个图像
        
        Args:
            image: 图像对象或字节数据
            custom_prompt: 自定义提示词，默认使用标准OCR提示词
            
        Returns:
            dict: 解析结果，包含layout_elements等信息
        """
        try:
            # 转换图像为base64
            image_url = self._image_to_base64(image)
            
            # 构建请求消息
            prompt = custom_prompt or self._create_ocr_prompt()
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        },
                        {
                            "type": "text", 
                            "text": f"<|img|><|imgpad|><|endofimg|>{prompt}"
                        }
                    ]
                }
            ]
            
            # 构建请求负载
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": self.max_completion_tokens,
                "stream": False
            }
            
            # 发送请求
            headers = {"Content-Type": "application/json"}
            response = requests.post(
                self.chat_url,
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'choices' in result and result['choices']:
                    content = result['choices'][0]['message']['content']
                    
                    # 尝试解析JSON内容
                    try:
                        content_stripped = content.strip()
                        if content_stripped.startswith('{') or content_stripped.startswith('['):
                            parsed_json = json.loads(content_stripped)
                            
                            # 如果返回的是数组（layout_elements的直接数组）
                            if isinstance(parsed_json, list):
                                return {
                                    'success': True,
                                    'raw_response': content,
                                    'layout_data': {'layout_elements': parsed_json},
                                    'layout_elements': parsed_json
                                }
                            # 如果返回的是对象
                            else:
                                return {
                                    'success': True,
                                    'raw_response': content,
                                    'layout_data': parsed_json,
                                    'layout_elements': parsed_json.get('layout_elements', [])
                                }
                        else:
                            # 非JSON格式，返回原始文本
                            return {
                                'success': True,
                                'raw_response': content,
                                'layout_data': None,
                                'layout_elements': [],
                                'note': '返回内容不是JSON格式'
                            }
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON解析失败: {e}")
                        return {
                            'success': True,
                            'raw_response': content,
                            'layout_data': None,
                            'layout_elements': [],
                            'error': f'JSON解析失败: {str(e)}'
                        }
                else:
                    return {
                        'success': False,
                        'error': '响应格式异常，缺少choices字段',
                        'raw_response': result
                    }
            else:
                return {
                    'success': False,
                    'error': f'请求失败: {response.status_code}',
                    'response_text': response.text
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'OCR请求超时'
            }
        except Exception as e:
            logger.error(f"图像解析异常: {e}")
            return {
                'success': False,
                'error': f'图像解析异常: {str(e)}'
            }
    
    def parse_pdf_pages(self, pdf_path: str, page_range: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """解析PDF文档的指定页面
        
        注意：此方法需要外部PDF转图像的支持。
        对于KnowFlow集成，建议使用上层的PDF处理逻辑将PDF转换为图像后调用parse_image方法。
        
        Args:
            pdf_path: PDF文件路径
            page_range: 页面范围元组(start, end)，默认解析所有页面
            
        Returns:
            list: 每页的解析结果列表
        """
        logger.error("parse_pdf_pages方法需要PyMuPDF支持，请使用上层PDF处理逻辑")
        return [{
            'success': False,
            'error': '此方法需要额外的PDF处理库支持，请使用上层PDF转图像逻辑后调用parse_image方法'
        }]

# 全局适配器实例
_global_adapter: Optional[DOTSFastAPIAdapter] = None

def get_global_adapter() -> DOTSFastAPIAdapter:
    """获取全局DOTS适配器实例
    
    Returns:
        DOTSFastAPIAdapter: 全局适配器实例
    """
    global _global_adapter
    if _global_adapter is None:
        _global_adapter = DOTSFastAPIAdapter()
    return _global_adapter

def test_adapter_connection() -> Dict[str, Any]:
    """测试全局适配器的连接状态
    
    Returns:
        dict: 连接测试结果
    """
    adapter = get_global_adapter()
    return adapter.test_connection()

def reset_global_adapter():
    """重置全局适配器（主要用于测试）"""
    global _global_adapter
    _global_adapter = None