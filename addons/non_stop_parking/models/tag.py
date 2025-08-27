# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class Tag(models.Model):
    _name = 'nsp.tag'
    _description = 'Thẻ phương tiện'
    _rec_name = 'tag_id'

    tag_id = fields.Char(string="TID", required=True,help='Tag ID')
    epc = fields.Char(string="EPC",size=128,help='Electronic Product Code')
    valid_from = fields.Datetime(string="Ngày bắt đầu", help="Ngày bắt đầu của thẻ")
    valid_to = fields.Datetime(string="Ngày kết thúc", help="Ngày kết thúc của thẻ")
    status = fields.Selection(
        [('active', 'Hoạt động'),
        ('inactive', 'Không hoạt động'),
        ('pending', 'Chưa kích hoạt'),
        ('lost', 'Đánh mất')],
        string="Trạng thái",
        default='pending',
        required=True
    )

    # Fields for syncnarization
    last_sync_date = fields.Datetime('Last Sync Date')
    sync_from_cloud = fields.Boolean('Synced from Cloud', default=False)
    sync_status = fields.Selection([
        ('pending', 'Pending Sync'),
        ('synced', 'Synced'),
        ('error', 'Sync Error')
    ], default='pending')

    # Relations
    partner_id = fields.Many2one('res.partner', string="Người dùng", help="Người dùng sở hữu thẻ này")
    vehicle_id = fields.Many2one('nsp.vehicle', string="Phương tiện", help='Phương tiện gắn với thẻ này')
    
    # SQL Constraints
    _sql_constraints = [
        ('tag_id_unique', 'UNIQUE(tag_id)', 'Tag ID phải là duy nhất'),
    ]
    
    # Xóa thẻ
    def unlink(self):
        """Xóa thẻ"""
        for tag in self:
            if tag.status == 'active':
                raise ValidationError(_("Thẻ vẫn đang hoạt động, vui lòng thu hồi trước khi xóa."))
        return super().unlink()

    @api.constrains('tag_id')
    def _check_tag_id_unique(self):
        """Kiểm tra xem thẻ đã được tồn tại chưa"""
        for record in self: 
            if record.tag_id:
                existing = self.search([
                    ('tag_id', '=', record.tag_id),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(_("Tag ID '%s' đã tồn tại") % record.tag_id)

    # Thẻ chỉ được gán cho một người dùng hoặc một phương tiện (Không được có cả hai hoặc rỗng)
    @api.constrains('partner_id', 'vehicle_id')
    def _check_owner_type(self):
        """
        Thẻ chỉ được gán cho một người dùng hoặc một phương tiện
        """
        for record in self:
            if record.partner_id and record.vehicle_id:
                raise ValidationError(_("Thẻ chỉ được gán cho một người dùng hoặc một phương tiện (Không được có cả hai)"))