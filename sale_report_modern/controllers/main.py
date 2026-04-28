from odoo import http
from odoo.http import request
from datetime import date, datetime
import io
import json

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class SalesReportModernController(http.Controller):

    def _get_domain(self, date_from=None, date_to=None, customer_ids=None):
        domain = [('state', 'in', ['sale', 'done'])]
        if date_from:
            domain.append(('date_order', '>=', date_from))
        if date_to:
            domain.append(('date_order', '<=', date_to))
        if customer_ids:
            domain.append(('partner_id', 'in', customer_ids))
        return domain

    def _format_indo(self, date_val):
        if not date_val:
            return ''
        if isinstance(date_val, str):
            try:
                date_val = datetime.strptime(date_val, '%Y-%m-%d').date()
            except Exception:
                return date_val
        months = {
            1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
            5: 'Mei', 6: 'Jun', 7: 'Jul', 8: 'Agu',
            9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Des'
        }
        return f"{date_val.day} {months[date_val.month]} {date_val.year}"

    def _get_val(self, order, line, key):
        if key == 'customer':
            return order.partner_id.name or 'Unknown Customer'
        if key == 'order':
            return order.name
        if key == 'product':
            return line.product_id.display_name or 'Unknown Product'
        if key == 'salesperson':
            return order.user_id.name or 'Unknown'
        return 'Other'

    def _build_tree(self, orders, groupby):
        report_data = {}
        all_lines = []
        total_revenue = 0.0
        total_qty = 0.0
        customer_set = set()
        order_set = set()

        for order in orders:
            customer_set.add(order.partner_id.id)
            order_set.add(order.id)
            for line in order.order_line:
                total_revenue += line.price_subtotal
                total_qty += line.product_uom_qty
                line_info = {
                    'order_id': order.id,
                    'ref': order.name,
                    'product': line.product_id.display_name or '',
                    'salesperson': order.user_id.name or '',
                    'qty': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'subtotal': line.price_subtotal,
                    'date_order': order.date_order.strftime('%d/%m/%Y') if order.date_order else '',
                    'customer': order.partner_id.name or '',
                }
                all_lines.append(line_info)

                if groupby:
                    active_keys = [self._get_val(order, line, k) for k in groupby]
                    current_level = report_data
                    for i, key in enumerate(active_keys):
                        if key not in current_level:
                            current_level[key] = {'total': 0.0, 'qty': 0.0, 'children': {}, 'lines': []}
                        current_level[key]['total'] += line.price_subtotal
                        current_level[key]['qty'] += line.product_uom_qty
                        if i == len(active_keys) - 1:
                            current_level[key]['lines'].append(line_info)
                        else:
                            current_level = current_level[key]['children']

        kpi = {
            'total_revenue': total_revenue,
            'total_orders': len(order_set),
            'total_customers': len(customer_set),
            'total_qty': total_qty,
        }
        return report_data, all_lines, kpi

    @http.route('/sale_report_modern/data', type='json', auth='user')
    def get_report_data(self, groupby=None, date_from=None, date_to=None, **kw):
        if groupby is None:
            groupby = ['customer']

        domain = self._get_domain(date_from, date_to, kw.get('customer_ids'))
        orders = request.env['sale.order'].sudo().search(domain, order='date_order desc')
        report_data, all_lines, kpi = self._build_tree(orders, groupby)

        if date_from and date_to:
            periode_label = f"{self._format_indo(date_from)} - {self._format_indo(date_to)}"
        elif date_from:
            periode_label = f"Mulai {self._format_indo(date_from)}"
        elif date_to:
            periode_label = f"Hingga {self._format_indo(date_to)}"
        else:
            periode_label = f"Semua Periode"

        # Top 5 customers by revenue for chart
        customer_totals = {}
        for line in all_lines:
            c = line['customer']
            customer_totals[c] = customer_totals.get(c, 0) + line['subtotal']
        top_customers = sorted(customer_totals.items(), key=lambda x: x[1], reverse=True)[:5]

        return request.env['ir.ui.view']._render_template(
            'sale_report_modern.report_modern_html', {
                'report_data': report_data,
                'all_lines': all_lines,
                'active_groups': groupby,
                'date_from': date_from or '',
                'date_to': date_to or '',
                'periode_label': periode_label,
                'kpi': kpi,
                'top_customers': top_customers,
                'base_url': request.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            }
        )

    @http.route('/sale_report_modern/export_excel', type='http', auth='user')
    def export_excel(self, groupby=None, date_from=None, date_to=None, **kw):
        groupby = json.loads(groupby) if groupby else []
        domain = self._get_domain(date_from, date_to)
        orders = request.env['sale.order'].sudo().search(domain, order='date_order desc')
        _, all_lines, kpi = self._build_tree(orders, [])

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Sales Report')

        # Formats
        title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#1e293b'})
        head_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#6366f1', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        normal_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1})
        total_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#f1f5f9', 'border': 1,
            'num_format': '#,##0.00'
        })

        sheet.write(0, 0, 'Sales Report Modern', title_fmt)
        sheet.write(1, 0, f'Periode: {date_from or "-"} s/d {date_to or "-"}')
        sheet.write(2, 0, f'Total Revenue: {kpi["total_revenue"]:,.2f}')
        sheet.write(3, 0, f'Total Orders: {kpi["total_orders"]}')

        headers = ['No', 'Reference', 'Date', 'Customer', 'Product', 'Salesperson', 'Qty', 'Unit Price', 'Subtotal']
        for col, h in enumerate(headers):
            sheet.write(5, col, h, head_fmt)

        for i, line in enumerate(all_lines):
            r = 6 + i
            sheet.write(r, 0, i + 1, normal_fmt)
            sheet.write(r, 1, line['ref'], normal_fmt)
            sheet.write(r, 2, line['date_order'], date_fmt)
            sheet.write(r, 3, line['customer'], normal_fmt)
            sheet.write(r, 4, line['product'], normal_fmt)
            sheet.write(r, 5, line['salesperson'], normal_fmt)
            sheet.write(r, 6, line['qty'], normal_fmt)
            sheet.write(r, 7, line['price_unit'], money_fmt)
            sheet.write(r, 8, line['subtotal'], money_fmt)

        # Total row
        total_row = 6 + len(all_lines)
        sheet.write(total_row, 7, 'TOTAL', total_fmt)
        sheet.write(total_row, 8, kpi['total_revenue'], total_fmt)

        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 18)
        sheet.set_column(2, 2, 14)
        sheet.set_column(3, 3, 30)
        sheet.set_column(4, 4, 40)
        sheet.set_column(5, 5, 20)
        sheet.set_column(6, 6, 8)
        sheet.set_column(7, 8, 16)

        workbook.close()
        output.seek(0)
        file_name = f"Sales_Modern_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return request.make_response(output.read(), [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename={file_name}')
        ])
