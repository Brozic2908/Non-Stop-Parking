import json
from odoo import http
from odoo.http import request
from .base import BaseAPI

class ParkingLogsAPIController(http.Controller):
    
    # ============ CHECK IN/OUT APIs ============
       
    @http.route('/api/v1/check/in', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def check_in(self):
        """
        API để ghi nhận xe vào bãi
        {
            "tag_ids": ["TAG001", "TAG002", "TAG003"],
            "photo_url": "https://example.com/photo.jpg",
            "notes": "Batch check in from API"
        }
        """
        try:
            data = json.loads(http.request.httprequest.data)
            tag_ids = data.get('tag_ids')
            photo_url = data.get('photo_url')
            notes = data.get('notes', 'Check in tự động từ API')

            if not tag_ids:
                return BaseAPI._get_response(False, message="tag_ids is required", error_code="MISSING_PARAMS")

            if not isinstance(tag_ids, list):
                return BaseAPI._get_response(False, message="tag_ids must be a list", error_code="INVALID_PARAMS")
            
            if notes and not isinstance(notes, str):
                return BaseAPI._get_response(False, message="Notes phải là string", error_code="INVALID_PARAMS")

            # Lọc các tag_id rỗng
            tag_ids = [tag_id for tag_id in tag_ids if tag_id]

            # Tìm tất cả tag_id trong hệ thống
            system_tags = request.env['nsp.tag'].sudo().search([('tag_id', 'in', tag_ids)])

            # Lấy vehicle_tags
            vehicle_tags = system_tags.filtered(lambda t: t.vehicle_id)

            # Kết quả khi tạo log
            results = []
            
            # Tạo log cho các thẻ xe
            for vehicle_tag in vehicle_tags:
                result = request.env['nsp.vehicle.logs'].sudo().create_log_entry(
                    tag_id=vehicle_tag.tag_id,
                    direction='in',
                    photo_url=photo_url,
                    notes=notes
                )

                results.append({
                    'tag_id': vehicle_tag.tag_id,
                    'vehicle_plate_number': vehicle_tag.vehicle_id.plate_number,
                    'vehicle_owner': vehicle_tag.vehicle_id.owner_partner_id.name,
                    'success': result['success'],
                    'message': result['message'],
                    'data': result.get('data', {}),
                    'error_code': result.get('error_code', 'SUCCESS')
                })

            any_success = any(r['success'] for r in results)
            return BaseAPI._get_response(
                any_success,
                data=results,
                message="Successful processing",
                error_code='SUCCESS'
            )

        except Exception as e:
            return BaseAPI._handle_exception(e)

    @http.route('/api/v1/check/out', type='json', auth='public', methods=['POST'], csrf=False, cors='*')
    def check_out(self):
        """
        API để ghi nhận xe ra khỏi bãi với logic kiểm tra nghiêm ngặt
        {
            "tag_ids": ["TAG001", "TAG002", "TAG003"],
            "photo_url": "https://example.com/photo.jpg",
            "notes": "Batch check out from API"
        }
        """
        try:
            data = json.loads(http.request.httprequest.data)
            tag_ids = data.get('tag_ids', [])
            photo_url = data.get('photo_url')
            notes = data.get('notes', 'Check out từ API')

            if not tag_ids:
                return BaseAPI._get_response(False, message='tag_ids is required', error_code="MISSING_PARAMS")

            if not isinstance(tag_ids, list):
                return BaseAPI._get_response(False, message='tag_ids phải là danh sách', error_code="INVALID_PARAMS")
            
            if len(tag_ids) < 2:
                return BaseAPI._get_response(False, message="Phải có ít nhất 2 thẻ để check out", error_code="INSUFFICIENT_TAGS")

            if notes and not isinstance(notes, str):
                return BaseAPI._get_response(False, message="Notes phải là string", error_code="INVALID_PARAMS")

            # Lọc các tag_id rỗng
            tag_ids = [tag_id for tag_id in tag_ids if tag_id]

            # Tìm tất cả tag_id trong hệ thống
            system_tags = request.env['nsp.tag'].sudo().search([('tag_id', 'in', tag_ids)])

            # 1. Kiểm tra thẻ có tồn tại trong hệ thống không
            found_tags = system_tags.mapped('tag_id')
            missing_tags = set(tag_ids) - set(found_tags)
            if missing_tags:
                return BaseAPI._get_response(False, message=f"Các thẻ {", ".join(missing_tags)} không tồn tại trong hệ thống", error_code="TAGS_NOT_FOUND")

            # Kiểm tra tất cả thẻ phải active
            inactive_tags = system_tags.filtered(lambda x: x.status != 'active')
            if inactive_tags:
                return BaseAPI._get_response(False, message=f"Các thẻ {", ".join(inactive_tags.mapped('tag_id'))} không hoạt động", error_code="TAGS_NOT_ACTIVE")

            # 2. Phân loại thẻ
            person_tags = system_tags.filtered(lambda t: t.partner_id and not t.vehicle_id)
            vehicle_tags = system_tags.filtered(lambda t: t.vehicle_id and not t.partner_id)
            unassigned_tags = system_tags.filtered(lambda t: not t.partner_id and not t.vehicle_id)
            mixed_tags = system_tags.filtered(lambda t: t.partner_id and t.vehicle_id)
            
            # Validate các loại thẻ
            if unassigned_tags:
                return BaseAPI._get_response(False, message=f"Các thẻ {", ".join(unassigned_tags.mapped("tag_id"))} không được gắn với phương tiện hoặc người dùng", error_code="TAGS_NOT_ASSIGNED")
            
            if mixed_tags:
                return BaseAPI._get_response(False, message=f"Các thẻ {", ".join(mixed_tags.mapped("tag_id"))} đã được gắn với cả phương tiện và người dùng", error_code="TAGS_MIXED_ASSIGNED")

            # 3. Kiểm tra có đủ thẻ người và thẻ xe chưa
            if not person_tags:
                return BaseAPI._get_response(False, message="Phải có ít nhất 1 thẻ người dùng", error_code="NO_PERSON_TAG")
            
            if not vehicle_tags:
                return BaseAPI._get_response(False, message="Phải có ít nhất 1 thẻ phương tiện", error_code="NO_VEHICLE_TAG")

            # Lấy danh sách người và xe
            persons = person_tags.mapped("partner_id")
            vehicles = vehicle_tags.mapped("vehicle_id")

            # 4. Kiểm tra quyền sở hữu - Mỗi xe phải thuộc về ít nhât 1 người trong danh sách
            ownership_errors = []
            for vehicle in vehicles:
                if not vehicle.owner_partner_id:
                    ownership_errors.append(f"Xe {vehicle.name} không có người sở hữu")
                    continue

                if vehicle.owner_partner_id not in persons:
                    ownership_errors.append(f"Xe {vehicle.name} không thuộc về người dùng {vehicle.owner_partner_id.name}")
                    continue

            if ownership_errors:
                return BaseAPI._get_response(False, message=";\n".join(ownership_errors), error_code="INVALID_OWNERSHIP")

            # 5. Kiểm tra trạng thái xe - Xe phải đang ở trong bãi
            status_errors = []
            for vehicle in vehicles:
                if vehicle.current_status != 'inside':
                    status_errors.append(f"Xe {vehicle.name} - {vehicle.plate_number} không đang ở trong bãi")
            
            if status_errors:
                return BaseAPI._get_response(False, message=";\n".join(status_errors), error_code="INVALID_STATUS")

            # Gọi method tạo log nếu tất cả thẻ để pass
            results = []
            for vehicle_tag in vehicle_tags:
                vehicle = vehicle_tag.vehicle_id
                person = vehicle_tag.partner_id
                
                # Gọi method tạo log
                result = request.env['nsp.vehicle.logs'].sudo().create_log_entry(
                    tag_id=vehicle_tag.tag_id,
                    direction='out',
                    photo_url=photo_url,
                    notes=notes,
                )

                results.append({
                    'tag_id': vehicle_tag.tag_id,
                    'vehicle_plate_number': vehicle.plate_number if vehicle else None,
                    'vehicle_owner': person.name if person else None,
                    'success': result['success'],
                    'message': result['message'],
                    'data': result.get('data', {}),
                    'error_code': result.get('error_code', 'SUCCESS')
                })

            any_success = any(r['success'] for r in results)
            return BaseAPI._get_response(
                any_success, 
                data=results, 
                message="Successful processing",
                error_code='SUCCESS'
            )

        except Exception as e:
            return BaseAPI._handle_exception(e)
    