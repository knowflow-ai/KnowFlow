from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


class AppConfig(BaseModel):
    """应用主配置"""
    dev_mode: bool = Field(False, description="是否启用开发模式")
    chunk_method: str = Field("smart", description="全局分块方法")


class ExcelConfig(BaseModel):
    """Excel处理配置"""
    default_strategy: str = Field("auto", description="默认分块策略")
    html_chunk_rows: int = Field(12, description="HTML分块的默认行数")
    enable_smart_chunk_size: bool = Field(True, description="是否启用智能分块大小计算")
    merge_adjacent_rows: int = Field(1, description="合并的相邻行数")
    preprocess_merged_cells: bool = Field(True, description="是否预处理合并的单元格")
    number_formatting: bool = Field(True, description="是否格式化数字")
    min_chunk_size: int = Field(50, description="最小分块字符数")
    max_chunk_size: int = Field(8000, description="最大分块字符数")
    preserve_table_structure: bool = Field(True, description="是否保持表格结构")


class ChunkingConfig(BaseModel):
    """分块预分段配置"""
    regex_pattern: str = Field("", description="正则表达式分段模式")
    strict_regex_split: bool = Field(False, description="严格按正则表达式分块，忽略token限制")


# =======================================================
# DOTS OCR 配置模型类
# =======================================================

@dataclass
class DOTSVLLMConfig:
    """DOTS VLLM 服务配置"""
    url: str = "http://8.134.177.47:30001"
    model_name: str = "dotsocr-model"
    temperature: float = 0.1
    top_p: float = 1.0
    max_completion_tokens: int = 16384

@dataclass
class DOTSConfig:
    """DOTS OCR 客户端配置"""
    vllm: DOTSVLLMConfig = field(default_factory=DOTSVLLMConfig)

# =======================================================
# PaddleOCR 配置模型类
# =======================================================

@dataclass
class PaddleOCRConfig:
    """PaddleOCR 客户端配置"""
    url: str = "http://8.134.177.47:15003"
    timeout: int = 300
    max_file_size: int = 50

# =======================================================
# MinerU 配置模型类
# =======================================================

@dataclass
class MinerUFastAPIConfig:
    """MinerU FastAPI 客户端配置"""
    url: str = "http://localhost:8888"

@dataclass
class MinerUPipelineConfig:
    """MinerU Pipeline 后端配置"""
    parse_method: str = "auto"
    lang: str = "ch"
    formula_enable: bool = True
    table_enable: bool = True

@dataclass
class MinerUHTTPClientConfig:
    """MinerU HTTP Client 配置"""
    server_url: str = "http://localhost:30001"

@dataclass
class MinerUVLMConfig:
    """MinerU VLM 配置"""
    http_client: MinerUHTTPClientConfig = field(default_factory=MinerUHTTPClientConfig)

@dataclass
class MinerUModelConfig:
    """MinerU 模型配置"""
    source: str = "modelscope"
    device_mode: str = "auto"
    cache_dir: str = ""

@dataclass
class MinerUConfig:
    """MinerU 客户端配置"""
    fastapi: MinerUFastAPIConfig = field(default_factory=MinerUFastAPIConfig)
    default_backend: str = "pipeline"
    pipeline: MinerUPipelineConfig = field(default_factory=MinerUPipelineConfig)
    vlm: MinerUVLMConfig = field(default_factory=MinerUVLMConfig)
    model: MinerUModelConfig = field(default_factory=MinerUModelConfig)


class RootConfig(BaseModel):
    """根配置类"""
    app: AppConfig = Field(default_factory=AppConfig)
    excel: ExcelConfig = Field(default_factory=ExcelConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    mineru: MinerUConfig = Field(default_factory=MinerUConfig)
    dots: DOTSConfig = Field(default_factory=DOTSConfig)
    paddleocr: PaddleOCRConfig = Field(default_factory=PaddleOCRConfig)
    default_parser: str = Field("mineru", description="默认解析器: mineru, dots") 