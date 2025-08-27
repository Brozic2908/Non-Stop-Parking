# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.http import request
from odoo.exceptions import ValidationError

class Vehicle(models.Model):
    _name="nsp.vehicle"
    _description="Phương tiện"
    _rec_name = 'plate_number'
    
    name = fields.Char(string="Tên phương tiện", required=True)
    brand = fields.Char(string="Hãng xe")
    plate_number = fields.Char(string="Biến số xe", size=20, required=True)
    color = fields.Char(string="Màu sắc")
    vehicle_type = fields.Selection([
        ('car', 'Ô tô'),
        ('motorcycle', 'Xe máy'),
        ('bicycle', 'Xe đạp'),
        ('truck', 'Xe tải'),
        ('other', 'Khác')
    ], string='Loại xe', default='motorcycle', required=True)

    # Status tracking fields
    last_direction = fields.Selection([
        ('in', 'Vào'),
        ('out', 'Ra'),
    ], string="Hướng cuối cùng", default='in')
    current_status = fields.Selection([
        ('inside', 'Trong bãi'),
        ('outside', 'Ngoài bãi'),
        ('unknown', 'Không xác định')
    ], string="Trạng thái hiện tại", default='unknown', compute="_compute_current_status", store=True, help="Hướng di chuyển cuối cùng của xe")

    # Relations
    # Quan hệ Nhiều-Một: Nhiều xe thuộc về một chủ sở hữu
    owner_partner_id = fields.Many2one('res.partner', string="Chủ sở hữu")

    # Quan hệ Một-Một (thực hiện bằng Many2one + unique constraint)
    # Một xe chỉ được gắn một thẻ
    vehicle_tag_id = fields.Many2one('nsp.tag', string="Thẻ phương tiện", help="Thẻ RFID gắn với phương tiện này")

    # 1 Xe có thể có nhiều logs
    vehicle_logs_ids = fields.One2many('nsp.vehicle.logs', 'vehicle_id', string="Lịch sử ra vào")
    
    # Ràng buộc dữ liệu
    _sql_constraints = [
        ('plate_number_unique', 'UNIQUE(plate_number)', 'Biển số xe phải là duy nhất'),
        ('vehicle_tag_id_unique', 'UNIQUE(vehicle_tag_id)', 'Mỗi thẻ chỉ được gán cho một xe!')
    ]

    @api.depends('last_direction')
    def _compute_current_status(self):
        """Tính toán trạng thái hiện tại dựa trên hướng cuối cùng"""
        for vehicle in self:
            if vehicle.last_direction == 'in':
                vehicle.current_status = 'inside'
            elif vehicle.last_direction == 'out':
                vehicle.current_status = 'outside'
            else:
                vehicle.current_status = 'unknown'

    @api.model
    def create(self, vals):
        """Tạo phương tiện"""
        vehicle = super().create(vals)
        return vehicle
    
    def write(self, vals):
        """Cập nhật phương tiện"""
        result = super().write(vals)
        return result
    
    @api.model
    def assign_tag_to_vehicle(self, vehicle_id, tag_id):
        """API method để gán tag trực tiếp cho vehicle"""
        vehicle = self.browse(vehicle_id)
        if not vehicle.exists():
            return {'success': False, 'message': 'Không tìm thấy phương tiện'}
        
        # Kiểm tra tag đã tồn tại hay chưa
        existing_tag = self.env['nsp.tag'].search([
            ('tag_id', '=', tag_id)
        ])
        
        if existing_tag:
            if existing_tag.status == 'active':
                # Kiểm tra tag đã được gán cho vehicle khác chưa
                if existing_tag.vehicle_id and existing_tag.vehicle_id != vehicle:
                    return {
                        'success': False, 
                        'message': f"Thẻ này đã được sử dụng."
                    }
                    
                if existing_tag.partner_id:
                    return {
                        'success': False,
                        'message': f"Thẻ này đã được sử dụng."
                    }
                    # Nếu tag đang active nhưng không gán cho ai, cũng không cho gán (tránh trường hợp lỗi dữ liệu)
                return {
                    'success': False,
                    'message': "Thẻ này đang ở trạng thái active nhưng không gán cho ai. Vui lòng kiểm tra lại dữ liệu."
                }
                
            # Gán tag hiện có cho vehicle
            existing_tag.vehicle_id = vehicle.id
            existing_tag.status = 'active'
            vehicle.vehicle_tag_id = existing_tag.id
        else:
            # Tạo tag mới và gán cho vehicle
            new_tag = self.env['nsp.tag'].create({
                'tag_id': tag_id,
                'status': 'active',
                'vehicle_id': vehicle.id,
            })
            vehicle.vehicle_tag_id = new_tag.id
        
        return {'success': True, 'message': 'Tag đã được gán thành công'}
    
    # Lấy thẻ mới từ API và gán vào vehicle_tag_id
    def action_refresh_temp_tag_vehicle(self):
        """Lấy thẻ mới từ API và gán vào vehicle_tag_id"""
        for vehicle in self:
            # Trả về action để gọi JavaScript function
            return {
                'type': 'ir.actions.client',
                'name': _('Scan RFID'),
                'tag': 'call_rfid_reader_vehicle',
                'params': {
                    'vehicle_id': vehicle.id,
                    'action': 'scan_and_assign_tag'
                }
            }

    # Thu hồi thẻ
    def action_revoke_tag(self):
        """Thu hồi thẻ"""
        for vehicle in self:
            tag = vehicle.vehicle_tag_id
            if tag:
                tag.write({
                    'partner_id': False,
                    'vehicle_id': False,
                    'status': 'inactive',
                })
                vehicle.vehicle_tag_id = False
                
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Thu hồi thẻ thành công'),
                'message': _('Thẻ đã được thu hồi thành công'),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            }
        }

    # def action_check_in(self):
    #     """Thực hiện check in thủ công"""
    #     if not self.vehicle_tag_id:
    #         raise ValidationError(_("Xe chưa có thẻ RFID"))
        
    #     result = self.env['nsp.vehicle.logs'].create_log_entry(
    #         tag_id=self.vehicle_tag_id.tag_id,
    #         direction='in',
    #         notes='Check in thủ công từ form xe'
    #     )
        
    #     if result['success']:
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'title': _('Check in thành công'),
    #                 'message': result['message'],
    #                 'type': 'success',
    #             }
    #         }
    #     else:
    #         raise ValidationError(result['message'])
    # def action_check_out(self):
    #     """Thực hiện check out thủ công"""
    #     if not self.vehicle_tag_id:
    #         raise ValidationError(_("Xe chưa có thẻ RFID"))
        
    #     result = self.env['nsp.vehicle.logs'].create_log_entry(
    #         tag_id=self.vehicle_tag_id.tag_id,
    #         direction='out',
    #         notes='Check out thủ công từ form xe'
    #     )
        
    #     if result['success']:
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'title': _('Check out thành công'),
    #                 'message': result['message'],
    #                 'type': 'success',
    #             }
    #         }
    #     else:
    #         raise ValidationError(result['message'])