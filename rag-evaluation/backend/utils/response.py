"""
统一的API响应格式
标准化所有API的返回结构
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from flask import jsonify, Response


class ApiResponse:
    """统一的API响应格式"""

    @staticmethod
    def success(
        data: Any = None,
        message: str = "操作成功",
        code: int = 200,
        meta: Optional[Dict[str, Any]] = None
    ) -> Response:
        """成功响应"""
        response = {
            "success": True,
            "message": message,
            "code": code,
            "timestamp": datetime.now().isoformat(),
        }

        if data is not None:
            response["data"] = data

        if meta:
            response["meta"] = meta

        return jsonify(response), code

    @staticmethod
    def error(
        message: str = "操作失败",
        code: int = 500,
        details: Optional[Any] = None,
        errors: Optional[List[Dict[str, Any]]] = None
    ) -> Response:
        """错误响应"""
        response = {
            "success": False,
            "message": message,
            "code": code,
            "timestamp": datetime.now().isoformat(),
        }

        if details is not None:
            response["details"] = details

        if errors:
            response["errors"] = errors

        return jsonify(response), code

    @staticmethod
    def paginated(
        items: List[Any],
        total: int,
        offset: int = 0,
        limit: int = 10,
        message: str = "获取成功"
    ) -> Response:
        """分页响应"""
        return ApiResponse.success(
            data={
                "items": items,
                "pagination": {
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "has_next": offset + limit < total,
                    "has_prev": offset > 0,
                    "total_pages": (total + limit - 1) // limit,
                    "current_page": (offset // limit) + 1,
                }
            },
            message=message,
            meta={
                "count": len(items),
                "page_info": {
                    "showing_from": offset + 1,
                    "showing_to": min(offset + limit, total),
                }
            }
        )

    @staticmethod
    def created(
        data: Any = None,
        message: str = "创建成功",
        location: Optional[str] = None
    ) -> Response:
        """创建成功响应"""
        response = ApiResponse.success(data, message, 201)
        if location:
            response.headers["Location"] = location
        return response

    @staticmethod
    def no_content(message: str = "操作成功") -> Response:
        """无内容响应"""
        return ApiResponse.success(message=message, code=204)

    @staticmethod
    def bad_request(
        message: str = "请求参数错误",
        errors: Optional[List[Dict[str, Any]]] = None
    ) -> Response:
        """400错误响应"""
        return ApiResponse.error(message, 400, errors=errors)

    @staticmethod
    def unauthorized(message: str = "未授权访问") -> Response:
        """401错误响应"""
        return ApiResponse.error(message, 401)

    @staticmethod
    def forbidden(message: str = "禁止访问") -> Response:
        """403错误响应"""
        return ApiResponse.error(message, 403)

    @staticmethod
    def not_found(message: str = "资源不存在") -> Response:
        """404错误响应"""
        return ApiResponse.error(message, 404)

    @staticmethod
    def conflict(message: str = "资源冲突") -> Response:
        """409错误响应"""
        return ApiResponse.error(message, 409)

    @staticmethod
    def validation_error(
        field_errors: Dict[str, List[str]],
        message: str = "数据验证失败"
    ) -> Response:
        """验证错误响应"""
        errors = [
            {"field": field, "messages": messages}
            for field, messages in field_errors.items()
        ]
        return ApiResponse.bad_request(message, errors)


class BatchOperationResult:
    """批量操作结果"""

    def __init__(
        self,
        total: int,
        success: int = 0,
        failed: int = 0,
        skipped: int = 0,
        results: Optional[List[Dict[str, Any]]] = None
    ):
        self.total = total
        self.success = success
        self.failed = failed
        self.skipped = skipped
        self.results = results or []

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total == 0:
            return 0.0
        return (self.success / self.total) * 100

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": round(self.success_rate, 2),
            "results": self.results,
            "summary": f"总计 {self.total} 项，成功 {self.success} 项，失败 {self.failed} 项，跳过 {self.skipped} 项"
        }

    def to_response(self, message: str = None) -> Response:
        """转换为API响应"""
        if not message:
            message = self.to_dict()["summary"]

        return ApiResponse.success(
            data=self.to_dict(),
            message=message
        )


def handle_api_exception(func):
    """API异常处理装饰器"""
    from functools import wraps
    from werkzeug.exceptions import HTTPException
    import logging

    logger = logging.getLogger(__name__)

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPException as e:
            logger.warning(f"HTTP异常: {e.description}")
            return ApiResponse.error(
                message=e.description or str(e),
                code=e.code
            )
        except ValueError as e:
            logger.warning(f"值错误: {str(e)}")
            return ApiResponse.bad_request(str(e))
        except KeyError as e:
            logger.warning(f"键错误: 缺少参数 {str(e)}")
            return ApiResponse.bad_request(f"缺少必需参数: {str(e)}")
        except PermissionError as e:
            logger.warning(f"权限错误: {str(e)}")
            return ApiResponse.forbidden(str(e))
        except FileNotFoundError as e:
            logger.warning(f"文件未找到: {str(e)}")
            return ApiResponse.not_found(str(e))
        except Exception as e:
            logger.error(f"未处理的异常: {str(e)}", exc_info=True)
            return ApiResponse.error(
                message="服务器内部错误",
                details=str(e) if logger.isEnabledFor(logging.DEBUG) else None
            )

    return wrapper


def validate_json(required_fields: List[str] = None, optional_fields: List[str] = None):
    """JSON数据验证装饰器"""
    from functools import wraps
    from flask import request

    if required_fields is None:
        required_fields = []
    if optional_fields is None:
        optional_fields = []

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return ApiResponse.bad_request("请求必须是JSON格式")

            data = request.get_json()
            if not data:
                return ApiResponse.bad_request("请求体不能为空")

            # 检查必需字段
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return ApiResponse.bad_request(f"缺少必需字段: {', '.join(missing_fields)}")

            # 检查额外字段
            allowed_fields = set(required_fields + optional_fields)
            extra_fields = [field for field in data if field not in allowed_fields]
            if extra_fields:
                return ApiResponse.bad_request(f"不支持的字段: {', '.join(extra_fields)}")

            return func(*args, **kwargs)

        return wrapper
    return decorator


# ==================== 常用响应模板 ====================

class ResponseTemplates:
    """常用响应模板"""

    @staticmethod
    def delete_success(count: int = 1) -> Response:
        """删除成功响应"""
        message = f"成功删除 {count} 项"
        if count > 1:
            message += "记录"
        return ApiResponse.success(message=message)

    @staticmethod
    def batch_delete_result(
        deleted: List[str],
        failed: List[str] = None,
        skipped: List[str] = None
    ) -> Response:
        """批量删除结果响应"""
        result = BatchOperationResult(
            total=len(deleted) + (len(failed) if failed else 0) + (len(skipped) if skipped else 0),
            success=len(deleted),
            failed=len(failed) if failed else 0,
            skipped=len(skipped) if skipped else 0,
            results=[
                {"id": id, "status": "success"} for id in deleted
            ] + [
                {"id": id, "status": "failed"} for id in (failed or [])
            ] + [
                {"id": id, "status": "skipped"} for id in (skipped or [])
            ]
        )
        return result.to_response()

    @staticmethod
    def upload_success(
        file_id: str,
        filename: str,
        size: int = None
    ) -> Response:
        """上传成功响应"""
        data = {
            "id": file_id,
            "filename": filename,
        }
        if size is not None:
            data["size"] = size
        return ApiResponse.created(data, "文件上传成功")

    @staticmethod
    def task_status_update(
        task_id: str,
        old_status: str,
        new_status: str
    ) -> Response:
        """任务状态更新响应"""
        return ApiResponse.success(
            data={
                "task_id": task_id,
                "old_status": old_status,
                "new_status": new_status,
            },
            message=f"任务状态从 {old_status} 更新为 {new_status}"
        )