# models/sync_service.py - Cho Local Server

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SyncQueue(models.Model):
    _name = 'nsp.sync.queue'
    _description = 'Sync Queue for offline data'
    _order = 'create_date desc'
    
    model_name = fields.Char('Model', required=True)
    record_id = fields.Integer('Record ID', required=True)
    action = fields.Selection([
        ('create', 'Create'),
        ('write', 'Update'),
        ('unlink', 'Delete')
    ], required=True)
    data = fields.Text('Data JSON')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('syncing', 'Syncing'),
        ('synced', 'Synced'),
        ('failed', 'Failed')
    ], default='pending')
    error_message = fields.Text('Error Message')
    retry_count = fields.Integer('Retry Count', default=0)
    

class TagSyncService(models.Model):
    _name = 'nsp.tag.sync'
    _description = 'Tag Sync Service'
    
    def _get_cloud_config(self):
        """Lấy config kết nối cloud"""
        return {
            'url': self.env['ir.config_parameter'].sudo().get_param('sync.cloud_url', 'https://your-cloud-server.com'),
            'api_key': self.env['ir.config_parameter'].sudo().get_param('sync.api_key', ''),
            'timeout': 30
        }
    
    def _call_cloud_api(self, endpoint, data):
        """Gọi API cloud server bằng urllib"""
        config = self._get_cloud_config()
        if not config['api_key']:
            raise UserError(_("Cloud API key not configured"))
        
        url = f"{config['url']}{endpoint}"
        payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'params': {**data, 'api_key': config['api_key']},
            'id': 1
        }
        
        try:
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=config['timeout']) as response:
                resp_body = response.read().decode('utf-8')
                result = json.loads(resp_body)
            
            if 'error' in result:
                raise Exception(f"API Error: {result['error']}")
                
            return result.get('result', {})
        
        except urllib.error.HTTPError as e:
            _logger.error(f"HTTP error: {e.code} {e.reason}")
            raise Exception(f"HTTP error: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            _logger.error(f"Connection error: {str(e)}")
            raise Exception(f"Connection failed: {str(e)}")
        except Exception as e:
            _logger.error(f"Unexpected error: {str(e)}")
            raise

    def sync_tag_to_cloud(self, tag_ids=None):
        """Đồng bộ tag lên cloud"""
        if not tag_ids:
            # Lấy tags chưa đồng bộ hoặc đã thay đổi trong 1 giờ qua
            domain = ['|',
                      ('last_sync_date', '=', False),
                      ('write_date', '>', fields.Datetime.now() - timedelta(hours=1))]
            tags = self.env['nsp.tag'].search(domain)
        else:
            tags = self.env['nsp.tag'].browse(tag_ids)
            
        if not tags:
            return {'success': True, 'message': 'No tags to sync'}
        
        tags_data = []
        for tag in tags:
            tags_data.append({
                'tag_id': tag.tag_id,
                'epc': tag.epc,
                'status': tag.status,
                'valid_from': tag.valid_from.isoformat() if tag.valid_from else None,
                'valid_to': tag.valid_to.isoformat() if tag.valid_to else None,
                'write_date': tag.write_date.isoformat(),
                'partner_id': tag.partner_id.id if tag.partner_id else None,
                'vehicle_id': tag.vehicle_id.id if tag.vehicle_id else None
            })
        
        try:
            result = self._call_cloud_api('/api/v1/sync/tag', {'tag': tags_data})
            if result.get('success'):
                # Cập nhật last_sync_date
                tags.sudo().write({'last_sync_date': datetime.now()})
                return {'success': True, 'data': result.get('data')}
            else:
                # Thêm vào queue để retry sau
                self._add_to_queue(tags_data)
                return {'success': False, 'message': result.get('message')}
            
        except Exception as e:
            # Lưu vào queue khi lỗi mạng
            self._add_to_queue(tags_data)
            _logger.error(f"Sync failed, added to queue: {str(e)}")
            return {'success': False, 'message': str(e)}
        
    def pull_from_cloud(self):
        """Kéo dữ liệu mới từ cloud"""
        try:
            last_sync = self.env['ir.config_parameter'].sudo().get_param('sync.last_pull_date')
            
            result = self._call_cloud_api('/api/v1/sync/tag/pull', {
                'last_sync_date': last_sync
            })
            
            if result.get('success'):
                cloud_tags = result.get('data', {}).get('tags', [])
                synced_count = 0
                
                for tag_data in cloud_tags:
                    tag_id = tag_data.get('tag_id')
                    existing_tag = self.env['nsp.tag'].search([('tag_id', '=', tag_id)], limit=1)

                    values = {
                        'tag_id': tag_data.get('tag_id'),
                        'epc': tag_data.get('epc'),
                        'status': tag_data.get('status'),
                        'valid_from': tag_data.get('valid_from'),
                        'valid_to': tag_data.get('valid_to'),
                        'sync_from_cloud': True
                    }

                    if existing_tag:
                        cloud_date = datetime.fromisoformat(tag_data.get('write_date').replace('Z', '+00:00'))
                        if cloud_date > existing_tag.write_date:
                            existing_tag.sudo().write(values)
                            synced_count += 1
                    else:
                        self.env['nsp.tag'].sudo().create(values)
                        synced_count += 1

                # Cập nhật thời gian pull cuối
                self.env['ir.config_parameter'].sudo().set_param('sync.last_pull_date', datetime.now().isoformat())

                return {'success': True, 'synced_count': synced_count}

        except Exception as e:
            _logger.error(f"Pull from cloud failed: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _add_to_queue(self, tags_data):
        """Thêm dữ liệu vào queue khi offline"""
        for tag_data in tags_data:
            self.env['nsp.sync.queue'].sudo().create({
                'model_name': 'nsp.tag',
                'record_id': 0,  # Sẽ cập nhật sau
                'action': 'create',
                'data': json.dumps(tag_data),
                'status': 'pending'
            })
    
    def process_sync_queue(self):
        """Xử lý queue khi có mạng trở lại"""
        pending_items = self.env['nsp.sync.queue'].search([
            ('status', '=', 'pending'),
            ('retry_count', '<', 3)
        ], limit=50)
        
        for item in pending_items:
            try:
                item.status = 'syncing'
                data = json.loads(item.data)
                
                result = self._call_cloud_api('/api/v1/sync/tag', {'tags': [data]})
                
                if result.get('success'):
                    item.status = 'synced'
                else:
                    item.retry_count += 1
                    item.status = 'failed' if item.retry_count >= 3 else 'pending'
                    item.error_message = result.get('message')
                    
            except Exception as e:
                item.retry_count += 1
                item.status = 'failed' if item.retry_count >= 3 else 'pending'
                item.error_message = str(e)
        
        return len(pending_items)