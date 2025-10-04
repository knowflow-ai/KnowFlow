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
Parent-Child Chunking Method

基于父子分块的解析方法。

流程：
1. MinerU Parser 调用 KnowFlow Server 解析 PDF，返回 markdown + coordinate_map
2. 从 markdown 中提取纯文本和坐标映射
3. 调用 KnowFlow Server 的父子分块服务
4. 返回子块，父块和映射关系已存储到数据库

特点：
- 双层分块：父块提供上下文，子块用于向量检索
- 支持多种检索模式：parent（返回父块）、child（返回子块）、both（返回两者）
- 精确的行级别坐标映射
- 父块和子块的关系自动维护
"""

from rag.app.mineru_parser_base import MinerUParserBase


class ParentChildChunker(MinerUParserBase):
    """Parent-Child 父子分块解析器"""

    def __init__(self):
        super().__init__(strategy_name="Parent-Child")

    def get_default_config(self):
        """返回默认配置"""
        return {
            "chunk_token_num": 256,  # 子块 token 数
            "min_chunk_tokens": 10,
            "parent_config": {
                "parent_chunk_size": 1024,
                "parent_chunk_overlap": 100,
                "retrieval_mode": "parent",
                "parent_split_level": 2
            }
        }

    def build_chunking_config(self, parser_config):
        """构建分块配置"""
        parent_config = parser_config.get('parent_config', {})
        return {
            'strategy': 'parent_child',
            'chunk_token_num': int(parser_config.get('chunk_token_num', 256)),
            'min_chunk_tokens': int(parser_config.get('min_chunk_tokens', 10)),
            'parent_config': {
                'parent_chunk_size': int(parent_config.get('parent_chunk_size', 1024)),
                'parent_chunk_overlap': int(parent_config.get('parent_chunk_overlap', 100)),
                'retrieval_mode': parent_config.get('retrieval_mode', 'parent'),
                'parent_split_level': int(parent_config.get('parent_split_level', 2))
            }
        }

    def process_chunks_result(self, result):
        """
        处理父子分块的结果

        父子分块的 result 可能是字典（包含 chunks 字段）或直接是列表
        """
        return result if isinstance(result, list) else result.get('chunks', [])


# 创建全局实例
_chunker = ParentChildChunker()


def chunk(filename, binary=None, from_page=0, to_page=100000,
          lang="Chinese", callback=None, **kwargs):
    """
    Parent-Child Chunking - 父子分块方法

    流程：
    1. MinerU 解析 PDF → markdown + coordinate_map
    2. 提取纯文本和坐标映射
    3. 调用父子分块服务 → 带坐标的分块结果

    Args:
        filename: 文件路径或文件名
        binary: 二进制文件内容
        from_page: 起始页码
        to_page: 结束页码
        lang: 语言（Chinese/English）
        callback: 进度回调函数
        **kwargs: 额外参数，包括 parser_config 等

    Returns:
        List[dict]: 分块结果列表（子块）
    """
    return _chunker.chunk(filename, binary, from_page, to_page, lang, callback, **kwargs)


if __name__ == "__main__":
    import sys

    def dummy(prog=None, msg=""):
        print(f"[{prog*100:.1f}%] {msg}")

    if len(sys.argv) > 1:
        result = chunk(sys.argv[1], from_page=0, to_page=10, callback=dummy)
        print(f"\nGenerated {len(result)} child chunks")
