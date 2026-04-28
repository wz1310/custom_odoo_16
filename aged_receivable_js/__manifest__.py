{
    'name': 'Aged Receivable Report JS',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Interactive Aged Receivable Report using JavaScript (Owl)',
    'description': """
        This module provides a modern, interactive Aged Receivable Report built with Odoo 16's JavaScript framework (Owl).
    """,
    'author': 'Antigravity',
    'depends': ['account', 'web'],
    'data': [
        'views/aged_receivable_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'aged_receivable_js/static/src/js/aged_receivable.js',
            'aged_receivable_js/static/src/xml/aged_receivable.xml',
            'aged_receivable_js/static/src/scss/aged_receivable.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
