# controllers/api_tags.py

import json
from odoo import http
from odoo.http import request
from .base import BaseAPI

class tagAPIController(http.Controller):
    def _check_param_tag_id(tag_id):
        if not tag_id:
            return BaseAPI._get_response(False, message="Tag ID không được để trống", error_code="MISSING_PARAM")
    
    # ============ TAG APIs ============
    @http.route('/api/v1/tag/check', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def check_tag_exists(self, **data):
        """Kiểm tra tag có tồn tại trong database không"""
        try:
            # Lấy dữ liệu từ request body
            tag_id = data.get('tag_id')
            self._check_param_tag_id(tag_id)
            
            tag = request.env['nsp.tag'].sudo().search([('tag_id', '=', tag_id)], limit=1)

            if tag:
                tag_data = {
                    'id': tag.id,
                    'tag_id': tag.tag_id,
                    'epc': tag.epc,
                    'status': tag.status,
                    'user_id': tag.user_id.id if tag.user_id else None,
                    'user_name': tag.user_id.name if tag.user_id else None,
                    'vehicle_id': tag.vehicle_id.id if tag.vehicle_id else None,
                    'vehicle_name': tag.vehicle_id.name if tag.vehicle_id else None,
                    'create_date': tag.create_date.isoformat() 
                }
                return BaseAPI._get_response(True, tag_data, "Tag đã tồn tại trong hệ thống")
            else:
                return BaseAPI._get_response(False, message="Tag không tồn tại trong hệ thống", error_code="TAG_NOT_FOUND")
        
        except Exception as e:
            return BaseAPI._handle_exception(e)
    
    @http.route('/api/v1/tag/create', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def create_tag(self, **data):
        """Tạo bảng mới"""
        try: 
            tag_id = data.get('tag_id')
            epc = data.get('epc')
            status = data.get('status', 'pending')
            
            self._check_param_tag_id(tag_id)
            
            # Kiểm tra tag đã tồn tại 
            existing_tag = request.env['nsp.tag'].sudo().search([('tag_id', '=', tag_id)], limit=1)
            if existing_tag:
                return BaseAPI._get_response(False, message='Tag ID đã tồn tại', error_code="TAG_EXISTS")
            
            # Tạo tag mới
            tag = request.env['nsp.tag'].sudo().create({
                'tag_id': tag_id,
                'epc': epc,
                'status': status
            })
            
            tag_data = {
                'id': tag.id,
                'tag_id': tag.tag_id,
                'epc': tag.epc,
                'status': tag.status,
                'create_date': tag.create_date.isoformat()
            }
            return BaseAPI._get_response(True, tag_data, "Tạo tag thành công")
            
        except Exception as e:
            return BaseAPI._handle_exception(e)
