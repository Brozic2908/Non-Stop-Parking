# controllers/hello_api.py

import json
from odoo import http, fields
from odoo.http import Response
from .base import BaseAPI
import logging

_logger = logging.getLogger(__name__)

class helloAPIController(http.Controller):
    # API Hello world for testing
    @http.route('/api/v1/hello', type='http', auth='public', methods=['GET'], csrf=False, cors='*')
    def hello_plain(self):
        return Response(json.dumps({'message': 'Hello, world!'}),
                        content_type='application/json')
        
    # API for testing one tag_id
    @http.route('/api/v1/test/1tag_id', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def hello_tag_id(self):
        data = json.loads(http.request.httprequest.data)
        tag_id = data.get('tag_id')
        if not tag_id:
            return {"success": False, "message": "Thiếu trường 'tag_id'"}
        message = f"Hello, {tag_id}"
        return {"success": True, "message": message}

    # API for testing many tag_id
    @http.route('/api/v1/test/ntag_id', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def hello_tag_ids(self):
        data = json.loads(http.request.httprequest.data)
        tag_ids = data.get('tag_ids', [])
        _logger.info(f"tag_ids: {tag_ids}")
        if not isinstance(tag_ids, list) or not tag_ids:
            return {"success": False, 'message': "Trường 'tag_ids' không hợp lệ."}
        messages = [f"Hello, {tag_id}" for tag_id in tag_ids]
        return {"success": True, "messages": messages}

    @http.route('/api/v1/health', type='json', auth='public', methods=['POST'], csrf=False, cors="*")
    def health_check(self):
        """Health check API"""
        return BaseAPI._get_response(True, {
            'status': 'healthy',
            'timestamp': fields.Datetime.now().isocalendar()
        }, "API đang hoạt động bình thường")