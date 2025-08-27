import json
from odoo import http
from odoo.http import request
from .base import BaseAPI

class vehicleAPIController(http.Controller):
    
    # ============ VEHICLE APIs ============
    
    @http.route('/api/v1/vehicle/list', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def list_vehicles(self):
        try:
            data = json.loads(http.request.httprequest.data)
            limit = data.get('limit', 50)
            offset = data.get('offset', 0)
            owner_partner_id = data.get('owner_partner_id')
            if not limit:
                limit = 50
            if not offset:
                offset = 0
            if not owner_partner_id:
                return BaseAPI._get_response(False, message='owner_partner_id is required', error_code="MISSING_PARAMS")
                
            
            domain = [('owner_partner_id', '=', owner_partner_id)]
            
            vehicles = request.env['nsp.vehicle'].sudo().search(domain, limit=limit, offset=offset, order='name desc')

            vehicles_data = []
            for vehicle in vehicles:
                vehicles_data.append({
                    'id': vehicle.id,
                    'name': vehicle.name,
                    'plate_number': vehicle.plate_number,
                    'color': vehicle.color,
                    'vehicle_type': vehicle.vehicle_type,
                    'owner_partner_id': vehicle.owner_partner_id.id,
                    'owner_name': vehicle.owner_partner_id.name,
                    'vehicle_tag_id': vehicle.vehicle_tag_id.id if vehicle.vehicle_tag_id else None,
                    'create_date': vehicle.create_date.isoformat(),
                })
            
            return BaseAPI._get_response(True, {
                    'vehicles': vehicles_data,
                    'total': len(vehicles),
                    'limit': limit,
                    'offset': offset,
                }, 'Lấy danh sách phương tiện thành công')
        except Exception as e:
            return BaseAPI._handle_exception(e)
    
    # ============ TAG ASSIGNMENT APIs ============
    
    @http.route('/api/v1/assign-tag/vehicle', type='json', auth='public', methods=['POST'], csrf=False, cors="*")
    def assign_tag_to_vehicle(self):
        """Gán thẻ cho vehicle - API lắng nghe từ Windows app"""
        try:
            data = json.loads(http.request.httprequest.data)
            vehicle_id = data.get('vehicle_id')
            tag_id = data.get('tag_id')

            if not vehicle_id or not tag_id:
                return BaseAPI._get_response(False, message='vehicle_id and tag_id are required', error_code="MISSING_PARAMS")
            
            # Kiểm tra vehicle_id có tồn tại không
            vehicle = request.env['nsp.vehicle'].sudo().browse(vehicle_id)
            if not vehicle.exists():
                return BaseAPI._get_response(False, message='Không tìm thấy phương tiện', error_code="VEHICLE_NOT_FOUND")
            
            # Gán tag cho vehicle
            result = request.env['nsp.vehicle'].sudo().assign_tag_to_vehicle(vehicle_id, tag_id)
            return BaseAPI._get_response(result['success'], message=result['message'])

        except Exception as e:
            return BaseAPI._handle_exception(e)