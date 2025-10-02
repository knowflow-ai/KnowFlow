# 路由模块初始化
from flask import Blueprint

# 创建蓝图
users_bp = Blueprint('users', __name__, url_prefix='/api/v1/users')
teams_bp = Blueprint('teams', __name__, url_prefix='/api/v1/teams')
tenants_bp = Blueprint('tenants', __name__, url_prefix='/api/v1/tenants')
files_bp = Blueprint('files', __name__, url_prefix='/api/v1/files')
knowledgebase_bp = Blueprint('knowledgebases', __name__, url_prefix='/api/v1/knowledgebases')
documents_bp = Blueprint('documents', __name__, url_prefix='/api/v1/documents')

# 导入路由
from .users.routes import *
from .teams.routes import *
from .tenants.routes import *
from .files.routes import *
from .knowledgebases.routes import *
from .documents.routes import *
from .rbac.rbac_routes import rbac_bp
from .rbac.permission_routes import permission_bp
from .parse import parse_bp

def register_routes(app):
    """注册所有路由蓝图到应用"""
    app.register_blueprint(users_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(tenants_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(knowledgebase_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(rbac_bp)
    app.register_blueprint(permission_bp)
    app.register_blueprint(parse_bp)