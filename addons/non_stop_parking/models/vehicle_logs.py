# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class VehicleLog(models.Model):
    _name = "nsp.vehicle.logs"
    _description = "Lịch sử ra vào phương tiện"
    _order = "create_date desc"
    _rec_name = "display_name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # Relations - Core fields
    vehicle_id = fields.Many2one('nsp.vehicle', string="Phương tiện", required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string="Người dùng", required=True, ondelete='cascade')
    tag_id = fields.Many2one('nsp.tag', string='Thẻ RFID', required=True, ondelete='cascade')
    
    # Computed fields
    display_name = fields.Char(string="Tên hiển thị", compute="_compute_display_name", store=True)
    partner_name = fields.Char(string="Tên người dùng", related='partner_id.name', store=True)
    vehicle_name = fields.Char(string="Tên phương tiện", related='vehicle_id.name', store=True)
    plate_number = fields.Char(string="Biển số xe", related='vehicle_id.plate_number', store=True)
    tag_code = fields.Char(string="mã thẻ", related='tag_id.tag_id', store=True)

    direction = fields.Selection([
        ('in', 'Vào'),
        ('out', 'Ra')
    ], string="Hướng", required=True)

    photo_url = fields.Char(string="Đường dẫn ảnh", help='URL hoặc đường dẫn đến ảnh')
    photo_binary = fields.Binary(string="Ảnh", attachment=True)
    # TODO thêm attachment
    photo_filename = fields.Char(string="Tên file ảnh")

    # additional into fields
    gate_name = fields.Char(string="Tên cổng", help="Tên cổng ra/vào")
    reader_device = fields.Char(string="Thiết bị đọc", help="Thiết bị đọc RFID")
    notes = fields.Text(string="Ghi chú")
    
    # Parking time fields
    parking_time = fields.Float(string="Thời gian đỗ (giờ)", digits=(16, 2), compute="_compute_parking_time", store=True, help="Thời gian xe đã ở trong bãi (tính bằng giờ)")
    parking_time_display = fields.Char(string="Thời gian đỗ", compute="_compute_parking_time_display", store=True, help="Hiển thị thời gian đỗ dạng dễ đọc")
    entry_log_id = fields.Many2one('nsp.vehicle.logs', string="Log vào bãi", help="Log tương ứng khi xe vào bãi")

    # Status fields for anomaly detection
    is_anomaly = fields.Boolean(string="Bất thường", default=False, help="Đánh dấu các log bất thường")
    anomaly_reason = fields.Text(string="Lý do bất thường")
    anomaly_warning = fields.Char(
        string='Cảnh báo',
        compute='_compute_anomaly_warning',
        store=False
    )
    
    # Unique constraints
    _sql_constraints = [
        ('check_direction', "CHECK (direction IN ('in', 'out'))", "Hướng phải là 'in' hoặc 'out'"),
    ]
    
    @api.depends('direction', 'create_date', 'vehicle_id')
    def _compute_parking_time(self):
        """Tính thời gian đỗ xe trong bãi"""
        for record in self:
            if record.direction == 'out' and record.vehicle_id:
                # Tìm log vào bãi gần nhất trước log ra này
                entry_log = self.search([
                    ('vehicle_id', '=', record.vehicle_id.id),
                    ('direction', '=', 'in'),
                    ('create_date', '<', record.create_date),
                    ('id', '!=', record.id)
                ], order='create_date desc', limit=1)
                
                if entry_log:
                    # Tính khoảng thời gian
                    time_diff = record.create_date - entry_log.create_date
                    parking_hours = time_diff.total_seconds() / 3600.0
                    record.parking_time = parking_hours
                    record.entry_log_id = entry_log.id
                else:
                    record.parking_time = 0.0
                    record.entry_log_id = False
            else:
                record.parking_time = 0.0
                record.entry_log_id = False
                
    @api.depends('parking_time')
    def _compute_parking_time_display(self):
        """Hiển thị thời gian đỗ dạng dễ đọc"""
        for record in self:
            if record.parking_time > 0:
                days = int(record.parking_time / 24)
                hours = int(record.parking_time) - days * 24
                minutes = int((record.parking_time - hours) * 60)

                if days > 0 and hours > 0:
                    record.parking_time_display = f"{days} ngày {hours} giờ"
                elif days > 0 and minutes > 0:
                    record.parking_time_display = f"{days} ngày {minutes} phút"
                elif hours > 0 and minutes > 0:
                    record.parking_time_display = f"{hours} giờ {minutes} phút"
                elif hours > 0:
                    record.parking_time_display = f"{hours} giờ"
                elif minutes > 0:
                    record.parking_time_display = f"{minutes} phút"
                else:
                    record.parking_time_display = "< 1 phút"

            else:
                record.parking_time_display = ""

    @api.depends('vehicle_id', 'direction', 'create_date')
    def _compute_display_name(self):
        """Tính toán tên hiển thị cho log"""
        for record in self:
            if record.vehicle_id and record.direction and record.create_date:
                direction_text = 'Vào' if record.direction == 'in' else 'Ra'
                record.display_name = _(f"{record.vehicle_id.plate_number} - {direction_text} ({record.create_date.strftime('%d/%m/%Y %H:%M:%S')})")
            else:
                record.display_name = _("Log chưa đầy đủ thông tin")

    @api.depends('is_anomaly')
    def _compute_anomaly_warning(self):
        for rec in self:
            rec.anomaly_warning = '⚠︎ WARNING' if rec.is_anomaly else ''

    @api.constrains('vehicle_id', 'partner_id', 'tag_id')
    def _check_required_fields(self):
        """Kiểm tra tính hợp lệ của các trường bắt buộc"""
        for record in self:
            if not record.vehicle_id:
                raise ValidationError(_("Phương tiện là bắt buộc"))
            if not record.partner_id:
                raise ValidationError(_("Người dùng là bắt buộc"))
            if not record.tag_id:
                raise ValidationError(_("Thẻ RFID là bắt buộc"))
            
    @api.model
    def create(self, vals):
        """Override create để kiểm tra tính nhất quán"""
        log = super().create(vals)
        return log

    @api.constrains('vehicle_id', 'tag_id')
    def _check_vehicle_tag_consistency(self):
        """Kiểm tra tính nhất quán giữa xe và thẻ"""
        for record in self:
            if not record.id:  # Skip nếu record chưa được tạo
                continue
                
            # Tìm log cuối cùng của xe này (trước log hiện tại)
            last_log = self.search([
                ('vehicle_id', '=', record.vehicle_id.id),
                ('tag_id', '=', record.tag_id.id),
                ('id', '!=', record.id),  # Loại trừ record hiện tại
                ('create_date', '<', record.create_date)
            ], order='create_date desc', limit=1)
            
            if last_log and last_log.direction == record.direction:
                # Phát hiện bất thường: cùng hướng liên tiếp
                try:
                    direction_text = 'Vào' if record.direction == 'in' else 'Ra'
                    record.write({
                        'is_anomaly': True,
                        'anomaly_reason': _(f"Xe {record.vehicle_id.name} {direction_text} 2 lần liên tiếp."
                                            f"Lần cuối là: {last_log.create_date.strftime('%d/%m/%Y %H:%M:%S')}")
                    })
                except Exception as e:
                    _logger.error(f"Lỗi khi ghi log bất thường: {e}")
            
                # Ghi log cảnh báo
                _logger.warning(f"Inconsistent vehicle log detected: Vehicle {record.vehicle_id.plate_number} "
                                  f"direction '{record.direction}' twice in a row. "
                                  f"Last: {last_log.create_date}, Current: {record.create_date}")
                
                # Tạo notification (optional) - chỉ tạo nếu không có lỗi
                try:
                    self._create_anomaly_notification(record, last_log)
                except Exception as e:
                    _logger.error(f"Lỗi khi tạo notification: {e}")

    def _create_anomaly_notification(self, current_log, last_log):
        """Tạo thông báo khi phát hiện bất thường"""
        try:
            # Tìm model_id cho nsp.vehicle.logs
            model = self.env['ir.model'].search([('model', '=', 'nsp.vehicle.logs')], limit=1)
            if not model:
                _logger.warning("Model nsp.vehicle.logs not found in ir_model, skipping notification")
                return
                
            # Tạo activity để thông báo
            self.env['mail.activity'].create({
                "activity_type_id": self.env.ref('mail.mail_activity_data_warning').id,
                'note': f"Phát hiện bất thường trong lịch sử ra vào xe {current_log.vehicle_id.plate_number}: \n"
                        f"- Hướng: {current_log.direction} \n"
                        f"- Thời gian trước: {last_log.create_date} \n"
                        f"Vui lòng kiểm tra lại dữ liệu.",
                'res_model_id': model.id,
                'res_id': current_log.id,
                'partner_id': self.env.user.partner_id.id,
            })
        except Exception as e:
            _logger.error(f"Fail to create anomaly notification: {e}")
    
    def _send_websocket_notification(self, log, vehicle, partner):
        """Gửi thông báo qua WebSocket"""
        try:
            message_data = {
                'type': 'parking_log_update',
                'log_id': log.id,
                'vehicle_plate': vehicle.plate_number,
                'partner_name': partner.name,
                'direction': log.direction,
                'time': log.create_date.strftime('%d/%m/%Y %H:%M:%S'),
                'is_anomaly': log.is_anomaly,
                'parking_time_display': log.parking_time_display,
                'photo_url': log.photo_url,
            }
            
            # Gửi notification đến channel 'nsp_system' như JavaScript đang subscribe
            self.env['bus.bus']._sendone(
                'nsp_system',  # channel name - phải khớp với JavaScript
                'parking_log_update',  # notification type
                message_data
            )
                    
            _logger.info(f"WebSocket notification sent for vehicle {vehicle.plate_number}")

        except Exception as e:
            _logger.error(f"Fail to send websocket notification: {e}")

    @api.model
    def create_log_entry(self, direction, tag_id, photo_url=None, notes=None):
        """
        Tạo log entry từ tag_id
        Args:
            tag_id (str): ID của thẻ RFID
            direction (str): 'in' hoặc 'out'
            photo_url (str): URL hình ảnh (optional)
            notes (str): Ghi chú (optional)
        Returns:
            dict: Kết quả tạo log
        """
        try:
            # Tìm thẻ
            tag = self.env['nsp.tag'].search([('tag_id', '=', tag_id)], limit=1)

            if not tag:
                return {
                    'success': False,
                    'message': _(f"Thẻ {tag_id} không tồn tại"),
                    'error_code': 'TAG_NOT_FOUND'
                }

            # Kiểm tra thẻ có active không
            if tag.status != 'active':
                return {
                    'success': False,
                    'message': _(f"Thẻ {tag_id} không hoạt động"),
                    'error_code': 'TAG_NOT_ACTIVE'
                }

            # Xác định vehicle và partner
            vehicle = tag.vehicle_id
            partner = tag.partner_id
            
            if not vehicle and not partner:
                return {
                    'success': False,
                    'message': _(f"Thẻ {tag_id} chưa được gán cho xe hoặc người dùng"),
                    'error_code': 'TAG_NOT_ASSIGNED'
                }
                
            # Nếu thẻ gán cho partner nhưng không có xe
            if partner and not vehicle:
                # Lấy xe đầu tiên của partner
                vehicle = partner.vehicle_ids[:1] if partner.vehicle_ids else None
                if not vehicle:
                    return {
                        'success': False,
                        'message': _(f"Người dùng {partner.name} chưa có xe đăng ký"),
                        'error_code': 'NO_VEHICLE_REGISTERED'
                    }
            
            # Nếu thẻ gán cho xe nhưng không có partner
            if vehicle and not partner:
                # Lấy partner từ owner_partner_id của xe
                partner = vehicle.owner_partner_id
                if not partner:
                    return {
                        'success': False,
                        'message': _(f"Phương tiện {vehicle.name} chưa được gán cho người dùng"),
                        'error_code': 'VEHICLE_NOT_ASSIGNED'
                    }

            # Đảm bảo cả vehicle và partner đều có
            if not vehicle or not partner:
                return {
                    'success': False,
                    'message': _(f"Không thể xác định xe hoặc người dùng cho thẻ {tag_id}"),
                    'error_code': 'INVALID_TAG_ASSIGNMENT'
                }

            # Tạo log entry
            log_data = {
                'vehicle_id': vehicle.id,
                'partner_id': partner.id,
                'tag_id': tag.id,
                'direction': direction,
                'photo_url': photo_url,
                'notes': notes,
            }

            # Tạo log
            log = self.create(log_data)

            # Cập nhật trạng thái xe
            try:
                vehicle.write({
                    'last_direction': direction,
                })
            except Exception as e:
                _logger.error(f"Lỗi khi cập nhật trạng thái xe: {e}")

            # Send notification through WebSocket
            self._send_websocket_notification(log, vehicle, partner)
            
            return {
                'success': True,
                'message': f'Ghi nhận thành công: {vehicle.plate_number} - {direction}',
                'data': {
                    'log_id': log.id,
                    'vehicle': vehicle.plate_number,
                    'partner': partner.name,
                    'direction':  direction,
                    'time': log.create_date.strftime('%d/%m/%Y %H:%M:%S'),
                    'is_anomaly': log.is_anomaly,
                    'parking_time': log.parking_time,
                    'parking_time_display': log.parking_time_display,
                }
            }
        except Exception as e:
            _logger.error(f"Fail to create log entry: {e}")
            return {
                'success': False,
                'message': str(e),
                'error_code': 'CREATE_LOG_FAILED'
            }

    @api.model
    def get_vehicle_status(self, vehicle_id):
        """
        Lấy trạng thái hiện tại của xe (in/out)
        Args:
            vehicle_id (int): ID của xe
        Returns:
            dict: Trạng thái xe
        """
        try:
            vehicle = self.env['nsp.vehicle'].browse(vehicle_id)
            if not vehicle.exists():
                return {
                    'success': False,
                    'message': f"Không tìm thấy xe",
                    'error_code': "VEHICLE_NOT_FOUND"
                }
                
            # Lấy log cuối cùng
            last_log = self.search([('vehicle_id', '=', vehicle.id)], limit=1, order='create_date desc')

            if not last_log:
                status = 'unknown'
                last_time = None
                current_parking_time = 0
            else:
                status = 'in' if last_log.direction == 'in' else 'out'
                last_time = last_log.create_date.strftime('%d/%m/%Y %H:%M:%S')

                # Tính thời gian đỗ hiện tại nếu xe đang trong bãi
                if status == "in":
                    time_diff = datetime.now() - last_log.create_date
                    current_parking_time = time_diff.total_seconds() / 3600.0
                else:
                    current_parking_time = 0.0

            return {
                'success': True,
                'data': {
                    'vehicle_id': vehicle_id,
                    'plate_number': vehicle.plate_number,
                    'status': status,
                    'last_time': last_time,
                    'last_direction': last_log.direction if last_log else None,
                    'current_parking_time': current_parking_time,
                    'current_parking_time_display': self._format_parking_time(current_parking_time)
                }
            }
        except Exception as e:
            _logger.error(f"fail to get vehicle status: {e}")
            return {
                'success': False,
                'message': 'Lỗi model',
                'error_code': 'MODEL_ERROR'
            }

    def _format_parking_time(self, parking_time):
        """Format thời gian đỗ để hiển thị"""
        if parking_time > 0:
            days = int(parking_time / 24)
            hours = int(parking_time) - days * 24
            minutes = int((parking_time - hours) * 60)
            
            if days > 0 and hours > 0:
                return f"{days} ngày {hours} giờ"
            elif days > 0 and minutes > 0:
                return f"{days} ngày {minutes} phút"
            elif hours > 0 and minutes > 0:
                return f"{hours} giờ {minutes} phút"
            elif hours > 0:
                return f"{hours} giờ"
            elif minutes > 0:
                return f"{minutes} phút"
            else:
                return "< 1 phút"
        return ""

    def action_view_vehicle(self):
        """Chuyển đến form view của phương tiện"""
        self.ensure_one()
        return {
            'name': _(f"Phương tiện: {self.vehicle_id.plate_number}"),
            'type': 'ir.actions.act_window',
            'res_model': 'nsp.vehicle',
            'view_mode': 'form',
            'res_id': self.vehicle_id.id,
            'target': 'new',
            'flags': {'mode': 'readonly'},
        }
        
    def action_view_partner(self):
        """Chuyển đến form view của Người dùng"""
        self.ensure_one()
        return {
            'name': _(f"Người dùng: {self.partner_id.name}"),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'res_id': self.partner_id.id,
            'target': 'new',
            'flags': {'mode': 'readonly'},
        }
    
    def action_view_entry_log(self):
        """Xem log vào bãi tương ứng"""
        self.ensure_one()
        if self.entry_log_id:
            return {
                'name': _(f"Log vào bãi: {self.entry_log_id.display_name}"),
                'type': 'ir.actions.act_window',
                'res_model': 'nsp.vehicle.logs',
                'view_mode': 'form',
                'res_id': self.entry_log_id.id,
                'target': 'new',
                'flags': {'mode': 'readonly'},
            }

    # Todo
    """
    Lấy thống kê ra vào bãi xe
    Args:
        date_from (str): Từ ngày (YYYY-MM-DD)
        date_to (str): Đến ngày (YYYY-MM-DD)
    Returns:
        dict: Thống kê
    """