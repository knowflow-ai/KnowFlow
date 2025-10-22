#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""
Smart Chunking Method

基于 MinerU middle.json 的智能分块解析方法。

流程：
1. MinerU Parser 调用 KnowFlow Server 解析 PDF，返回 markdown + coordinate_map
2. 从 markdown 中提取纯文本和坐标映射
3. 调用 KnowFlow Server 的智能分块服务，根据 token 限制进行分块
4. 返回带坐标的分块结果

特点：
- 保留完整的文档格式（标题、列表、表格、图片）
- 精确的行级别坐标映射，支持文档定位
- 智能分块，支持多种分块策略（smart/advanced/parent_child）
"""

from rag.app.modern_parser_base import ModernParserBase


class SmartChunker(ModernParserBase):
    """Smart 智能分块解析器"""

    def __init__(self):
        super().__init__(strategy_name="Smart")

    def get_default_config(self):
        """返回默认配置"""
        return {
            "chunk_token_num": 256,
            "min_chunk_tokens": 10,
            "enable_vision_enhancement": False,
            "vision_description_format": "[图片描述]: {desc}",
            "vision_batch_size": 3,
        }

    def build_chunking_config(self, parser_config):
        """构建分块配置"""
        config = {
            'strategy': 'smart',
            'chunk_token_num': int(parser_config.get('chunk_token_num', 256)),
            'min_chunk_tokens': int(parser_config.get('min_chunk_tokens', 10)),
            'enable_heading_in_content': parser_config.get('enable_heading_in_content', False)
        }
        # 添加图片理解配置
        config.update(self._extract_vision_config(parser_config))
        return config


# 创建全局实例
_chunker = SmartChunker()


def chunk(filename, binary=None, from_page=0, to_page=100000,
          lang="Chinese", callback=None, **kwargs):
    """
    Smart Chunking - 智能分块方法

    流程：
    1. MinerU 解析 PDF → markdown + coordinate_map
    2. 提取纯文本和坐标映射
    3. 调用智能分块服务 → 带坐标的分块结果

    Args:
        filename: 文件路径或文件名
        binary: 二进制文件内容
        from_page: 起始页码
        to_page: 结束页码
        lang: 语言（Chinese/English）
        callback: 进度回调函数
        **kwargs: 额外参数，包括 parser_config 等

    Returns:
        List[dict]: 分块结果列表
    """
    return _chunker.chunk(filename, binary, from_page, to_page, lang, callback, **kwargs)


if __name__ == "__main__":
    import sys

    def dummy(prog=None, msg=""):
        print(f"[{prog*100:.1f}%] {msg}")

    if len(sys.argv) > 1:
        result = chunk(sys.argv[1], from_page=0, to_page=10, callback=dummy)
        print(f"\nGenerated {len(result)} chunks")
