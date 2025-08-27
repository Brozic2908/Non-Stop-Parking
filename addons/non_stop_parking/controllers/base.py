import logging
from odoo.exceptions import ValidationError, AccessError

_logger = logging.getLogger(__name__)

BASE_URL = 'http://192.168.1.222:8069'

class BaseAPI:
    @staticmethod
    def _get_response(success=True, data=None, message="", error_code=None):
        """Tạo response chuẩn cho API"""
        response = {
            'success': success,
            'message': message,
            'data': data or {}
        }
        _logger.info(f"API Response: {response}")
        if error_code:
            response['error_code'] = error_code
        return response

    @staticmethod
    def _handle_exception(e):
        """Xử lý exception và trả về response lỗi"""
        _logger.error(f"API Error: {str(e)}")
        if isinstance(e, ValidationError):
            return BaseAPI._get_response(False, message=str(e), error_code="VALIDATION_ERROR")
        elif isinstance(e, AccessError):
            return BaseAPI._get_response(False, message="Không có quyền truy cập", error_code="ACCESS_ERROR")
        return BaseAPI._get_response(False, message="Lỗi hệ thống", error_code="SYSTEM_ERROR")
    
    @staticmethod
    def _base_url():
        return BASE_URL