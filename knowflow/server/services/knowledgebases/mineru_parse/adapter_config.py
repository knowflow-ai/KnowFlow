#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU FastAPI 适配器配置管理

提供统一的配置管理接口，支持环境变量、配置文件等多种配置来源。
现在支持从KnowFlow的统一配置系统加载配置。
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path

# 尝试导入KnowFlow的配置系统
# 尝试导入KnowFlow的配置系统
try:
    from ...config.config_loader import MINERU_CONFIG
    KNOWFLOW_CONFIG_AVAILABLE = True
except ImportError:
    try:
        # 备用导入路径
        from services.config.config_loader import MINERU_CONFIG
        KNOWFLOW_CONFIG_AVAILABLE = True
    except ImportError:
        KNOWFLOW_CONFIG_AVAILABLE = False


class AdapterConfig:
    """适配器配置管理类"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        'fastapi_url': 'http://localhost:8888',
        'backend': 'pipeline',
        'pipeline_config': {
            'parse_method': 'auto',
            'lang': 'ch',
            'formula_enable': True,
            'table_enable': True
        },
        'vlm_config': {
            'server_url': None
        }
    }
    
    def __init__(self, config_file: str = None):
        """
        初始化配置
        
        Args:
            config_file: 配置文件路径（可选）
        """
        # 1. 先从KnowFlow统一配置系统加载
        if KNOWFLOW_CONFIG_AVAILABLE:
            self._config = self._load_from_knowflow_config()
        else:
            self._config = self.DEFAULT_CONFIG.copy()
        
        # 2. 再从环境变量加载（优先级更高）
        self._load_from_env()
        
        # 3. 最后从指定的配置文件加载（优先级最高）
        if config_file and os.path.exists(config_file):
            self._load_from_file(config_file)
    
    def _load_from_knowflow_config(self) -> Dict[str, Any]:
        """从KnowFlow统一配置系统加载配置"""
        try:
            config = {
                'fastapi_url': MINERU_CONFIG.fastapi.url,
                'backend': MINERU_CONFIG.default_backend,
                'pipeline_config': {
                    'parse_method': MINERU_CONFIG.pipeline.parse_method,
                    'lang': MINERU_CONFIG.pipeline.lang,
                    'formula_enable': MINERU_CONFIG.pipeline.formula_enable,
                    'table_enable': MINERU_CONFIG.pipeline.table_enable
                },
                'vlm_config': {
                    'server_url': MINERU_CONFIG.vlm.sglang.server_url
                }
            }
            print("✅ 已从KnowFlow统一配置系统加载MinerU配置")
            return config
        except Exception as e:
            print(f"⚠️  从KnowFlow配置系统加载失败，使用默认配置: {e}")
            return self.DEFAULT_CONFIG.copy()
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        env_mappings = {
            'MINERU_FASTAPI_URL': 'fastapi_url',
            'MINERU_FASTAPI_BACKEND': 'backend',
            'MINERU_PARSE_METHOD': 'pipeline_config.parse_method',
            'MINERU_LANG': 'pipeline_config.lang',
            'MINERU_FORMULA_ENABLE': 'pipeline_config.formula_enable',
            'MINERU_TABLE_ENABLE': 'pipeline_config.table_enable',
            'MINERU_VLM_SERVER_URL': 'vlm_config.server_url',
            'SGLANG_SERVER_URL': 'vlm_config.server_url',  # 兼容旧环境变量
        }
        
        for env_key, config_key in env_mappings.items():
            env_value = os.environ.get(env_key)
            if env_value is not None:
                self._set_nested_value(config_key, self._convert_env_value(env_value))
    
    def _load_from_file(self, config_file: str):
        """从配置文件加载配置"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
            self._config.update(file_config)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
    
    def _convert_env_value(self, value: str):
        """转换环境变量值为合适的类型"""
        # 布尔值
        if value.lower() in ('true', '1', 'yes', 'on'):
            return True
        elif value.lower() in ('false', '0', 'no', 'off'):
            return False
        
        # 数字
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # 字符串
        return value
    
    def _set_nested_value(self, key_path: str, value):
        """设置嵌套配置值"""
        keys = key_path.split('.')
        config = self._config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def get(self, key: str, default=None):
        """获取配置值"""
        keys = key.split('.')
        config = self._config
        
        try:
            for key in keys:
                config = config[key]
            return config
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value):
        """设置配置值"""
        self._set_nested_value(key, value)
    
    def get_fastapi_config(self) -> Dict[str, Any]:
        """获取 FastAPI 相关配置"""
        return {
            'base_url': self.get('fastapi_url'),
            'backend': self.get('backend')
        }
    
    def get_backend_config(self, backend: str = None) -> Dict[str, Any]:
        """获取特定后端的配置"""
        backend = backend or self.get('backend')
        
        if backend == 'pipeline':
            return self.get('pipeline_config', {})
        elif backend in ['vlm-transformers', 'vlm-sglang-engine', 'vlm-sglang-client']:
            return self.get('vlm_config', {})
        else:
            return {}
    
    def save_to_file(self, config_file: str):
        """保存配置到文件"""
        try:
            config_dir = os.path.dirname(config_file)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)
                
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            print(f"配置已保存到: {config_file}")
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def update_env_variables(self):
        """更新环境变量以反映当前配置"""
        env_mappings = {
            'fastapi_url': 'MINERU_FASTAPI_URL',
            'backend': 'MINERU_FASTAPI_BACKEND',
            'pipeline_config.parse_method': 'MINERU_PARSE_METHOD',
            'pipeline_config.lang': 'MINERU_LANG',
            'pipeline_config.formula_enable': 'MINERU_FORMULA_ENABLE',
            'pipeline_config.table_enable': 'MINERU_TABLE_ENABLE',
            'vlm_config.server_url': 'MINERU_VLM_SERVER_URL',
        }
        
        for config_key, env_key in env_mappings.items():
            value = self.get(config_key)
            if value is not None:
                os.environ[env_key] = str(value)
    
    def print_config(self):
        """打印当前配置"""
        print("=== MinerU FastAPI 适配器配置 ===")
        print(f"配置来源: {'KnowFlow统一配置' if KNOWFLOW_CONFIG_AVAILABLE else '环境变量/默认值'}")
        print(f"FastAPI URL: {self.get('fastapi_url')}")
        print(f"默认后端: {self.get('backend')}")

        print("\nPipeline 配置:")
        pipeline_config = self.get('pipeline_config', {})
        for key, value in pipeline_config.items():
            print(f"  {key}: {value}")

        print("\nVLM 配置:")
        vlm_config = self.get('vlm_config', {})
        for key, value in vlm_config.items():
            print(f"  {key}: {value}")

        print("=" * 35)


# 全局配置实例
_global_config = None

def get_config() -> AdapterConfig:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        config_file = os.environ.get('MINERU_CONFIG_FILE')
        _global_config = AdapterConfig(config_file)
    return _global_config


# 便捷函数
def configure_fastapi(base_url: str = None, backend: str = None):
    """配置 FastAPI 设置"""
    config = get_config()
    
    if base_url:
        config.set('fastapi_url', base_url)
    if backend:
        config.set('backend', backend)
    
    config.update_env_variables()
    print(f"FastAPI 配置已更新: {base_url or config.get('fastapi_url')}, 后端: {backend or config.get('backend')}")

def set_backend(backend: str):
    """设置默认后端"""
    config = get_config()
    config.set('backend', backend)
    config.update_env_variables()
    print(f"默认后端已设置为: {backend}")

def get_current_config() -> Dict[str, Any]:
    """获取当前配置信息"""
    config = get_config()
    return {
        'mode': 'FastAPI',
        'url': config.get('fastapi_url'),
        'backend': config.get('backend'),
        'config_source': 'KnowFlow统一配置' if KNOWFLOW_CONFIG_AVAILABLE else '环境变量/默认值'
    } 