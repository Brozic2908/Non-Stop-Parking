# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.http import request
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    """
    Kế thừa model res.partner để thêm các trường và logic cho việc quản lý bãi đỗ xe.
    Bằng cách này, mỗi người dùng Odoo cũng có thể là một người dùng bãi đỗ xe.
    """
    _inherit = "res.partner"
    _rec_name = 'name'

    # Tag assignment fields
    citizen_id = fields.Char(string='CCCD/CMND', help="CCCD/CMND của người dùng")

    current_funds = fields.Monetary(string="Số dư", currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    
    # Relations
    partner_tag_id = fields.Many2one('nsp.tag', string='Thẻ thành viên')
    vehicle_ids = fields.One2many('nsp.vehicle', 'owner_partner_id', string="Phương tiện sở hữu")
    partner_logs_ids = fields.One2many('nsp.vehicle.logs', 'partner_id', string="Lịch sử ra vào")
    
    user_ids = fields.One2many('res.users', 'partner_id', string="Linked Users")

    # Contraints
    _sql_constraints = [
        ('citizen_id_unique', 'unique(citizen_id)', 'CCCD/CMND phải là duy nhất')
    ]

    roles = fields.Many2many(
        'nsp.role',
        'res_partner_nsp_role_rel',
        'partner_id',                   
        'role_id',                      
        string='Roles',
        help='Access rights to be assigned to a user'
    )

    groups = fields.Many2many(
        'res.groups',
        string='Role Groups',
        compute='_compute_groups_from_roles',
        store=False,
        help='Groups assigned to the role above, which will provide the neccessary access rights'
    )
    
    display_funds = fields.Char(string="Số dư", compute='_get_display_funds')

    # Kiểm tra CCCD/CMND phải là duy nhất
    @api.constrains('citizen_id')
    def _check_citizen_id(self):
        """Kiểm tra CCCD/CMND phải là duy nhất"""
        for record in self:
            if record.citizen_id:
                # Kiểm tra độ dài (CCCD: 12 số, CMND: 9 số)
                if len(record.citizen_id) not in [9, 12]:
                    raise ValidationError(_("CCCD phải có 9 số và CMND phải có 12 số"))
                # Kiểm tra chỉ chứa số
                if not record.citizen_id.isdigit():
                    raise ValidationError(_("CCCD/CMND phải là số"))
                
    @api.model
    def open_profile(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'view_id': self.env.ref('non_stop_parking.nsp_profile_view_form').id,
            'res_id': self.env.user.partner_id.id,
            'target': 'current',
        }
    
    def _get_display_funds(self):
        for record in self:
            record.display_funds = f"Số dư: {record.currency_id.symbol or ''}{record.current_funds:,.0f}"

    def open_fund_package_kanban(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chọn Gói Nạp Tiền'),
            'res_model': 'nsp.fund.package',
            'view_mode': 'kanban',
            'view_id': self.env.ref('non_stop_parking.nsp_funds_package_kanban_view').id,
            'target': 'new',
        }

    # Tạo partner và user
    @api.model
    def create(self, vals):
        """Tạo partner và user"""
        partner = super().create(vals)

        user = self.env['res.users'].create({
            'name': partner.name,
            'login': partner.email,
            'email': partner.email,
            'partner_id': partner.id,
        })

        partner.assign_default_roles()
        return partner
	
    # Cập nhật partner
    def write(self, vals):
        """Cập nhật partner"""
        result = super().write(vals)
        self.assign_groups_from_roles()
        return result
    
    def unlink(self):
        """Delete partern và user mà nó được link đến"""
        for partner in self:
            if partner.user_ids:
                partner.user_ids.unlink()

        return super().unlink()
	
    # API method để gán tag trực tiếp cho partner
    @api.model
    def assign_tag_to_partner(self, partner_id, tag_id):
        """API method để gán tag trực tiếp cho partner"""
        partner = self.browse(partner_id)
        if not partner.exists():
            return {'success': False, 'message': "Không tìm thấy người dùng"}
        
        # Kiểm tra tag đã tồn tại hay chưa
        existing_tag = self.env['nsp.tag'].search([
            ('tag_id', '=', tag_id)
        ])
        
        if not existing_tag:
            # Tạo tag mới và gán cho partner
            new_tag = self.env['nsp.tag'].create({
                'tag_id': tag_id,
                'status': 'active',
                'partner_id': partner.id
            })
            partner.partner_tag_id = new_tag.id
        else:
            # Nếu tag đang active thì không cho gán lại
            if existing_tag.status == 'active':
                if existing_tag.partner_id and existing_tag.partner_id != partner:
                    return {
                        'success': False, 
                        'message': f"Thẻ này đã được sử dụng."
                    }
                if existing_tag.vehicle_id:
                    return {
                        'success': False,
                        'message': f"Thẻ này đã được sử dụng."
                    }
                # Nếu tag đang active nhưng không gán cho ai, cũng không cho gán (tránh trường hợp lỗi dữ liệu)
                return {
                    'success': False,
                    'message': "Thẻ này đang ở trạng thái active nhưng không gán cho ai. Vui lòng kiểm tra lại dữ liệu."
                }
            # Nếu tag đang inactive, cho phép gán lại
            existing_tag.partner_id = partner.id
            existing_tag.vehicle_id = False
            existing_tag.status = 'active'
            partner.partner_tag_id = existing_tag.id
                
        return {'success': True, 'message': 'Tag đã được gán thành công'}

    # Lấy thẻ mới từ API và gán vào partner_tag_id
    def action_refresh_temp_tag_partner(self):
        """Lấy thẻ mới từ API và gán vào partner_tag_id"""
        for partner in self:
            # Trả về action để gọi JavaScript function
            return {
                'type': 'ir.actions.client',
                'name': _('Scan RFID'),
                'tag': 'call_rfid_reader',
                'params': {
                    'partner_id': partner.id,
                    'action': 'scan_and_assign_tag'
                }
            }

    # Thu hồi thẻ
    def action_revoke_tag(self):
        """Thu hồi thẻ"""
        for partner in self:
            tag = partner.partner_tag_id
            if tag:
                tag.write({
                    'partner_id': False,
                    'vehicle_id': False,
                    'status': 'inactive',
                })
                partner.partner_tag_id = False
                
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
    
    @api.depends('roles', 'roles.group_id')
    def _compute_groups_from_roles(self):
        for partner in self:
            groups = partner.roles.mapped('group_id')
            partner.groups = groups

    #Update role của user, bỏ hết các group mặc định
    #Chỉ assign vào group NSP để chỉ hiển thị NSP
    def assign_groups_from_roles(self):
        for partner in self:
            if partner.user_ids and not partner.user_ids.has_groups('base.group_system'):
                nsp_group = partner.roles.mapped('group_id')
                partner.user_ids.write({'groups_id': [(6, 0, nsp_group.ids)]})

    #Set role của User tạo mới mặc định là User
    def assign_default_roles(self):
        for partner in self:
            if not partner.roles: #Kiểm tra xem role User đã tạo chưa để tránh tạo duplicate
                group = self.env.ref('non_stop_parking.group_nsp_users')
                role = self.env['nsp.role'].search([('name', '=', 'User')], limit=1)
                if not role:
                    role = self.env['nsp.role'].create({
                        'name': 'User',
                        'description': "Default User access rights",
                        'group_id': [(6, 0, [group.id])]
                    })
                partner.roles = [(4, role.id)]
                partner.user_ids.write({'groups_id': [(6, 0, [group.id])]})