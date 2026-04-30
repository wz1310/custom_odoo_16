{
    'name': 'Dynamic Balance Sheet Report JS',
    'version': '16.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Interactive Balance Sheet Report using JavaScript (Owl)',
    'description': """
        This module provides a modern, interactive Balance Sheet Report built with Odoo 16's JavaScript framework (Owl).
    """,
    'author': 'Odoo',
    'depends': ['base', 'account', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/balance_sheet_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dynamic_balance_sheet_report/static/src/js/balance_sheet_report.js',
            'dynamic_balance_sheet_report/static/src/xml/balance_sheet_templates.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
