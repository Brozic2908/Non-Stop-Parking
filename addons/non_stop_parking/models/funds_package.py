from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FundPackage(models.Model):
    _name = "nsp.fund.package"
    _description = "Gói nạp tiền"

    price = fields.Monetary(string="Gói tiền", required=True, currency_field="currency_id")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)

    @api.constrains('price')
    def _check_price_package(self):
        """Gói nạp phải it nhất 2000 VND"""
        for record in self:
            if record.price <= 0 or record.price < 2000:
                raise ValidationError(_("Giá gói phải ít nhất là 2000 VND"))
            
    def action_select_package(self):
        """Cập nhật số dư của người dùng"""
        partner = self.env.user.partner_id
        for package in self:
            partner.current_funds += package.price