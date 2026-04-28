{
    'name': 'Sales Report Modern',
    'version': '16.0.1.0.0',
    'summary': 'Modern Sales Report with KPI Cards and Charts',
    'depends': ['sale', 'web'],
    'data': [
        'views/client_action.xml',
        'views/report_html_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sale_report_modern/static/src/js/sales_report_modern.js',
            'sale_report_modern/static/src/xml/sales_report_modern.xml',
        ],
    },
    'license': 'LGPL-3',
}
