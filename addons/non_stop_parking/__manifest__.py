# -*- coding: utf-8 -*-​
{
    'name': 'Non Stop Parking',
    'version': '1.0.0',
    'category': 'nsp',
    'sequence': 5,
    'summary': 'Hệ thống quản lý xe cho bãi đậu xe không cần chạm',
    'description': """
        Hệ thống quản lý xe với API toàn diện
        ================================================
        Tính năng:
        * Theo dõi và quản lý xe
        * Tích hợp thẻ RFID
        * Mối quan hệ giữa người dùng và xe
        * Hệ thống chia sẻ xe
        * Thông báo thời gian thực
        * Ghi nhật ký ảnh
        * Quản lý thiết bị đọc
        * API REST toàn diện cho các ứng dụng bên ngoài
    """,
    'author': 'Team BK-IOT-T4Tek-2025',
    'website': 'https://t4tek.co/vi',
    'depends': ["base", "web", "website", "account", "payment", "bus"],
    'installable': True,
    'auto_install': False,
    'application': True,
    'data': [
        'data/module_category.xml',

        'security/security.xml',
        'security/ir.model.access.csv',
        
        'views/tag_views.xml',
        'views/reader_views.xml',
        'views/role_views.xml',
        'views/group_views.xml',
        'views/dashboard_views.xml',
        'views/add_funds_views.xml',
        'views/fee_calculator_views.xml',
        'views/user_views.xml',
        'views/user_personal_views.xml',
        'views/vehicle_views.xml',
        'views/vehicle_logs_views.xml',
        'views/vehicle_price_views.xml',
        'views/payment_provider_views.xml',
        'views/payment_methods_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'non_stop_parking/static/src/js/**/*.js',
            'non_stop_parking/static/src/xml/**/*.xml',
        ],
    },
    'license': 'LGPL-3',
}