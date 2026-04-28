# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime
import io
import json

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class StockLotReportController(http.Controller):

    def _get_quant_lines(self, location_id=None, product_id=None, lot_id=None, check_date=None, company_ids=None):
        """
        Query stock.quant untuk mendapatkan stok on-hand per lot.
        Jika check_date diisi, hitung qty berdasarkan stock.move.line s/d tanggal tersebut.
        """
        # Gunakan company_ids yang dikirim dari JS (company yang dicentang user)
        # Fallback ke request.env.companies jika tidak dikirim
        if not company_ids:
            company_ids = request.env.companies.ids

        domain = [
            ('location_id.usage', 'in', ['internal', 'transit']),
            ('quantity', '!=', 0),
            ('company_id', 'in', company_ids),
        ]
        if location_id:
            domain.append(('location_id', 'child_of', int(location_id)))
        if product_id:
            domain.append(('product_id', '=', int(product_id)))
        if lot_id:
            domain.append(('lot_id', '=', int(lot_id)))

        lines = []

        if check_date:
            # Hitung qty berdasarkan stock.move.line yang sudah done s/d check_date
            check_dt = check_date + ' 23:59:59'
            move_domain = [
                ('state', '=', 'done'),
                ('date', '<=', check_dt),
                ('location_dest_id.usage', 'in', ['internal', 'transit']),
                ('company_id', 'in', company_ids),
            ]
            if location_id:
                move_domain.append(('location_dest_id', 'child_of', int(location_id)))
            if product_id:
                move_domain.append(('product_id', '=', int(product_id)))
            if lot_id:
                move_domain.append(('lot_id', '=', int(lot_id)))

            # Incoming moves (masuk ke lokasi internal)
            incoming = request.env['stock.move.line'].sudo().read_group(
                move_domain,
                ['qty_done:sum'],
                ['product_id', 'lot_id', 'location_dest_id'],
                lazy=False,
            )

            # Outgoing moves (keluar dari lokasi internal)
            out_domain = [
                ('state', '=', 'done'),
                ('date', '<=', check_dt),
                ('location_id.usage', 'in', ['internal', 'transit']),
                ('company_id', 'in', company_ids),
            ]
            if location_id:
                out_domain.append(('location_id', 'child_of', int(location_id)))
            if product_id:
                out_domain.append(('product_id', '=', int(product_id)))
            if lot_id:
                out_domain.append(('lot_id', '=', int(lot_id)))

            outgoing = request.env['stock.move.line'].sudo().read_group(
                out_domain,
                ['qty_done:sum'],
                ['product_id', 'lot_id', 'location_id'],
                lazy=False,
            )

            # Gabungkan: key = (product_id, lot_id, location_id)
            qty_map = {}
            for rec in incoming:
                pid = rec['product_id'][0] if rec['product_id'] else 0
                lid = rec['lot_id'][0] if rec['lot_id'] else 0
                loc = rec['location_dest_id'][0] if rec['location_dest_id'] else 0
                key = (pid, lid, loc)
                qty_map[key] = qty_map.get(key, 0) + (rec['qty_done'] or 0)

            for rec in outgoing:
                pid = rec['product_id'][0] if rec['product_id'] else 0
                lid = rec['lot_id'][0] if rec['lot_id'] else 0
                loc = rec['location_id'][0] if rec['location_id'] else 0
                key = (pid, lid, loc)
                qty_map[key] = qty_map.get(key, 0) - (rec['qty_done'] or 0)

            # Build lines dari qty_map
            Product = request.env['product.product'].sudo()
            Lot = request.env['stock.lot'].sudo()
            Location = request.env['stock.location'].sudo()

            for (pid, lid, loc_id), qty in qty_map.items():
                if qty == 0:
                    continue
                product = Product.browse(pid)
                lot = Lot.browse(lid) if lid else None
                location = Location.browse(loc_id)
                lines.append({
                    'location': location.complete_name or location.name or '',
                    'product': product.display_name or '',
                    'product_id': pid,
                    'lot': lot.name if lot and lot.exists() else '',
                    'lot_id': lid,
                    'uom': product.uom_id.name or '',
                    'qty': qty,
                })
        else:
            # Gunakan stock.quant langsung (stok saat ini)
            quants = request.env['stock.quant'].sudo().search(domain)
            for q in quants:
                lines.append({
                    'location': q.location_id.complete_name or q.location_id.name or '',
                    'product': q.product_id.display_name or '',
                    'product_id': q.product_id.id,
                    'lot': q.lot_id.name if q.lot_id else '',
                    'lot_id': q.lot_id.id if q.lot_id else 0,
                    'uom': q.product_uom_id.name or '',
                    'qty': q.quantity,
                })

        # Sort: lokasi -> produk -> lot
        lines.sort(key=lambda x: (x['location'], x['product'], x['lot']))
        return lines

    def _group_lines(self, lines, group_by, group_by2=None):
        """
        Mengelompokkan lines. Jika group_by2 diisi, hasilnya nested 2 level.
        Single level: [{'key', 'lines', 'subtotal'}]
        Two level:    [{'key', 'subtotal', 'subgroups': [{'key', 'lines', 'subtotal'}]}]
        """
        key_fns = {
            'location': lambda l: l['location'],
            'product':  lambda l: l['product'],
        }
        fn1 = key_fns.get(group_by, lambda l: '')

        # Build level-1 groups
        groups1 = {}
        order1 = []
        for line in lines:
            k = fn1(line)
            if k not in groups1:
                groups1[k] = []
                order1.append(k)
            groups1[k].append(line)

        if not group_by2 or group_by2 == group_by:
            # Single level
            return [
                {'key': k, 'lines': groups1[k], 'subtotal': sum(l['qty'] for l in groups1[k]), 'subgroups': None}
                for k in order1
            ]

        fn2 = key_fns.get(group_by2, lambda l: '')

        result = []
        for k1 in order1:
            sub = {}
            sub_order = []
            for line in groups1[k1]:
                k2 = fn2(line)
                if k2 not in sub:
                    sub[k2] = []
                    sub_order.append(k2)
                sub[k2].append(line)
            subgroups = [
                {'key': k2, 'lines': sub[k2], 'subtotal': sum(l['qty'] for l in sub[k2])}
                for k2 in sub_order
            ]
            result.append({
                'key': k1,
                'subtotal': sum(l['qty'] for l in groups1[k1]),
                'subgroups': subgroups,
                'lines': [],
            })
        return result

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

    @http.route('/stock_lot_report/data', type='json', auth='user')
    def get_report_data(self, location_id=None, product_id=None, lot_id=None, check_date=None, company_ids=None, group_by=None, group_by2=None, **kw):
        lines = self._get_quant_lines(location_id, product_id, lot_id, check_date, company_ids)

        total_products = len(set(l['product_id'] for l in lines))
        total_lots = len(set(l['lot_id'] for l in lines if l['lot_id']))
        total_qty = sum(l['qty'] for l in lines)
        total_locations = len(set(l['location'] for l in lines))

        kpi = {
            'total_locations': total_locations,
            'total_products': total_products,
            'total_lots': total_lots,
            'total_qty': total_qty,
        }

        date_label = f"Per Tanggal: {self._format_indo(check_date)}" if check_date else "Stok Saat Ini"

        grouped = self._group_lines(lines, group_by, group_by2) if group_by else None

        return request.env['ir.ui.view']._render_template(
            'stock_lot_report.report_html', {
                'lines': lines,
                'grouped': grouped,
                'group_by': group_by or '',
                'group_by2': group_by2 or '',
                'kpi': kpi,
                'check_date': check_date or '',
                'date_label': date_label,
            }
        )

    @http.route('/stock_lot_report/export_excel', type='http', auth='user')
    def export_excel(self, location_id=None, product_id=None, lot_id=None, check_date=None, company_ids=None, group_by=None, **kw):
        # company_ids dari query string dikirim sebagai string "1,2"
        if company_ids:
            company_ids = [int(x) for x in str(company_ids).split(',') if x.strip().isdigit()]
        lines = self._get_quant_lines(location_id, product_id, lot_id, check_date, company_ids)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Stock Lot Report')

        title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#1e293b'})
        head_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#0f766e', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        normal_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        qty_fmt = workbook.add_format({'num_format': '#,##0.##', 'border': 1, 'align': 'right'})
        total_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#f0fdf4', 'border': 1,
            'num_format': '#,##0.##', 'align': 'right'
        })

        date_label = f"Per Tanggal: {check_date}" if check_date else "Stok Saat Ini"
        sheet.write(0, 0, 'Stock Lot Report', title_fmt)
        sheet.write(1, 0, date_label)
        sheet.write(2, 0, f'Total Qty: {sum(l["qty"] for l in lines):,.2f}')

        headers = ['No', 'Lokasi', 'Produk', 'Lot/Serial Number', 'UoM', 'On Hand Qty']
        for col, h in enumerate(headers):
            sheet.write(4, col, h, head_fmt)

        for i, line in enumerate(lines):
            r = 5 + i
            sheet.write(r, 0, i + 1, normal_fmt)
            sheet.write(r, 1, line['location'], normal_fmt)
            sheet.write(r, 2, line['product'], normal_fmt)
            sheet.write(r, 3, line['lot'] or '-', normal_fmt)
            sheet.write(r, 4, line['uom'], normal_fmt)
            sheet.write(r, 5, line['qty'], qty_fmt)

        total_row = 5 + len(lines)
        sheet.write(total_row, 4, 'TOTAL', total_fmt)
        sheet.write(total_row, 5, sum(l['qty'] for l in lines), total_fmt)

        sheet.set_column(0, 0, 5)
        sheet.set_column(1, 1, 40)
        sheet.set_column(2, 2, 40)
        sheet.set_column(3, 3, 25)
        sheet.set_column(4, 4, 12)
        sheet.set_column(5, 5, 14)

        workbook.close()
        output.seek(0)
        file_name = f"Stock_Lot_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return request.make_response(output.read(), [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename={file_name}')
        ])
