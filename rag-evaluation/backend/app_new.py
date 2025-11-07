#!/usr/bin/env python3
"""
RAG 评估系统主应用
独立部署的 RAG 评估服务，可与多种 RAG 系统集成
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request
from flask_cors import CORS
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_logging(app):
    """配置日志"""
    # 设置根日志级别
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
        handlers=[
            logging.StreamHandler(),  # 控制台输出
        ]
    )

    # 创建日志目录
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 配置文件日志
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'evaluation.log'),
        maxBytes=10240000,
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(name)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)

    # 添加文件处理器到根日志器
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)

    app.logger.setLevel(logging.INFO)
    app.logger.info('RAG Evaluation System startup')
    print("✓ 日志系统已初始化 - 输出到控制台和 logs/evaluation.log")

def create_app():
    """应用工厂函数"""
    app = Flask(__name__)

    # 加载配置
    from config import get_config
    config_class = get_config()
    app.config.from_object(config_class)

    # 初始化配置
    config_class.init_app(app)

    # 加载环境变量
    # 1. 首先加载项目根目录的 .env
    project_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(project_env):
        load_dotenv(project_env, override=False)
        print(f"Loaded project .env from: {project_env}")

    # 2. 然后加载 backend 目录的 .env（如果存在）
    backend_env = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(backend_env):
        load_dotenv(backend_env, override=True)
        print(f"Loaded backend .env from: {backend_env}")

    # 3. 如果有 KnowFlow 的 .env 文件，也加载（向后兼容）
    knowflow_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'knowflow', '.env')
    if os.path.exists(knowflow_env):
        load_dotenv(knowflow_env, override=False)
        print(f"Loaded KnowFlow .env from: {knowflow_env}")

    # 配置日志
    setup_logging(app)

    # 启用 CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config['CORS_ORIGINS'],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # 注册评测蓝图 - 使用 evaluation_db.py
    try:
        from evaluation_db import init_services, evaluation_bp
        init_services()  # 初始化服务
        app.register_blueprint(evaluation_bp)
        app.logger.info("✅ Evaluation blueprint registered successfully")
    except ImportError as e:
        app.logger.error(f"❌ Failed to import evaluation_db module: {e}")
        print(f"Error: {e}")
        print("Make sure the evaluation_db.py file is in the same directory as app_new.py")
        raise e

    # 健康检查端点
    @app.route('/health')
    def health_check():
        return {
            'status': 'healthy',
            'service': 'rag-evaluation',
            'version': '1.0.0',
            'config': {
                'debug': app.config.get('DEBUG', False),
                'ragflow_url': app.config.get('RAGFLOW_BASE_URL'),
                'default_llm': app.config.get('DEFAULT_LLM_MODEL')
            }
        }

    # RAGFlow API 代理
    @app.route('/api/ragflow/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    def ragflow_proxy(path):
        """代理 RAGFlow API 请求"""
        import requests
        
        # 从配置读取 RAGFlow 地址
        ragflow_base_url = app.config.get('RAGFLOW_BASE_URL', 'http://localhost:9380')
        ragflow_api_key = app.config.get('RAGFLOW_API_KEY', '')
        
        # 构建目标 URL
        target_url = f"{ragflow_base_url}/{path}"
        
        # 准备请求头
        headers = dict(request.headers)
        headers.pop('Host', None)  # 移除 Host 头
        if ragflow_api_key:
            headers['Authorization'] = f'Bearer {ragflow_api_key}'
        
        # 转发请求
        try:
            resp = requests.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.args,
                json=request.get_json(silent=True),
                data=request.get_data() if request.get_json(silent=True) is None else None,
                timeout=30
            )
            
            # 返回响应
            return resp.content, resp.status_code, dict(resp.headers)
        except Exception as e:
            app.logger.error(f"RAGFlow proxy error: {str(e)}")
            return {'error': f'Failed to connect to RAGFlow: {str(e)}'}, 502

    # 根路径
    @app.route('/')
    def index():
        return {
            'service': 'RAG Evaluation System',
            'version': '1.0.0',
            'description': '独立部署的 RAG 系统评测工具',
            'endpoints': {
                'evaluation': '/api/v1/evaluation',
                'health': '/health',
                'docs': '/api/v1/evaluation/docs'
            },
            'features': [
                '支持多种 RAG 系统评测',
                '基于 RAGAS 框架',
                '多种评测指标',
                '可视化报告',
                '批量评测支持'
            ]
        }

    return app

if __name__ == '__main__':
    app = create_app()
    port = app.config.get('PORT', 5002)
    host = app.config.get('HOST', '0.0.0.0')

    print(f"\n{'='*60}")
    print(f"RAG Evaluation System")
    print(f"{'='*60}")
    print(f"Starting on {host}:{port}")
    print(f"Debug Mode: {app.config.get('DEBUG', False)}")
    print(f"RAGFlow URL: {app.config.get('RAGFLOW_BASE_URL')}")
    print(f"Default LLM: {app.config.get('DEFAULT_LLM_MODEL')}")
    print(f"{'='*60}")
    print(f"API Documentation: http://{host}:{port}/api/v1/evaluation/docs")
    print(f"Health Check: http://{host}:{port}/health")
    print(f"{'='*60}\n")

    app.run(host=host, port=port, debug=app.config.get('DEBUG', False))