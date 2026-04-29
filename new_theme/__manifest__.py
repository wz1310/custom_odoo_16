{
    'name': 'New Theme',
    'version': '1.0',
    'category': 'Themes/Backend',
    'summary': 'Custom Modern Theme for Odoo 16',
    'description': """
        This module changes the primary colors of Odoo 16 to a modern and premium look.
    """,
    'author': 'Odoo Community',
    'depends': ['web', 'base_setup', 'web_responsive'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'new_theme/static/src/scss/colors.scss',
            'new_theme/static/src/xml/apps_menu.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
