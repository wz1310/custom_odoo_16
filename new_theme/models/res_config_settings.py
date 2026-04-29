# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    theme_primary_color = fields.Char(
        string="Theme Primary Color",
        config_parameter='new_theme.primary_color',
        default='#875A7B'
    )
    
    theme_navbar_color = fields.Char(
        string="Navbar Background Color",
        config_parameter='new_theme.navbar_color',
        default='#714B67'
    )

    theme_menu_style = fields.Selection([
        ('default', 'Default Odoo Menu'),
        ('fullscreen_rolling', 'Fullscreen Rolling Menu')
    ], string="Menu Style", config_parameter='new_theme.menu_style', default='default')

    theme_navbar_autohide = fields.Boolean(
        string="Auto-hide Navbar",
        config_parameter='new_theme.navbar_autohide',
        default=False
    )

    def action_reset_theme(self):
        """ Reset theme colors to Odoo 16 Enterprise default values """
        self.env['ir.config_parameter'].sudo().set_param('new_theme.primary_color', '#875A7B')
        self.env['ir.config_parameter'].sudo().set_param('new_theme.navbar_color', '#714B67')
        self.env['ir.config_parameter'].sudo().set_param('new_theme.menu_style', 'default')
        self.env['ir.config_parameter'].sudo().set_param('new_theme.navbar_autohide', False)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
