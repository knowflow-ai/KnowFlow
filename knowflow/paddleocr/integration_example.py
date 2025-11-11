"""
PaddleOCR API 集成示例

展示如何在实际项目中集成 PaddleOCR API
"""

import requests
import base64
import logging
from typing import Optional


class PaddleOCRClient:
    """PaddleOCR API 客户端"""
    
    def __init__(self, api_url: str = "http://8.134.177.47:15003"):
        self.api_url = api_url
        self.endpoint = f"{api_url}/layout-parsing"
    
    def recognize_image(self, image_path: str, timeout: int = 120) -> Optional[str]:
        """
        识别图片内容，返回 Markdown 文本
        
        Args:
            image_path: 图片文件路径
            timeout: 请求超时时间（秒）
            
        Returns:
            识别的 Markdown 文本，失败返回 None
        """
        try:
            # 读取图片
            with open(image_path, 'rb') as f:
                image_binary = f.read()
            
            # 转换为 base64
            base64_data = base64.b64encode(image_binary).decode('utf-8')
            
            # 调用 API
            response = requests.post(
                self.endpoint,
                json={
                    'file': base64_data,
                    'fileType': 1  # 1 = 图像
                },
                timeout=timeout
            )
            
            if response.status_code != 200:
                logging.error(f"PaddleOCR API returned status {response.status_code}")
                return None
            
            result = response.json()
            
            # 检查错误码
            if result.get('errorCode') != 0:
                logging.error(f"PaddleOCR API error: {result.get('errorMsg')}")
                return None
            
            # 提取 Markdown 文本
            layout_results = result.get('result', {}).get('layoutParsingResults', [])
            if layout_results:
                markdown_text = layout_results[0].get('markdown', {}).get('text', '')
                return markdown_text.strip() if markdown_text else None
            
            return None
            
        except requests.exceptions.Timeout:
            logging.error(f"PaddleOCR API timeout for {image_path}")
            return None
        except Exception as e:
            logging.error(f"PaddleOCR API error: {e}")
            return None
    
    def recognize_image_binary(self, image_binary: bytes, timeout: int = 120) -> Optional[str]:
        """
        识别图片二进制内容
        
        Args:
            image_binary: 图片二进制数据
            timeout: 请求超时时间（秒）
            
        Returns:
            识别的 Markdown 文本，失败返回 None
        """
        try:
            base64_data = base64.b64encode(image_binary).decode('utf-8')
            
            response = requests.post(
                self.endpoint,
                json={
                    'file': base64_data,
                    'fileType': 1
                },
                timeout=timeout
            )
            
            if response.status_code != 200:
                return None
            
            result = response.json()
            if result.get('errorCode') != 0:
                return None
            
            layout_results = result.get('result', {}).get('layoutParsingResults', [])
            if layout_results:
                markdown_text = layout_results[0].get('markdown', {}).get('text', '')
                return markdown_text.strip() if markdown_text else None
            
            return None
            
        except Exception as e:
            logging.error(f"PaddleOCR API error: {e}")
            return None


# 使用示例
if __name__ == "__main__":
    # 创建客户端
    client = PaddleOCRClient()
    
    # 识别图片
    result = client.recognize_image("dashboard.png")
    
    if result:
        print("识别成功!")
        print(f"文本长度: {len(result)} 字符")
        print(f"\n前 500 字符:\n{result[:500]}")
    else:
        print("识别失败")
