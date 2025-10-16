import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any

from .business_config import RootConfig

logger = logging.getLogger(__name__)

ENV_PREFIX = "KNOWFLOW_"

# 配置文件路径优先级：
# 1. 环境变量 KNOWFLOW_SETTINGS_PATH（最高优先级）
# 2. docker/knowflow-server/settings.yaml（本地开发和Docker部署统一使用）
# 3. 当前目录下的 settings.yaml（向后兼容）
def _get_config_path() -> Path:
    """获取配置文件路径"""
    # 优先使用环境变量指定的路径
    env_path = os.environ.get('KNOWFLOW_SETTINGS_PATH')
    if env_path:
        return Path(env_path)

    # 尝试使用项目根目录下的 docker/knowflow-server/settings.yaml
    current_dir = Path(__file__).parent
    # 从 knowflow/server/services/config 向上 4 层到项目根目录
    project_root = current_dir.parent.parent.parent.parent
    docker_config_path = project_root / "docker" / "knowflow-server" / "settings.yaml"

    if docker_config_path.exists():
        return docker_config_path

    # 向后兼容：使用当前目录下的 settings.yaml
    fallback_path = current_dir / "settings.yaml"
    return fallback_path

DEFAULT_CONFIG_PATH = _get_config_path()

def _load_config_from_yaml(path: Path) -> Dict[str, Any]:
    """从YAML文件加载配置"""
    if not path.exists():
        logger.warning(f"配置文件不存在: {path}")
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"加载或解析YAML配置失败: {path}, 错误: {e}")
        raise

def _recursive_update(d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
    """递归更新字典"""
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = _recursive_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def _load_env_vars() -> Dict[str, Any]:
    """从环境变量加载配置"""
    env_config = {}
    for key, value in os.environ.items():
        if key.startswith(ENV_PREFIX):
            parts = key.replace(ENV_PREFIX, "").lower().split('__')
            
            # 类型转换
            if value.lower() in ["true", "false"]:
                processed_value = value.lower() == "true"
            elif value.isdigit():
                processed_value = int(value)
            else:
                try:
                    processed_value = float(value)
                except (ValueError, TypeError):
                    processed_value = value
            
            d = env_config
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = processed_value
            
    return env_config

def _load_mineru_env_vars() -> Dict[str, Any]:
    """从环境变量加载MinerU相关配置"""
    mineru_env_config = {}
    
    # MinerU环境变量映射（仅客户端相关）
    env_mappings = {
        # FastAPI客户端配置
        'MINERU_FASTAPI_URL': 'fastapi.url',
        'MINERU_FASTAPI_BACKEND': 'default_backend',
        
        # Pipeline后端配置
        'MINERU_PARSE_METHOD': 'pipeline.parse_method',
        'MINERU_LANG': 'pipeline.lang',
        'MINERU_FORMULA_ENABLE': 'pipeline.formula_enable',
        'MINERU_TABLE_ENABLE': 'pipeline.table_enable',
        
        # VLM后端配置
        'MINERU_VLM_HTTP_SERVER_URL': 'vlm.http_client.server_url',
        
        # 额外的MinerU服务端配置（用于web_api目录）
        'MINERU_MODEL_SOURCE': 'model.source',
        'MINERU_DEVICE_MODE': 'model.device_mode',
        'MINERU_MODEL_CACHE_DIR': 'model.cache_dir',
    }
    
    for env_key, config_path in env_mappings.items():
        env_value = os.environ.get(env_key)
        if env_value is not None:
            # 类型转换
            if env_value.lower() in ["true", "false"]:
                processed_value = env_value.lower() == "true"
            elif env_value.isdigit():
                processed_value = int(env_value)
            else:
                try:
                    processed_value = float(env_value)
                except (ValueError, TypeError):
                    processed_value = env_value
            
            # 设置嵌套配置
            parts = config_path.split('.')
            d = mineru_env_config
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = processed_value
    
    if mineru_env_config:
        return {'mineru': mineru_env_config}
    return {}

def _load_dots_env_vars() -> Dict[str, Any]:
    """从环境变量加载DOTS相关配置"""
    dots_env_config = {}
    
    # DOTS环境变量映射
    env_mappings = {
        # VLLM服务配置
        'DOTS_VLLM_URL': 'vllm.url',
        'DOTS_MODEL_NAME': 'vllm.model_name',
        'DOTS_TEMPERATURE': 'vllm.temperature',
        'DOTS_TOP_P': 'vllm.top_p',
        'DOTS_MAX_COMPLETION_TOKENS': 'vllm.max_completion_tokens',

    }
    
    for env_key, config_path in env_mappings.items():
        env_value = os.environ.get(env_key)
        if env_value is not None:
            # 类型转换
            if env_value.lower() in ["true", "false"]:
                processed_value = env_value.lower() == "true"
            elif env_value.replace('.', '').isdigit():  # 处理浮点数
                try:
                    processed_value = float(env_value) if '.' in env_value else int(env_value)
                except (ValueError, TypeError):
                    processed_value = env_value
            else:
                processed_value = env_value
            
            # 设置嵌套配置
            parts = config_path.split('.')
            d = dots_env_config
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = processed_value
    
    if dots_env_config:
        return {'dots': dots_env_config}
    return {}

def load_configuration() -> RootConfig:
    """
    加载、合并和验证配置
    加载顺序: 默认YAML -> 环境变量 -> MinerU环境变量 -> DOTS环境变量
    """
    # 1. 从默认YAML文件加载
    logger.info(f"加载配置文件: {DEFAULT_CONFIG_PATH.absolute()}")
    config_data = _load_config_from_yaml(DEFAULT_CONFIG_PATH)

    # 2. 从KNOWFLOW_环境变量加载并覆盖
    env_data = _load_env_vars()
    if env_data:
        config_data = _recursive_update(config_data, env_data)
    
    # 3. 从MinerU环境变量加载并覆盖
    mineru_env_data = _load_mineru_env_vars()
    if mineru_env_data:
        config_data = _recursive_update(config_data, mineru_env_data)
        
    # 4. 从DOTS环境变量加载并覆盖
    dots_env_data = _load_dots_env_vars()
    if dots_env_data:
        config_data = _recursive_update(config_data, dots_env_data)

    # 5. 使用Pydantic模型进行验证
    try:
        return RootConfig.model_validate(config_data)
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        raise

def get_mineru_env_mapping() -> Dict[str, str]:
    """获取MinerU环境变量到配置路径的映射"""
    return {
        'MINERU_FASTAPI_URL': 'mineru.fastapi.url',
        'MINERU_FASTAPI_BACKEND': 'mineru.default_backend',
        'MINERU_PARSE_METHOD': 'mineru.pipeline.parse_method',
        'MINERU_LANG': 'mineru.pipeline.lang',
        'MINERU_FORMULA_ENABLE': 'mineru.pipeline.formula_enable',
        'MINERU_TABLE_ENABLE': 'mineru.pipeline.table_enable',
        'MINERU_VLM_HTTP_SERVER_URL': 'mineru.vlm.http_client.server_url',
    }

# 创建全局配置实例
CONFIG = load_configuration()
APP_CONFIG = CONFIG.app
EXCEL_CONFIG = CONFIG.excel
MINERU_CONFIG = CONFIG.mineru
DOTS_CONFIG = CONFIG.dots

# 打印加载的配置（在开发模式下）
if APP_CONFIG.dev_mode:
    import json
    logger.info("--- 加载的配置 (开发模式) ---")
    logger.info(json.dumps(CONFIG.model_dump(), indent=2))
    logger.info("-----------------------------") 