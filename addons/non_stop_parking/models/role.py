from odoo import models, fields, api
from odoo.exceptions import ValidationError

class Roles(models.Model):
    _name = 'nsp.role'
    _description = 'a model for creating roles for staffs'

    name = fields.Char("Role Name",required=True)
    description = fields.Char("Description")

    group_id = fields.Many2many(
        'res.groups',
        string='Group',
        help='Các quyền truy cập của role này'
    )

    date_created = fields.Date("Creation Date")
