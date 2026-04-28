{
    'name': 'Stock Lot Report',
    'version': '16.0.1.0.0',
    'summary': 'Stock On Hand Report by Lot/Serial Number',
    'depends': ['stock', 'web'],
    'data': [
        'views/client_action.xml',
        'views/report_html_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stock_lot_report/static/src/js/stock_lot_report.js',
            'stock_lot_report/static/src/xml/stock_lot_report.xml',
        ],
    },
    'license': 'LGPL-3',
}
