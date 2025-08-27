from odoo import models, fields, api, _
from odoo.http import request
from odoo.exceptions import ValidationError

class VehiclePrice(models.Model):
    _name = "nsp.vehicle.price"
    _description = "Giá thành cho từng loại xe theo thời gian"

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)

    vehicle_type = fields.Char(string="Loại xe")
    day_time = fields.Monetary(string="Giá Ngày", currency_field="currency_id")
    night_time = fields.Monetary(string="Giá Đêm", currency_field="currency_id")

    @api.constrains('day_time', 'night_time')
    def _check_price_time(self):
        """Gói nạp phải it nhất 2000 VND"""
        for record in self:
            if (record.day_time <= 0 or record.day_time < 1000) and (record.night_time <= 0 or record.night_time < 1000):
                raise ValidationError(_("Giá tối thiểu là 1000 VND"))