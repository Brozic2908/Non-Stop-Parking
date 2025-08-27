from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class AddFundsWizard(models.TransientModel):
    _name = "res.partner.add.funds.wizard"
    _description = "Add Funds Wizard"

    partner_id = fields.Many2one('res.partner', required=True, readonly=True)
    bank_account = fields.Char(string="Số tài khoản thanh toán")
    amount = fields.Monetary(string="Số tiền cần nạp", required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    fund_package_id = fields.Many2one(
        'nsp.fund.package',
        string="Chọn gói nạp",
        required=True
    )
    
    #TODO: add logic to handle payment via payment providers e.g PayPal, Amazon, MoMo, etc

    def confirm_adding_funds(self):
        self.partner_id.current_funds += self.amount
