# controllers/api_users.py

import json
from odoo import http
from odoo.http import request
from .base import BaseAPI

class userAPIController(http.Controller):
    
    # ============ USER APIs ============

    @http.route('/api/v1/user/list', type='json', auth='public', methods=['POST'], csrf=False, cors="*")
    def list_users(self):
        """Lấy danh sách người dùng"""
        try:
            data = json.loads(http.request.httprequest.data)
            limit = data.get('limit', 50)
            offset = data.get('offset', 0)
            
            users = request.env['res.users'].sudo().search([], limit=limit, offset=offset, order='name desc')
            
            users_data = []
            for user in users:
                users_data.append({
                    'id': user.id,
                    'name': user.display_name,
                    'email': user.email or '',
                    'phone': user.phone or '',
                    'login': user.login,
                    'create_date': user.create_date.isoformat(),
                })
            
            return BaseAPI._get_response(True, {
                    'users': users_data,
                    'total': len(users),
                    'limit': limit,
                    'offset': offset,
                }, 'Lấy danh sách người dùng thành công')
        except Exception as e:
            return BaseAPI._handle_exception(e)
        
    # ============ TAG ASSIGNMENT APIs ============
    
    @http.route('/api/v1/assign-tag/user', type='json', auth='public', methods=['POST'], csrf=False, cors="*")
    def assign_tag_to_user(self):
        """Gán tag cho user"""
        try:
            data = json.loads(http.request.httprequest.data)
            user_id = data.get('user_id')
            tag_id = data.get('tag_id')
            
            if not user_id or not tag_id:
                return BaseAPI._get_response(False, message='user_id and tag_id are required', error_code="MISSING_PARAMS")
            
            # Kiểm tra user_id có tồn tại không
            user_id = request.env['res.users'].sudo().browse(user_id)
            if not user_id.exists():
                return BaseAPI._get_response(False, message="Không tìm thấy người dùng", error_code="USER_NOT_FOUND")
            
            # Gán tag
            result = user_id.assign_tag_to_user(user_id, tag_id)
            return BaseAPI._get_response(result['success'], message=result['message'])
        
        except Exception as e:
            return BaseAPI._handle_exception(e)
            