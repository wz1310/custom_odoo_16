{
    'name': 'Sales Analytics Dashboard (Fixed)',
    'version': '16.0.2.0.1',
    'summary': 'Advanced Sales Analytics with Interactive Charts & AI Insights',
    'description': """
        # Sales Analytics Dashboard
        
        Modul analitik penjualan modern dengan fitur-fitur canggih:
        - Dashboard interaktif dengan chart real-time
        - KPI Cards dengan animasi
        - Segmentasi data berbasis AI
        - Export data lanjutan (Excel, PDF)
        - Filter dinamis multi-dimensi
        - Dark/Light mode support
        - Mobile responsive
    """,
    'category': 'Sales',
    'author': 'Odoo Advanced Analytics',
    'website': 'https://www.odoo.com',
    'license': 'LGPL-3',
    'depends': ['sale', 'web', 'account', 'product'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/sales_analytics_menu.xml',
        'views/sales_analytics_templates.xml',
        'report/sales_analytics_reports.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sales_analytics_dashboard/static/src/scss/sales_analytics.scss',
            'sales_analytics_dashboard/static/src/js/sales_chart_component.js',
            'sales_analytics_dashboard/static/src/js/sales_kpi_component.js',
            'sales_analytics_dashboard/static/src/js/sales_table_component.js',
            'sales_analytics_dashboard/static/src/js/sales_analytics_dashboard.js',
            'sales_analytics_dashboard/static/src/xml/sales_analytics_templates.xml',
        ],
        'web.assets_frontend': [
            'sales_analytics_dashboard/static/src/scss/sales_analytics_frontend.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': [
        'static/description/icon.png',
        'static/description/banner.png',
    ],
    'price': 0,
    'currency': 'USD',
}