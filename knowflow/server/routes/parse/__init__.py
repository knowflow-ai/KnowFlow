from flask import Blueprint

parse_bp = Blueprint('parse', __name__)

from . import mineru, dots, smart_chunk
