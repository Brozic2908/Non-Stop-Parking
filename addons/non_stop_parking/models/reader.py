# # -*- coding: utf-8 -*-
# # Part of Odoo. See LICENSE file for full copyright and licensing details.

import socket
import time
import json
import logging
import datetime
import urllib.parse as uparse
import urllib.request as ureq
import urllib.error as uerr
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class NSPReader(models.Model):
    _name = "nsp.reader"
    _description = "Thiết bị"
    _order = "name"
    _rec_name = "name"
    _CHECK_URL = "/status"

    # Basic fields
    reader_id = fields.Char(string="Mã thiết bị", help="Mã định danh thiết bị đọc")
    name = fields.Char(string="Tên thiết bị", help="Tên thiết bị đọc thẻ")
    ip_address = fields.Char(string="Địa chỉ IP", help="Địa chỉ IP của thiết bị")
    port = fields.Integer(string="Cổng mạng", help="Cổng mạng TCP/UDP của thiết bị")
    com_port = fields.Char(string="Cổng COM", help="Cổng nối tiếp của thiết bị (ví dụ: COM1, COM2)")
    location = fields.Char(string="Vị trí", help="Vị trí của thiết bị")
    
    # Reader configuration
    type = fields.Selection([
        ('entry', 'Cổng vào'),
        ('exit', 'Cổng ra'),
        ('both', 'Cổng vào và ra')
    ], string="Loại thiết bị", required=True, default='both', help="Loại thiết bị đọc")
    
    status = fields.Selection([
        ('active', 'Hoạt động'),
        ('inactive', 'Không hoạt động'),
        ('maintenance', 'Bảo trì'),
        ('error', 'Lỗi')
    ])
    
    # Thông tin kết nối
    is_connected = fields.Boolean(string="Đã kết nối", default=False, readonly=True)
    installed_at = fields.Datetime(string="Ngày lắp đặt", help="Ngày lắp đặt thiết bị")
    last_checked = fields.Datetime(string="Lần kiểm tra gần nhất", help="Thời gian kiểm tra gần nhất")

    # Technical fields
    end_point = fields.Char(string="End point")
    auto_discovered = fields.Boolean(string="Tự động phát hiện", default=False)
    
    # Relations
    vehicle_logs_ids = fields.One2many('nsp.vehicle.logs', 'reader_device', string="Lịch sử ra vào")
        
    # SQL Constraints
    _sql_constraints = [
        ('reader_id_unique', 'UNIQUE(reader_id)', 'Reader ID phải là duy nhất'),
        ('port_unique', 'UNIQUE(port)', 'Cổng phải là duy nhất'),
    ]
    
    @api.constrains('reader_id')
    def _check_reader_id_unique(self):
        """Kiểm tra Reader ID phải là duy nhất"""
        for record in self:
            if record.reader_id:
                existing = self.search([
                    ('reader_id', '=', record.reader_id),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(_("Reader ID '%s' đã tồn tại") % record.reader_id)

    @api.constrains('ip_address')
    def _check_ip_address_unique(self):
        for record in self:
            if record.ip_address:
                existing = self.search([
                    ('ip_address', '=', record.ip_address),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(_("Địa chỉ IP '%s' đã tồn tại") % record.ip_address)

    @api.constrains('port')
    def _check_port_unique(self):
        for record in self:
            if record.port:
                existing = self.search([
                    ('port', '=', record.port),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(_("Cổng '%s' đã tồn tại") % record.port)

    @api.model        
    def create(self, vals):
        """Override create to validate IP and port"""
        if vals.get('ip_address') and vals.get('port'):
            self._validate_ip_port(vals['ip_address'], vals['port'])
        return super().create(vals)
        
    def write(self, vals):
        """Override write to validate IP and port"""
        if vals.get('ip_address') or vals.get('port'):
            for record in self:
                ip = vals.get('ip_address', record.ip_address)
                port = vals.get('port', record.port)
                is_connected = vals.get('is_connected', record.is_connected)
                self._validate_ip_port(ip, port)
        return super().write(vals)

    def _validate_ip_port(self, ip, port):
        """Validate IP address format and port range"""
        import re
        ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)?'

        if not re.match(ip_pattern, ip):
            raise ValidationError(_("IP Address không hợp lệ: %s") % ip)
        
        if not (1 <= int(port) <= 65535):
            raise ValidationError(_("Port phải trong khoảng 1-65535"))

    def _http_get_request(self, url, timeout = 5):
        """Make HTTP GET request using urllib"""
        try:
            request = ureq.Request(url)
            request.add_header('User-Agent', 'Odoo-Reader-Client/1.0')
            request.add_header('Accept', 'application/json')
            
            with ureq.urlopen(request, timeout=timeout) as response:
                if response.getcode() == 200:
                    data = response.read().decode('utf-8')
                    return json.loads(data)
                else:
                    _logger.warning(f"HTTP request returned status code: {response.getcode()}")
                    return None

        except uerr.HTTPError as e:
            _logger.error(f"HTTP Error: {e.code} - {e.reason}")
            return None
        except uerr.URLError as e:
            _logger.error(f"URL Error: {e.reason}")
            return None
        except socket.timeout:
            _logger.error("Request timeout")
            return None
        except json.JSONDecodeError as e:
            _logger.error(f"JSON decode error: {str(e)}")
            return None
        except Exception as e:
            _logger.error(f"Unexpected error: {str(e)}")
            return None            

    def _http_post_request(self, url, data=None, timeout=5):
        """Make HTTP POST request using urllib"""
        try:
            post_data = None
            if data:
                post_data = json.dumps(data).encode('utf-8')
            
            request = ureq.Request(url, data=post_data)
            request.add_header('User-Agent', 'Odoo-Reader-Client/1.0')
            request.add_header('Content-Type', 'application/json')
            request.add_header('Accept', 'application/json')
            
            with ureq.urlopen(request, timeout=timeout) as response:
                if response.getcode() == 200:
                    response_data = response.read().decode('utf-8')
                    return json.loads(response_data)
                else:
                    _logger.warning(f"HTTP POST request returned status code: {response.getcode()}")
                    return None
                    
        except uerr.HTTPError as e:
            _logger.error(f"HTTP Error: {e.code} - {e.reason}")
            return None
        except uerr.URLError as e:
            _logger.error(f"URL Error: {e.reason}")
            return None
        except socket.timeout:
            _logger.error("Request timeout")
            return None
        except json.JSONDecodeError as e:
            _logger.error(f"JSON decode error: {str(e)}")
            return None
        except Exception as e:
            _logger.error(f"Unexpected error: {str(e)}")
            return None
    
    def _check_connection_socket(self):
        """Check basic connection using socket"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Thời gian kết nối giới hạn 5 giây
            sock.settimeout(5)
            # Nếu không có lỗi thì trả về result = 0
            result = sock.connect_ex((self.ip_address, self.port))
            sock.close()
            return result == 0
        except Exception as e:
            _logger.error(f"Socket connection error: {str(e)}")
            return False
        
    # Kiểm tra trạng thái reader thông qua API
    def _check_reader_status(self):
        """Kiểm tra trạng thái thông qua API"""
        url = f"http://{self.ip_address}:{self.port}{self._CHECK_URL}"
        return self._http_get_request(url, timeout=5)

    # action test kết nối đến thiết bị
    def action_check_status(self):
        """Manual check reader status"""
        for reader in self:
            try:
                # First check basic connection
                if not reader._check_connection_socket():
                    reader.write({
                        'status': 'error',
                        'is_connected': False,
                        'last_checked': fields.Datetime.now(),
                    })
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _("Kết nối thất bại"),
                            'message': _("Không thể kết nối với reader %s") % reader.name,
                            'type': 'warning',
                        }
                    }
                
                # Then check reader status via API
                status_info = reader._check_reader_status()
                if status_info:
                    reader.write({
                        'status': 'active',
                        'is_connected': True,
                        'last_checked': fields.Datetime.now(),
                    })
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Kết nối thành công'),
                            'message': _('%s đang hoạt động bình thường') % reader.name,
                            'type': 'success',
                        }
                    }
                else:
                    reader.write({
                        'status': 'error',
                        'is_connected': False,
                        'last_checked': fields.Datetime.now(),
                    })
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _("Kết nối thất bại"),
                            'message': _('Reader %s không phản hồi đúng API') % reader.name,
                            'type': 'warning',
                        }
                    }
                 
            except Exception as e:
                _logger.error(f"Error checking reader {reader.name}: {str(e)}")
                reader.write({
                    'status': 'error',
                    'is_connected': False,
                    'last_checked': fields.Datetime.now()
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Lỗi kết nối'),
                        'message': _('Lỗi khi kiểm tra reader %s: %s') % (reader.name, str(e)),
                        'type': 'danger',
                    }
                }

    # FIX Kiểm tra phàn hồi bằng Broadcast UDP
    @api.model
    def discover_readers(self):
        """Discover readers - Docker-optimized version"""
        discovered_readers = []
        
        # Method 1: Try UDP broadcast with host network gateway
        _logger.info("Starting UDP broadcast discovery...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(5)
            
            broadcast_message = json.dumps({'action': 'DISCOVERY_REQUEST'}).encode('utf-8')
            
            # Try broadcast to Docker host network
            # Docker container IP: 172.20.0.3, so host network is likely 192.168.x.x
            broadcast_addresses = [
                '192.168.1.222',   # Most likely host network
                '192.168.1.255',   # Most likely host network
                # '172.30.200.230',   # Most likely host network
                '192.168.0.255',   # Alternative host network
                '255.255.255.255', # Global broadcast
            ]
            
            for addr in broadcast_addresses:
                try:
                    sock.sendto(broadcast_message, (addr, 9999))
                    _logger.info(f"Sent broadcast to {addr}")
                except Exception as e:
                    _logger.debug(f"Failed to send broadcast to {addr}: {str(e)}")
            
            # Listen for responses
            start_time = time.time()
            while time.time() - start_time < 5:
                try:
                    data, addr = sock.recvfrom(1024)
                    response = json.loads(data.decode())

                    if response.get('message') == 'DISCOVER_RESPONSE':
                        reader_info = {
                            'name': response.get('reader_name', f'Reader_{addr[0]}_{response.get("port")}'),
                            'ip_address': addr[0],
                            'reader_id': response.get('id'),
                            'type': response.get('type'),
                            'port': response.get('port'),
                        }
                        discovered_readers.append(reader_info)
                        _logger.info(f"UDP discovered: {reader_info}")

                except socket.timeout:
                    continue
                except Exception as e:
                    continue
            
            sock.close()
            
        except Exception as e:
            _logger.error(f"UDP broadcast failed: {str(e)}")
        
        # Method 2: Direct IP scanning (since we know reader exists at 192.168.1.222)
        if not discovered_readers:
            _logger.info("UDP broadcast found nothing, trying direct IP scanning...")
            
            # Known IP ranges to scan
            ip_ranges = [
                ('192.168.1.{}', range(220, 230)),  # Focus on known range first
                ('192.168.1.{}', range(1, 255)),    # Then full range
                ('192.168.0.{}', range(1, 255)),    # Alternative range
            ]
            
            # Common ports for readers
            ports_to_scan = [8080, 8081, 8082, 8083, 8084, 8085]
            
            for ip_pattern, ip_range in ip_ranges:
                _logger.info(f"Scanning IP pattern: {ip_pattern}")
                
                for i in ip_range:
                    if len(discovered_readers) >= 10:  # Limit to avoid too many scans
                        break
                        
                    ip = ip_pattern.format(i)
                    
                    for port in ports_to_scan:
                        try:
                            # Quick TCP connection test
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(0.5)
                            result = sock.connect_ex((ip, port))
                            sock.close()
                            
                            if result == 0:  # Connection successful
                                _logger.info(f"Found open port: {ip}:{port}")
                                
                                # Test HTTP endpoint
                                try:
                                    url = f"http://{ip}:{port}/status"
                                    response = self._http_get_request(url, timeout=2)
                                    
                                    if response and response.get('status') == 'ok':
                                        reader_info = {
                                            'name': response.get('name', f'Reader_{ip}_{port}'),
                                            'ip_address': ip,
                                            'reader_id': response.get('id'),
                                            'type': response.get('type', 'both'),
                                            'port': port,
                                        }
                                        discovered_readers.append(reader_info)
                                        _logger.info(f"HTTP discovered: {reader_info}")
                                        
                                except Exception as e:
                                    _logger.debug(f"HTTP test failed for {ip}:{port} - {str(e)}")
                                    
                        except Exception as e:
                            continue  # Skip this IP:port combination
                
                if discovered_readers:  # Found some readers, no need to scan other ranges
                    break
        
        _logger.info(f"Discovery completed. Found {len(discovered_readers)} readers")
        return discovered_readers

    # FIX
    def action_discover_and_register(self):
        """Discover and register new readers"""
        _logger.info("Starting reader discovery...")
        discovered_readers = self.discover_readers()
        _logger.info(f"Discovery result: {len(discovered_readers)} readers found")
        
        new_readers = []
        updated_readers = []
        
        for reader_info in discovered_readers:
            _logger.info(f"Processing reader: {reader_info}")
            
            # Check if reader already exists by multiple criteria
            existing_reader = None
            
            # Check by IP:port first
            if reader_info.get('ip_address') and reader_info.get('port'):
                existing_reader = self.search([
                    ('ip_address', '=', reader_info['ip_address']),
                    ('port', '=', reader_info['port'])
                ], limit=1)
            
            # Check by reader_id if not found by IP:port
            if not existing_reader and reader_info.get('reader_id'):
                existing_reader = self.search([
                    ('reader_id', '=', reader_info['reader_id'])
                ], limit=1)
            
            if not existing_reader:
                # Create new reader
                try:
                    # Validate required fields
                    if not reader_info.get('ip_address') or not reader_info.get('port'):
                        _logger.warning(f"Skipping reader due to missing IP/port: {reader_info}")
                        continue
                    
                    # Test connection before creating
                    temp_reader = self.new({
                        'ip_address': reader_info['ip_address'],
                        'port': reader_info['port']
                    })
                    
                    if temp_reader._check_connection_socket():
                        status_info = temp_reader._check_reader_status()
                        
                        if status_info:
                            reader_vals = {
                                'name': reader_info.get('name', f'Reader_{reader_info["ip_address"]}_{reader_info["port"]}'),
                                'reader_id': reader_info.get('reader_id', f'reader_{int(time.time())}'),
                                'ip_address': reader_info['ip_address'],
                                'port': reader_info['port'],
                                'type': reader_info.get('type', 'both'),
                                'status': 'active',
                                'is_connected': True,
                                'auto_discovered': True,
                                'installed_at': fields.Datetime.now(),
                                'last_checked': fields.Datetime.now(),
                            }

                            new_reader = self.create(reader_vals)
                            new_readers.append(new_reader)
                            _logger.info(f"Created new reader: {new_reader.name}")
                        else:
                            _logger.warning(f"Reader {reader_info['ip_address']}:{reader_info['port']} không phản hồi API")
                    else:
                        _logger.warning(f"Không thể kết nối socket tới {reader_info['ip_address']}:{reader_info['port']}")
                        
                except Exception as e:
                    _logger.error(f"Error creating reader {reader_info.get('name', 'Unknown')}: {str(e)}")
                    import traceback
                    _logger.error(f"Traceback: {traceback.format_exc()}")

            else:
                # Update existing reader
                _logger.info(f"Updating existing reader: {existing_reader.name}")
                try:
                    if existing_reader._check_connection_socket():
                        status_info = existing_reader._check_reader_status()
                        if status_info:
                            existing_reader.write({
                                'status': 'active',
                                'is_connected': True,
                                'last_checked': fields.Datetime.now(),
                            })
                            updated_readers.append(existing_reader)
                        else:
                            existing_reader.write({
                                'status': 'error',
                                'is_connected': False,
                                'last_checked': fields.Datetime.now(),
                            })
                    else:
                        existing_reader.write({
                            'status': 'error',
                            'is_connected': False,
                            'last_checked': fields.Datetime.now()
                        })
                except Exception as e:
                    _logger.error(f"Error updating reader {existing_reader.name}: {str(e)}")
        
        # Return detailed notification
        if new_readers:
            new_names = [r.name for r in new_readers]
            message = _("Phát hiện và đăng ký thành công %d reader mới:\n%s") % (len(new_readers), '\n'.join(new_names))
            notification_type = 'success'
        elif updated_readers:
            updated_names = [r.name for r in updated_readers]
            message = _("Cập nhật trạng thái %d reader:\n%s") % (len(updated_readers), '\n'.join(updated_names))
            notification_type = 'info'
        else:
            message = _("Không tìm thấy reader mới. Tổng số reader đã phát hiện: %d") % len(discovered_readers)
            notification_type = 'warning'
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Phát hiện thiết bị"),
                'message': message,
                'type': notification_type,
                'sticky': True,
            }
        }
    
    # TODO Cron job kiểm tra trạng thái thiết bị
    # @api.model
    # def _cron_check_readers_status(self):
    #     """Cron job to check all readers status"""
    #     readers = self.search([('status', 'in', ['active', 'error'])])

    #     for reader in readers:
    #         try:
    #             if reader._check_connection_socket():
    #                 status_info = reader._check_reader_status()
    #                 if status_info:
    #                     reader.write({
    #                         'status': 'active',
    #                         'last_checked': fields.Datetime.now(),
    #                     })
    #                 else:
    #                     reader.write({
    #                         'status': 'error',
    #                         'last_checked': fields.Datetime.now(),
    #                     })
    #         except Exception as e:
    #             _logger.error(f"Error checking reader {reader.name} in cron: {str(e)}")
    #             reader.write({
    #                 'status': 'error',
    #                 'last_checked': fields.Datetime.now(),
    #             })
    
    # # Công việc Cron để định kỳ khám phá những người đọc mới
    # @api.model
    # def _cron_discover_readers(self):
        """Cron job to periodically discover new readers"""
        self.action_discover_and_register()

    # Ghi đè hủy liên kết để kiểm tra người đọc đang hoạt động
    def unlink(self):
        """Override unlink to check for active readers"""
        for reader in self:
            if reader.status == 'active':
                raise ValidationError(_("Không thể xóa reader đang hoạt động. Vui lòng tắt reader trước khi xóa."))
        return super().unlink()
    
    # Nhận số liệu thống kê người đọc cho dashboard
    @api.model
    def get_reader_statistics(self):
        """Get reader statistics for dashboard"""
        total_readers = self.search_count([])
        active_readers = self.search_count([('status', '=', 'active')])
        error_readers = self.search_count([('status', '=', 'error')])
        auto_discovered = self.search_count([('auto_discovered', '=', True)])
        
        return {
            'total_readers': total_readers,
            'active_readers': active_readers,
            'error_readers': error_readers,
            'auto_discovered': auto_discovered,
        }

    @api.model
    def test_network_connectivity(self):
        """Test network connectivity and UDP broadcast capability"""
        results = []
        
        # Test 1: Check if we can create UDP socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            msg = json.dumps({'action': 'discover'}).encode('utf-8')
            
            sock.sendto(msg, ('255.255.255.255', 9999))
            sock.settimeout(5)

            start_time = time.time()
            discovered = []

            _logger.info("🔍 Đang quét thiết bị trong 5 giây...\n")

            while time.time() - start_time < 5:
                try:
                    data, addr = sock.recvfrom(1024)
                    decoded = data.decode('utf-8')
                    _logger.info(f"✅ Phát hiện: {decoded}, từ, {addr}")
                    _logger.info(f"✅ từ, {addr}")

                    # Optional: tránh trùng IP
                    if addr[0] not in [d[0] for d in discovered]:
                        discovered.append(addr)

                except socket.timeout:
                    continue
                except Exception as e:
                    _logger.error("❌ Lỗi:", e)
                    break

            if not discovered:
                _logger.warning("⚠️ Không phát hiện thiết bị nào.")
            _logger.warning(f"Kết thúc tìm kiếm")

            results.append("✅ UDP socket creation: SUCCESS")
            sock.close()
        except Exception as e:
            results.append(f"❌ UDP socket creation: FAILED - {str(e)}")
            return results
        
        # # Test 2: Check local IP
        # try:
        #     hostname = socket.gethostname()
        #     local_ip = socket.gethostbyname(hostname)
        #     results.append(f"✅ Local IP: {local_ip}")
        # except Exception as e:
        #     results.append(f"❌ Local IP detection: FAILED - {str(e)}")
        
        # # Test 3: Test UDP broadcast
        # try:
        #     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #     sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        #     sock.settimeout(2)
            
        #     test_message = json.dumps({'action': 'test'}).encode('utf-8')
            
        #     # Test different broadcast addresses
        #     broadcast_addresses = [
        #         '255.255.255.255',
        #         '192.168.1.255',
        #         '192.168.1.222',
        #         '192.168.0.255',
        #         '10.0.0.255'
        #     ]

        #     for addr in broadcast_addresses:
        #         try:
        #             sock.sendto(test_message, (addr, 9999))
        #             results.append(f"✅ Broadcast to {addr}: SUCCESS")
        #         except Exception as e:
        #             results.append(f"❌ Broadcast to {addr}: FAILED - {str(e)}")
            
        #     sock.close()
        # except Exception as e:
        #     results.append(f"❌ UDP broadcast test: FAILED - {str(e)}")
        
        # # Test 4: Test direct connection to known reader
        # try:
        #     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #     sock.settimeout(3)
        #     result = sock.connect_ex(('192.168.1.222', 8080))
        #     if result == 0:
        #         results.append("✅ Direct connection to 192.168.1.222:8080: SUCCESS")
        #     else:
        #         results.append(f"❌ Direct connection to 192.168.1.222:8080: FAILED - {result}")
        #     sock.close()
        # except Exception as e:
        #     results.append(f"❌ Direct connection test: FAILED - {str(e)}")
        
        # Log results
        for result in results:
            _logger.info(result)
        
        return results

    # Action để test từ UI
    def action_test_network(self):
        """Action to test network connectivity from UI"""
        results = self.test_network_connectivity()
        
        message = ";".join(results)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Network Test Results"),
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }