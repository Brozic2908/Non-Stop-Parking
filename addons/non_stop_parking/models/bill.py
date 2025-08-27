from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

class Bill(models.Model):
    _name = "nsp.bill"
    _description = "Hóa đơn gửi xe của NSP"

    vehicle_logs_id = fields.Many2one("nsp.vehicle.logs", string="Lịch sử đỗ xe", required=True, ondelete='cascade')
    vehicle_type_and_price = fields.Many2one("nsp.vehicle.price", string="Giá theo loại xe")

    #computed_fields
    user_name = fields.Char(string='Tên', related="vehicle_logs_id.partner_name", store=True)
    vehicle_name = fields.Char(string="Phương tiện", related="vehicle_logs_id.vehicle_name", store=True)
    tag_code = fields.Char(string="Mã thẻ", related="vehicle_logs_id.tag_code", store=True)
    parking_time = fields.Float(string="Thởi gian đỗ", related="vehicle_logs_id.parking_time", store=True)
    vehicle_type = fields.Char(string="Loại xe", related="vehicle_type_and_price.vehicle_type", store=True)

    parking_time_display = fields.Char(string="Thời gian đã đỗ", related="vehicle_logs_id.parking_time_display", store=True)

    #price fields
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)

    base_price = fields.Monetary(string="Giá gửi", currency_field="currency_id")
    overnight_price = fields.Monetary(string="Giá gửi qua đêm", currency_field="currency_id")
    total_price = fields.Monetary(string="Tổng giá thành", currency_field="currency_id") 

    # TODO: api to deduct cash from the user (use res.partner's current_funds for the calculation)
    # TODO: call check_in from api_parking_logs to calculate fee
    # TODO: test tính phí bằng POSTMAN
    def calculate_fee(self, response):
        """Gọi API từ api_parking_logs.py"""
        for record in self:
            error_code = response.get('error_code', 'SUCCESS')
            if error_code == 'SUCCESS':
                parking_log = self.env['nsp.vehicle.logs'].search([
                    ('tag_code', '=', record.tag_code),
                    ('parking_time', '=', record.parking_time)
                ])
                vehicle_pricing = self.env['nsp.vehicle.price'].search([
                    ('vehicle_type', '=', record.vehicle_type)
                ])
                if parking_log:
                    day = 0
                    # Match "x ngày"
                    match = re.search(r'(\d+)\s*ngày', parking_log.parking_time_display)
                    if match:
                        day = int(match.group(1))

                    if day > 0:
                        record.overnight_price = day * 5000
                    
                    log_time = parking_log.create_date.time()
                    night_threshold = time(15, 0)

                    if log_time >= night_threshold: #find the date of creation to find the exact hour and minute
                        record.base_price = vehicle_pricing.night_time
                        record.total_price = record.base_price + record.overnight_price
                        
                    else:
                        record.base_price = vehicle_pricing.day_time
                        record.total_price = record.base_price + record.overnight_price
                        
                    self.env['nsp.bill'].create({
                            'user_name': record.user_name,
                            'vehicle_name': record.vehicle_name,
                            'vehicle_type': vehicle_pricing.vehicle_type,
                            'tag_code': record.tag_code,
                            'parking_time_display': parking_log.parking_time_display,
                            'base_price': record.base_price,
                            'overnight_price': record.overnight_price,
                            'total_price': record.total_price
                        })
                    
                    record.deduct_cash_from_user()

    def deduct_cash_from_user(self):
        """Trừ hao số dư người dùng"""
        partner = self.env.user.partner_id
        for record in self:
            if partner.current_funds < record.total_price:
                """Cảnh báo người dùng đã hết số dư"""
            partner.current_funds -= record.total_price
