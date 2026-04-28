from odoo import http
from odoo.http import request
from collections import defaultdict
from datetime import date, datetime
import io
import json

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

class SalesIntelligenceController(http.Controller):


    @http.route('/sales_report/export_excel', type='http', auth='user')
    def export_excel(self, groupby=None, date_from=None, date_to=None, **kw):
        # 1. Parsing Params
        groupby = json.loads(groupby) if groupby else []
        domain = [('state', 'in', ['sale', 'done'])]
        if date_from: domain.append(('date_order', '>=', date_from))
        if date_to: domain.append(('date_order', '<=', date_to))
        
        orders = request.env['sale.order'].sudo().search(domain, order='date_order desc')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Sales Report')
        
        # --- STYLES ---
        head_fmt = workbook.add_format({'bold': True, 'bg_color': '#1e3a8a', 'color': 'white', 'border': 1})
        group_fmt = workbook.add_format({'bold': True, 'bg_color': '#f1f5f9', 'border': 1})
        number_group_fmt = workbook.add_format({'bold': True, 'bg_color': '#f1f5f9', 'border': 1, 'num_format': '#,##0'})
        normal_fmt = workbook.add_format({'border': 1})
        money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1})

        headers = ['Reference / Grouping', 'Date', 'Product', 'Salesperson', 'Qty', 'Price Unit', 'Subtotal']
        for col, title in enumerate(headers):
            sheet.write(0, col, title, head_fmt)

        # --- PERBAIKAN FUNGSI GET_VAL ---
        def get_val(order, line, key):
            if key == 'customer': 
                return order.partner_id.name or 'Unknown Customer'
            if key == 'salesperson': 
                return order.user_id.name or 'Unknown Salesperson'
            if key == 'product': 
                return line.product_id.name or 'Unknown Product'
            if key == 'order_id' or key == 'order': # Tambahkan penanganan Order
                return order.name or 'Unknown Order'
            return str(key).capitalize() # Fallback ke nama key jika tidak terdaftar

        # 2. Replikasi Logic Hirarki
        report_data = {}
        for order in orders:
            for line in order.order_line:
                active_keys = [get_val(order, line, k) for k in groupby]
                current_level = report_data
                for i, key in enumerate(active_keys):
                    if key not in current_level:
                        current_level[key] = {'total': 0.0, 'children': {}, 'lines': []}
                    
                    current_level[key]['total'] += line.price_subtotal
                    
                    if i == len(active_keys) - 1:
                        current_level[key]['lines'].append({
                            'ref': order.name,
                            'date': order.date_order,
                            'product': line.product_id.name,
                            'sp': order.user_id.name,
                            'qty': line.product_uom_qty,
                            'price_unit': line.price_unit,
                            'sub': line.price_subtotal
                        })
                    else:
                        current_level = current_level[key]['children']

        # 3. Penulisan ke Excel (Recursive)
        self.row_num = 1
        def write_level(nodes, level=0):
            # Sortir keys agar urutan rapi
            for key in sorted(nodes.keys()):
                indent = "    " * level
                sheet.write(self.row_num, 0, f"{indent}▾ {key}", group_fmt)
                sheet.write(self.row_num, 1, "", group_fmt)
                sheet.write(self.row_num, 2, "", group_fmt)
                sheet.write(self.row_num, 3, "", group_fmt)
                sheet.write(self.row_num, 4, "", group_fmt)
                sheet.write(self.row_num, 5, "", group_fmt)
                sheet.write(self.row_num, 6, nodes[key]['total'], number_group_fmt)
                self.row_num += 1
                
                if nodes[key]['children']:
                    write_level(nodes[key]['children'], level + 1)
                
                if nodes[key]['lines']:
                    for l in nodes[key]['lines']:
                        indent_detail = "    " * (level + 1)
                        sheet.write(self.row_num, 0, f"{indent_detail}{l['ref']}", normal_fmt)
                        sheet.write(self.row_num, 1, l['date'].strftime('%d/%m/%Y') if l['date'] else '', date_fmt)
                        sheet.write(self.row_num, 2, l['product'], normal_fmt)
                        sheet.write(self.row_num, 3, l['sp'], normal_fmt)
                        sheet.write(self.row_num, 4, l['qty'], normal_fmt)
                        sheet.write(self.row_num, 5, l['price_unit'], money_fmt)
                        sheet.write(self.row_num, 6, l['sub'], money_fmt)
                        self.row_num += 1

        if groupby:
            write_level(report_data)
        else:
            # Mode Flat List
            for order in orders:
                for line in order.order_line:
                    sheet.write(self.row_num, 0, order.name, normal_fmt)
                    sheet.write(self.row_num, 1, order.date_order.strftime('%d/%m/%Y') if order.date_order else '', date_fmt)
                    sheet.write(self.row_num, 2, line.product_id.name, normal_fmt)
                    sheet.write(self.row_num, 3, order.user_id.name, normal_fmt)
                    sheet.write(self.row_num, 4, line.product_uom_qty, normal_fmt)
                    sheet.write(self.row_num, 5, line.price_unit, money_fmt)
                    sheet.write(self.row_num, 6, line.price_subtotal, money_fmt)
                    self.row_num += 1

        sheet.set_column(0, 0, 40)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 2, 45)
        sheet.set_column(3, 5, 15)

        workbook.close()
        output.seek(0)
        
        file_name = f"Sales_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return request.make_response(output.read(), [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename={file_name}')
        ])

    @http.route('/sales_report/report_html', type='json', auth='user')
    def get_report_html(self, month=None, year=None, groupby=None, **kw):
        # 1. Handling Groupby (Bisa kosong untuk mode Flat List)
        if groupby is None:
            groupby = ['customer']
            
        # 2. Setup Filter Tanggal & Domain
        date_from = kw.get('date_from')
        date_to = kw.get('date_to')
        domain = [('state', 'in', ['sale', 'done'])]
        
        # Jika benar-benar pertama kali buka (date_from & date_to kosong)
        # Anda bisa mengaktifkan default hari ini di sini jika diinginkan
        if date_from:
            domain.append(('date_order', '>=', date_from))
        if date_to:
            domain.append(('date_order', '<=', date_to))
            
        customer_ids = kw.get('customer_ids', [])
        if customer_ids:
            domain.append(('partner_id', 'in', customer_ids))
            
        # 3. Ambil Data Sales
        sales_orders = request.env['sale.order'].sudo().search(domain, order='date_order desc')

        # 4. Helper Format Tanggal Indonesia (DD MMMM YYYY)
        def format_indo(date_val):
            if not date_val: return False
            # Jika date_val adalah string (dari kw), ubah ke date object
            if isinstance(date_val, str):
                try:
                    date_val = datetime.strptime(date_val, '%Y-%m-%d').date()
                except:
                    return date_val
            
            months = {
                1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
                5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
                9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
            }
            return f"{date_val.day} {months[date_val.month]} {date_val.year}"

        # 5. Tentukan Label Periode untuk Header
        if date_from and date_to:
            periode_label = f"{format_indo(date_from)} - {format_indo(date_to)}"
        elif date_from:
            periode_label = f"Mulai {format_indo(date_from)}"
        elif date_to:
            periode_label = f"Hingga {format_indo(date_to)}"
        else:
            today_str = format_indo(date.today())
            periode_label = f"Hari Ini ({today_str})"
        
        # 6. Helper untuk nilai grouping
        def get_val(order, line, key):
            if key == 'customer': return order.partner_id.name or "Unknown Customer"
            if key == 'order': return order.name
            if key == 'product': return line.product_id.display_name or "Unknown Product"
            return "Other"

        report_data = {}
        all_lines = [] # Untuk mode tanpa grouping

        # 7. Proses Data
        for order in sales_orders:
            for line in order.order_line:
                # Simpan data mentah untuk flat list (tampilan saat badge semua di-close)
                line_info = {
                    'order_id': order.id,
                    'ref': order.name,
                    'product': line.product_id.display_name,
                    'salesperson': order.user_id.name or '',
                    'qty': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'subtotal': line.price_subtotal,
                    'date_order': order.date_order.strftime('%d/%m/%Y') if order.date_order else ''
                }
                all_lines.append(line_info)

                # Proses Tree Data jika ada Grouping
                if groupby:
                    active_keys = [get_val(order, line, k) for k in groupby]
                    current_level = report_data
                    for i, key in enumerate(active_keys):
                        if key not in current_level:
                            current_level[key] = {'total': 0.0, 'children': {}, 'lines': []}
                        
                        current_level[key]['total'] += line.price_subtotal
                        
                        if i == len(active_keys) - 1:
                            current_level[key]['lines'].append(line_info)
                        else:
                            current_level = current_level[key]['children']

        # 8. Render Template
        return request.env['ir.ui.view']._render_template(
            'sale_sales_report.report_sales_html_screen', {
                'report_data': report_data,
                'all_lines': all_lines,      # Digunakan saat groupby kosong
                'active_groups': groupby,
                'date_from': date_from,
                'date_to': date_to,
                'periode_label': periode_label,
                'base_url': request.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            }
        )