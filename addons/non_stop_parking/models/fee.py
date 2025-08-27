from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FeeCalculator(models.Model):
    _name = "nsp.fee"
    _description = "Phí ra/vào bãi đỗ xe"

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    default_price = fields.Monetary(string="Giá mặc định", currency_field="currency_id")
    vehicle_price = fields.Monetary(string="Giá theo loại xe", currency_field="currency_id")
    overnight_price = fields.Monetary(string="Giá gửi qua đêm", currency_field="currency_id")
    total_price = fields.Monetary(string="Tổng giá thành", currency_field="currency_id")

    # function/constraint goes here
    # TODO: if the default price is not set, opens up a form for the admin to enter the price
    def set_default_fee(self):
        """Set giá mặc định gửi xe"""
        for record in self:
            if record.default_price <= 0:
                raise ValidationError(_("Giá mặc định phải lớn hơn 0."))
        return True

    # TODO: display the "report" of the total price
    # TODO: api to deduct cash from the user (use res.partner's current_funds for the calculation)
    # TODO: call check_in from api_parking_logs to calculate fee
    # def calculate_fee(self):
    #     """Gọi API từ api_parking_logs.py"""
        #TODO: lấy chuỗi dữ liệu từ check_out
        #TODO: lấy parking_time từ vehicle_logs.py
        #TODO: kiểm tra success chưa, rồi tính phí