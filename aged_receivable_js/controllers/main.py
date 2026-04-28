# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, date
import json
import io
from odoo.tools.misc import xlsxwriter

class AgedReceivableController(http.Controller):

    def _get_report_data(self, date_as_of, company_ids=None):
        if not company_ids:
            company_ids = tuple(request.env.companies.ids)
        else:
            # Handle if passed as string from URL
            if isinstance(company_ids, str):
                company_ids = tuple(int(x) for x in company_ids.split(','))
            else:
                company_ids = tuple(company_ids)
        
        # Optimized SQL Query to fetch all data in one go
        query = """
            SELECT 
                aml.id,
                p.id as partner_id,
                p.name as partner_name,
                m.id as move_id,
                m.name as move_name,
                m.ref as move_ref,
                m.payment_state as payment_state,
                aml.date as date,
                COALESCE(aml.date_maturity, aml.date) as date_maturity,
                aml.balance,
                (
                    SELECT COALESCE(SUM(pr.amount), 0)
                    FROM account_partial_reconcile pr
                    JOIN account_move_line aml2 ON (
                        (pr.debit_move_id = aml.id AND pr.credit_move_id = aml2.id) OR
                        (pr.credit_move_id = aml.id AND pr.debit_move_id = aml2.id)
                    )
                    WHERE aml2.date <= %s
                ) as reconciled_amount
            FROM account_move_line aml
            JOIN account_move m ON m.id = aml.move_id
            JOIN res_partner p ON p.id = aml.partner_id
            JOIN account_account acc ON acc.id = aml.account_id
            WHERE acc.account_type = 'asset_receivable'
              AND m.state = 'posted'
              AND aml.date <= %s
              AND aml.company_id IN %s
              AND m.payment_state NOT IN ('paid', 'in_payment')
            ORDER BY p.name, aml.date
        """
        
        request.env.cr.execute(query, (date_as_of, date_as_of, company_ids))
        results = request.env.cr.dictfetchall()
        
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

        currency = request.env.company.currency_id

        for res in results:
            # Calculate residual
            if res['balance'] > 0:
                residual = max(0, res['balance'] - res['reconciled_amount'])
            else:
                residual = min(0, res['balance'] + res['reconciled_amount'])

            # Skip if fully paid as of that date
            if currency.is_zero(residual):
                continue

            partner_id = res['partner_id'] or 0
            partner_name = res['partner_name'] or "Unknown Partner"
            
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
            
            due_date = res['date_maturity']
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
                'move_id': res['move_id'],
                'move_name': res['move_name'],
                'payment_state': res['payment_state'],
                'ref': res['move_ref'] or '',
                'date': res['date'].strftime('%d/%m/%Y'),
                'due_date': due_date.strftime('%d/%m/%Y'),
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
            'today': date_as_of.strftime('%d/%m/%Y')
        }

    @http.route('/aged_receivable/data', type='json', auth='user')
    def get_aged_receivable_data(self, **kwargs):
        date_str = kwargs.get('date_to')
        company_ids = kwargs.get('company_ids')
        if date_str:
            date_as_of = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date_as_of = date.today()
        return self._get_report_data(date_as_of, company_ids=company_ids)

    @http.route('/aged_receivable/export', type='http', auth='user')
    def export_aged_receivable_excel(self, date_to=None, company_ids=None, **kwargs):
        if date_to:
            date_as_of = datetime.strptime(date_to, '%Y-%m-%d').date()
        else:
            date_as_of = date.today()

        data = self._get_report_data(date_as_of, company_ids=company_ids)
        
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
        sheet.write('A2', f'As of: {date_as_of.strftime("%d/%m/%Y")}')
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
        sheet.write(row, 4, totals['total'], total_row_format) # Wait, index was wrong in my thought
        # Correcting columns for totals
        sheet.write(row, 3, totals['b31_60'], total_row_format)
        sheet.write(row, 4, totals['b61_90'], total_row_format)
        sheet.write(row, 5, totals['b91_120'], total_row_format)
        sheet.write(row, 6, totals['older'], total_row_format)
        sheet.write(row, 7, totals['total'], total_row_format)

        workbook.close()
        output.seek(0)
        
        filename = f'Aged_Receivable_{date_as_of.strftime("%d-%m-%Y")}.xlsx'
        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename={filename}')
            ]
        )
