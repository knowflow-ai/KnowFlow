#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU FastAPI 适配器

直接通过 FastAPI 接口处理文档，提供高性能的文档解析服务。
"""

import os
import tempfile
import requests
import json
from typing import Optional, Callable, Dict, Any
from loguru import logger

# 导入文档转换功能
from .file_converter import ensure_pdf

# 导入统一配置系统
try:
    from ...config.config_loader import MINERU_CONFIG
    CONFIG_AVAILABLE = True
except ImportError:
    try:
        from services.config.config_loader import MINERU_CONFIG
        CONFIG_AVAILABLE = True
    except ImportError:
        CONFIG_AVAILABLE = False
        logger.warning("无法导入统一配置系统，将使用环境变量作为备用")


class MinerUFastAPIAdapter:
    """MinerU FastAPI 适配器 - 统一配置管理版本"""
    
    def __init__(self, 
                 base_url: str = "http://localhost:8888",
                 backend: str = "pipeline",
                 timeout: int = 30000,
                 # VLM 配置参数
                 server_url: Optional[str] = None,
                 # Pipeline 配置参数
                 parse_method: str = "auto",
                 lang: str = "ch",
                 formula_enable: bool = True,
                 table_enable: bool = True):
        """
        初始化适配器 - 统一配置管理
        
        Args:
            base_url: FastAPI 服务地址
            backend: 默认后端类型
            timeout: 请求超时时间（秒）
            server_url: SGLang 服务器地址（vlm-sglang-client 后端）
            parse_method: 解析方法（pipeline 后端）
            lang: 语言设置（pipeline 后端）
            formula_enable: 公式解析开关（pipeline 后端）
            table_enable: 表格解析开关（pipeline 后端）
        """
        self.base_url = base_url.rstrip('/')
        self.backend = backend
        self.timeout = timeout
        
        # VLM 配置
        self.server_url = server_url
        
        # Pipeline 配置
        self.parse_method = parse_method
        self.lang = lang
        self.formula_enable = formula_enable
        self.table_enable = table_enable
        
        self.session = requests.Session()
        
        logger.info(f"MinerU FastAPI适配器已初始化: URL={self.base_url}, Backend={self.backend}")
        logger.info(f"VLM配置: server_url={self.server_url}")
        logger.info(f"Pipeline配置: parse_method={self.parse_method}, lang={self.lang}, formula_enable={self.formula_enable}, table_enable={self.table_enable}")
        
    def _check_server_health(self) -> bool:
        """检查 FastAPI 服务器是否可访问"""
        try:
            response = self.session.get(f"{self.base_url}/docs", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"FastAPI 服务器不可访问: {e}")
            return False
    
    def _prepare_request_data(self, 
                             backend: str = None,
                             parse_method: str = None,
                             lang: str = None, 
                             formula_enable: bool = None,
                             table_enable: bool = None,
                             server_url: Optional[str] = None,
                             **kwargs) -> Dict[str, Any]:
        """准备请求数据 - 使用适配器配置作为默认值"""
        backend = backend or self.backend
        
        data = {
            'backend': backend,
            'return_md': True,           # 返回 Markdown 内容
            'return_content_list': True,  # 总是返回内容列表
            'return_info': True,         # 默认返回解析信息（用于位置信息）
            'return_layout': False,      # 默认不返回布局
            'return_images': True,       # 获取原始图片数据
            'is_json_md_dump': False,    # 默认不保存文件到服务器
            'output_dir': 'output'  # 临时输出目录
        }
        
        # 添加特定后端参数，优先使用传入参数，否则使用适配器配置
        if backend == 'vlm-sglang-client':
            final_server_url = server_url or self.server_url
            if final_server_url:
                data['server_url'] = final_server_url
                logger.info(f"使用 server_url: {final_server_url}")
            else:
                logger.warning("vlm-sglang-client 后端需要 server_url 参数，但未配置")
                
        elif backend == 'pipeline':
            data.update({
                'parse_method': parse_method or self.parse_method,
                'lang': lang or self.lang,
                'formula_enable': formula_enable if formula_enable is not None else self.formula_enable,
                'table_enable': table_enable if table_enable is not None else self.table_enable
            })
            logger.info(f"使用 Pipeline 配置: parse_method={data['parse_method']}, lang={data['lang']}, formula_enable={data['formula_enable']}, table_enable={data['table_enable']}")
        
        # 合并额外参数，允许用户覆盖默认设置
        data.update(kwargs)
        return data
    
    def process_file(self,
                    file_path: str,
                    update_progress: Optional[Callable] = None,
                    backend: str = None,
                    **kwargs) -> Dict[str, Any]:
        """
        处理文件的主要接口 - 简化版本，自动使用适配器配置
        
        Args:
            file_path: 文件路径（支持PDF、Office文档、URL等）
            update_progress: 进度回调函数
            backend: 指定后端类型（可选，覆盖适配器默认值）
            **kwargs: 其他参数（可选，覆盖适配器配置）
            
        Returns:
            Dict: 处理结果
        """
        if update_progress:
            update_progress(0.1, "开始连接 FastAPI 服务")
            
        # 检查服务器健康状态
        if not self._check_server_health():
            raise Exception(f"FastAPI 服务器不可访问: {self.base_url}")
            
        if update_progress:
            update_progress(0.15, "检查文件格式")
            
        # 检查文件是否存在（对于本地文件）
        if not file_path.startswith(("http://", "https://")) and not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 创建临时目录用于文档转换
        temp_dir = tempfile.mkdtemp(prefix="fastapi_adapter_")
        pdf_to_process = None
        temp_pdf_to_delete = None
        
        try:
            if update_progress:
                update_progress(0.2, "准备文档转换")
            
            # 调用 ensure_pdf 进行文档转换（如果需要）
            logger.info(f"检查文档格式并转换: {file_path}")
            pdf_to_process, temp_pdf_to_delete = ensure_pdf(file_path, temp_dir)
            
            if not pdf_to_process:
                raise Exception(f"无法处理文件: {file_path}，转换为PDF失败")
            
            if temp_pdf_to_delete:
                logger.info(f"文档已转换为PDF: {pdf_to_process}")
                if update_progress:
                    update_progress(0.25, "文档转换完成")
            else:
                logger.info(f"文档已是PDF格式: {pdf_to_process}")
                if update_progress:
                    update_progress(0.25, "PDF文件检查完成")
            
            # 准备请求数据（自动使用适配器配置）
            data = self._prepare_request_data(backend=backend, **kwargs)
            
            if update_progress:
                update_progress(0.3, f"开始 {data['backend']} 后端处理")
                
            # 发送请求
            with open(pdf_to_process, 'rb') as f:
                # MinerU 期望 files 参数，并且是 List[UploadFile] 类型
                # 在 multipart/form-data 中，需要发送多个同名的文件字段
                files = [('files', f)]
                response = self.session.post(
                    f"{self.base_url}/file_parse",
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
                
            if response.status_code == 200:
                mineru_result = response.json()
                
                if update_progress:
                    update_progress(0.8, "FastAPI 处理完成")
                
                # 处理 MinerU 的响应数据结构
                # MinerU 返回: {"results": {"filename": {"md_content": "...", "middle_json": "..."}}}
                # 我们需要提取第一个文件的结果
                if 'results' in mineru_result and mineru_result['results']:
                    # 获取第一个文件的结果
                    first_file_key = list(mineru_result['results'].keys())[0]
                    result = mineru_result['results'][first_file_key]
                    
                    # 添加处理信息
                    result['_adapter_info'] = {
                        'backend_used': mineru_result.get('backend', data['backend']),
                        'file_processed': os.path.basename(file_path),
                        'converted_from': os.path.basename(file_path) if temp_pdf_to_delete else None,
                        'adapter_version': '2.2.0',  # 更新版本号
                        'processing_mode': 'fastapi_with_document_conversion'
                    }
                    
                    if update_progress:
                        update_progress(1.0, "处理完成")
                    
                    return result
                else:
                    raise Exception("MinerU 返回的结果为空")
            else:
                error_msg = f"FastAPI 请求失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except requests.exceptions.Timeout:
            error_msg = f"FastAPI 请求超时 ({self.timeout}秒)"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"FastAPI 请求失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
        finally:
            # 清理临时文件
            if temp_pdf_to_delete and os.path.exists(temp_pdf_to_delete):
                try:
                    os.remove(temp_pdf_to_delete)
                    logger.info(f"已清理临时PDF文件: {temp_pdf_to_delete}")
                except OSError as e:
                    logger.warning(f"清理临时PDF文件失败: {temp_pdf_to_delete}, 错误: {e}")
            
            # 清理临时目录
            try:
                import shutil
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    logger.debug(f"已清理临时目录: {temp_dir}")
            except OSError as e:
                logger.warning(f"清理临时目录失败: {temp_dir}, 错误: {e}")


# 全局适配器实例
_global_adapter = None

def get_global_adapter() -> MinerUFastAPIAdapter:
    """获取全局适配器实例 - 统一配置管理版本"""
    global _global_adapter
    if _global_adapter is None:
        # 统一配置获取逻辑
        if CONFIG_AVAILABLE:
            # 从统一配置系统读取
            fastapi_url = MINERU_CONFIG.fastapi.url
            backend = MINERU_CONFIG.default_backend
            timeout = MINERU_CONFIG.fastapi.timeout
            
            # VLM 配置
            server_url = MINERU_CONFIG.vlm.sglang.server_url
            
            # Pipeline 配置
            parse_method = MINERU_CONFIG.pipeline.parse_method
            lang = MINERU_CONFIG.pipeline.lang
            formula_enable = MINERU_CONFIG.pipeline.formula_enable
            table_enable = MINERU_CONFIG.pipeline.table_enable
            
            logger.info("从统一配置系统加载MinerU完整配置")
        else:
            # 环境变量备用方案
            fastapi_url = os.environ.get('MINERU_FASTAPI_URL', 'http://localhost:8888')
            backend = os.environ.get('MINERU_FASTAPI_BACKEND', 'pipeline')
            timeout = int(os.environ.get('MINERU_FASTAPI_TIMEOUT', '30'))
            
            # VLM 配置环境变量
            server_url = os.environ.get('MINERU_VLM_SERVER_URL', 
                                       os.environ.get('SGLANG_SERVER_URL'))
            
            # Pipeline 配置环境变量
            parse_method = os.environ.get('MINERU_PARSE_METHOD', 'auto')
            lang = os.environ.get('MINERU_LANG', 'ch')
            formula_enable = os.environ.get('MINERU_FORMULA_ENABLE', 'true').lower() == 'true'
            table_enable = os.environ.get('MINERU_TABLE_ENABLE', 'true').lower() == 'true'
            
            logger.warning("统一配置系统不可用，从环境变量加载MinerU配置")
        
        _global_adapter = MinerUFastAPIAdapter(
            base_url=fastapi_url,
            backend=backend,
            timeout=timeout,
            server_url=server_url,
            parse_method=parse_method,
            lang=lang,
            formula_enable=formula_enable,
            table_enable=table_enable
        )
        
        logger.info("MinerU FastAPI适配器统一配置加载完成")
    return _global_adapter


def configure_adapter(base_url: str = None, 
                     backend: str = None, 
                     timeout: int = None,
                     server_url: str = None,
                     parse_method: str = None,
                     lang: str = None,
                     formula_enable: bool = None,
                     table_enable: bool = None):
    """配置全局适配器 - 扩展版本，支持所有配置项"""
    global _global_adapter
    
    # 获取当前配置作为默认值
    if CONFIG_AVAILABLE:
        current_url = MINERU_CONFIG.fastapi.url
        current_backend = MINERU_CONFIG.default_backend
        current_timeout = MINERU_CONFIG.fastapi.timeout
        current_server_url = MINERU_CONFIG.vlm.sglang.server_url
        current_parse_method = MINERU_CONFIG.pipeline.parse_method
        current_lang = MINERU_CONFIG.pipeline.lang
        current_formula_enable = MINERU_CONFIG.pipeline.formula_enable
        current_table_enable = MINERU_CONFIG.pipeline.table_enable
    else:
        # 环境变量备用
        current_url = os.environ.get('MINERU_FASTAPI_URL', 'http://localhost:8888')
        current_backend = os.environ.get('MINERU_FASTAPI_BACKEND', 'pipeline')
        current_timeout = int(os.environ.get('MINERU_FASTAPI_TIMEOUT', '30'))
        current_server_url = os.environ.get('MINERU_VLM_SERVER_URL', 
                                           os.environ.get('SGLANG_SERVER_URL'))
        current_parse_method = os.environ.get('MINERU_PARSE_METHOD', 'auto')
        current_lang = os.environ.get('MINERU_LANG', 'ch')
        current_formula_enable = os.environ.get('MINERU_FORMULA_ENABLE', 'true').lower() == 'true'
        current_table_enable = os.environ.get('MINERU_TABLE_ENABLE', 'true').lower() == 'true'
    
    _global_adapter = MinerUFastAPIAdapter(
        base_url=base_url or current_url,
        backend=backend or current_backend,
        timeout=timeout or current_timeout,
        server_url=server_url or current_server_url,
        parse_method=parse_method or current_parse_method,
        lang=lang or current_lang,
        formula_enable=formula_enable if formula_enable is not None else current_formula_enable,
        table_enable=table_enable if table_enable is not None else current_table_enable
    )
    
    logger.info(f"FastAPI 适配器配置已更新 - 统一配置管理")


def test_adapter_connection(base_url: str = None) -> Dict[str, Any]:
    """测试适配器连接"""
    test_url = base_url or os.environ.get('MINERU_FASTAPI_URL', 'http://localhost:8888')
    
    try:
        response = requests.get(f"{test_url.rstrip('/')}/docs", timeout=10)
        if response.status_code == 200:
            return {
                'status': 'success',
                'url': test_url,
                'message': 'FastAPI 服务可访问'
            }
        else:
            return {
                'status': 'error',
                'url': test_url,
                'message': f'服务响应异常: {response.status_code}'
            }
    except Exception as e:
        return {
            'status': 'error',
            'url': test_url,
            'message': f'连接失败: {str(e)}'
        }


def get_adapter_config_info() -> Dict[str, Any]:
    """获取当前适配器配置信息 - 新增调试函数"""
    adapter = get_global_adapter()
    return {
        'fastapi_config': {
            'base_url': adapter.base_url,
            'backend': adapter.backend,
            'timeout': adapter.timeout
        },
        'vlm_config': {
            'server_url': adapter.server_url
        },
        'pipeline_config': {
            'parse_method': adapter.parse_method,
            'lang': adapter.lang,
            'formula_enable': adapter.formula_enable,
            'table_enable': adapter.table_enable
        },
        'config_source': 'unified_config_system' if CONFIG_AVAILABLE else 'environment_variables'
    } 