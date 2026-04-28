# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, date
import json
import io
from odoo.tools.misc import xlsxwriter

class AgedReceivableController(http.Controller):

    def _get_report_data(self, date_as_of):
        # Find all receivable lines that existed on or before the selected date
        domain = [
            ('account_id.account_type', '=', 'asset_receivable'),
            ('parent_state', '=', 'posted'),
            ('date', '<=', date_as_of),
        ]
        
        # Check for company filtering
        domain.append(('company_id', '=', request.env.company.id))

        move_lines = request.env['account.move.line'].search(domain)
        
        partners_data = {}
        totals = {
            'current': 0.0,
            'b1_30': 0.0,
            'b31_60': 0.0,
            'b61_90': 0.0,
            'b91_120': 0.0,
            'older': 0.0,
            'total': 0.0
        }

        for line in move_lines:
            # Calculate residual as of date_as_of
            balance = line.balance
            
            partials = request.env['account.partial.reconcile'].search([
                '|',
                ('debit_move_id', '=', line.id),
                ('credit_move_id', '=', line.id)
            ])
            
            reconciled_amount = 0.0
            for partial in partials:
                counterpart_line = partial.credit_move_id if partial.debit_move_id == line else partial.debit_move_id
                if counterpart_line.date <= date_as_of:
                    reconciled_amount += partial.amount

            if line.balance > 0:
                residual = max(0, line.balance - reconciled_amount)
            else:
                residual = min(0, line.balance + reconciled_amount)

            # Skip if fully paid as of that date OR currently already paid/in_payment
            if request.env.company.currency_id.is_zero(residual) or line.move_id.payment_state in ['paid', 'in_payment']:
                continue

            partner = line.partner_id
            partner_id = partner.id or 0
            partner_name = partner.name or "Unknown Partner"
            
            if partner_id not in partners_data:
                partners_data[partner_id] = {
                    'name': partner_name,
                    'current': 0.0,
                    'b1_30': 0.0,
                    'b31_60': 0.0,
                    'b61_90': 0.0,
                    'b91_120': 0.0,
                    'older': 0.0,
                    'total': 0.0,
                    'lines': []
                }
            
            due_date = line.date_maturity or line.date
            age = (date_as_of - due_date).days
            amount = residual
            
            bucket = 'current'
            if age <= 0:
                bucket = 'current'
            elif 1 <= age <= 30:
                bucket = 'b1_30'
            elif 31 <= age <= 60:
                bucket = 'b31_60'
            elif 61 <= age <= 90:
                bucket = 'b61_90'
            elif 91 <= age <= 120:
                bucket = 'b91_120'
            else:
                bucket = 'older'
            
            partners_data[partner_id][bucket] += amount
            partners_data[partner_id]['total'] += amount
            totals[bucket] += amount
            totals['total'] += amount
            
            partners_data[partner_id]['lines'].append({
                'move_id': line.move_id.id,
                'move_name': line.move_id.name,
                'payment_state': line.move_id.payment_state,
                'ref': line.move_id.ref or '',
                'date': line.date.strftime('%Y-%m-%d'),
                'due_date': due_date.strftime('%Y-%m-%d'),
                'age': age,
                'amount': amount,
                'bucket': bucket
            })

        partner_list = sorted(partners_data.values(), key=lambda x: x['total'], reverse=True)
        
        return {
            'partners': partner_list,
            'totals': totals,
            'currency': request.env.company.currency_id.name,
            'currency_symbol': request.env.company.currency_id.symbol,
            'currency_position': request.env.company.currency_id.position,
            'today': date_as_of.strftime('%Y-%m-%d')
        }

    @http.route('/aged_receivable/data', type='json', auth='user')
    def get_aged_receivable_data(self, **kwargs):
        date_str = kwargs.get('date_to')
        if date_str:
            date_as_of = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date_as_of = date.today()
        return self._get_report_data(date_as_of)

    @http.route('/aged_receivable/export', type='http', auth='user')
    def export_aged_receivable_excel(self, date_to=None, **kwargs):
        if date_to:
            date_as_of = datetime.strptime(date_to, '%Y-%m-%d').date()
        else:
            date_as_of = date.today()

        data = self._get_report_data(date_as_of)
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Aged Receivable')

        # Formats
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center'})
        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#008784'})
        partner_format = workbook.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1})
        amount_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        amount_bold_format = workbook.add_format({'num_format': '#,##0.00', 'bold': True, 'border': 1})
        detail_format = workbook.add_format({'font_size': 9, 'font_color': '#555555', 'border': 1})
        total_row_format = workbook.add_format({'bold': True, 'bg_color': '#E3F2FD', 'border': 1, 'num_format': '#,##0.00'})

        # Header info
        sheet.merge_range('A1:H1', 'Aged Receivable Report', title_format)
        sheet.write('A2', f'As of: {date_as_of}')
        sheet.write('A3', f'Currency: {data["currency"]}')

        # Table headers
        headers = ['PARTNER / INVOICE', 'NOT DUE', '1 - 30', '31 - 60', '61 - 90', '91 - 120', 'OLDER', 'TOTAL']
        for col, h in enumerate(headers):
            sheet.write(4, col, h, header_format)
        
        sheet.set_column('A:A', 45)
        sheet.set_column('B:H', 15)

        row = 5
        for partner in data['partners']:
            sheet.write(row, 0, partner['name'], partner_format)
            sheet.write(row, 1, partner['current'], amount_bold_format)
            sheet.write(row, 2, partner['b1_30'], amount_bold_format)
            sheet.write(row, 3, partner['b31_60'], amount_bold_format)
            sheet.write(row, 4, partner['b61_90'], amount_bold_format)
            sheet.write(row, 5, partner['b91_120'], amount_bold_format)
            sheet.write(row, 6, partner['older'], amount_bold_format)
            sheet.write(row, 7, partner['total'], amount_bold_format)
            row += 1

            for line in partner['lines']:
                sheet.write(row, 0, f"    {line['move_name']} ({line['ref']})", detail_format)
                sheet.write(row, 1, line['amount'] if line['bucket'] == 'current' else 0, amount_format)
                sheet.write(row, 2, line['amount'] if line['bucket'] == 'b1_30' else 0, amount_format)
                sheet.write(row, 3, line['amount'] if line['bucket'] == 'b31_60' else 0, amount_format)
                sheet.write(row, 4, line['amount'] if line['bucket'] == 'b61_90' else 0, amount_format)
                sheet.write(row, 5, line['amount'] if line['bucket'] == 'b91_120' else 0, amount_format)
                sheet.write(row, 6, line['amount'] if line['bucket'] == 'older' else 0, amount_format)
                sheet.write(row, 7, line['amount'], amount_bold_format)
                row += 1

        # Total Row at Bottom
        totals = data['totals']
        sheet.write(row, 0, 'TOTALS', total_row_format)
        sheet.write(row, 1, totals['current'], total_row_format)
        sheet.write(row, 2, totals['b1_30'], total_row_format)
        sheet.write(row, 3, totals['b31_60'], total_row_format)
        sheet.write(row, 4, totals['b61_90'], total_row_format)
        sheet.write(row, 5, totals['b91_120'], total_row_format)
        sheet.write(row, 6, totals['older'], total_row_format)
        sheet.write(row, 7, totals['total'], total_row_format)

        workbook.close()
        output.seek(0)
        
        filename = f'Aged_Receivable_{date_as_of}.xlsx'
        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename={filename}')
            ]
        )
