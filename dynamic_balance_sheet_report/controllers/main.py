# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime
import io
from odoo.tools.misc import xlsxwriter

class BalanceSheetController(http.Controller):

    def _get_report_data(self, date_from, date_to, target_move, company_id, account_range_type, show_unposted, show_zero):
        model = request.env['balance.sheet.report']
        # Create a temporary record for the report
        rec = model.create({
            'date_from': date_from,
            'date_to': date_to,
            'target_move': target_move,
            'company_id': company_id.id if company_id else False,
            'account_range_type': account_range_type,
            'show_unposted': show_unposted,
            'show_zero': show_zero,
        })
        try:
            return rec.get_balance_sheet_data()
        except Exception as e:
            # Log error and re-raise
            request.env.cr.rollback()
            raise e
        finally:
            try:
                rec.unlink()
            except Exception:
                # If unlink fails (e.g., transaction aborted), ignore
                pass

    @http.route('/dynamic_balance_sheet_report/data', type='json', auth='user')
    def get_balance_sheet_data(self, **kwargs):
        date_str = kwargs.get('date_to')
        date_from_str = kwargs.get('date_from')
        company_ids = kwargs.get('company_ids')
        target_move = kwargs.get('target_move', 'posted')
        account_range_type = kwargs.get('account_range_type', 'all')
        show_unposted = kwargs.get('show_unposted', False)
        show_zero = kwargs.get('show_zero', False)
        
        if date_str:
            date_to = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date_to = datetime.now().date()
            
        if date_from_str:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        else:
            date_from = datetime.now().date().replace(month=1, day=1)
        
        company_id = request.env['res.company'].browse(company_ids) if company_ids else request.env.company
        
        return self._get_report_data(date_from, date_to, target_move, company_id, account_range_type, show_unposted, show_zero)

    @http.route('/dynamic_balance_sheet_report/export/excel', type='http', auth='user')
    def export_excel(self, **kwargs):
        date_from_str = kwargs.get('date_from')
        date_to_str = kwargs.get('date_to')
        target_move = kwargs.get('target_move', 'posted')
        company_id = kwargs.get('company_id', False)
        account_range_type = kwargs.get('account_range_type', 'all')
        show_unposted = kwargs.get('show_unposted', 'false') == 'true'
        show_zero = kwargs.get('show_zero', 'false') == 'true'
        
        if date_from_str:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        else:
            date_from = datetime.now().date().replace(month=1, day=1)
            
        if date_to_str:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        else:
            date_to = datetime.now().date()
        
        company = request.env['res.company'].browse(int(company_id)) if company_id else request.env.company
        
        data = self._get_report_data(date_from, date_to, target_move, company, account_range_type, show_unposted, show_zero)
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Balance Sheet')
        
        title_format = workbook.add_format({'bold': True, 'font_size': 16, 'font_color': '#1a73e8', 'bottom': 2})
        subtitle_format = workbook.add_format({'bold': True, 'font_size': 10, 'font_color': '#5f6368'})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#f8f9fa', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        account_format = workbook.add_format({'bold': True, 'bg_color': '#f0f4f8', 'border': 1, 'left': 2})
        line_format = workbook.add_format({'font_size': 9, 'border': 1, 'left': 1})
        amount_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1, 'right': 1})
        total_format = workbook.add_format({'bold': True, 'bg_color': '#e8f0fe', 'border': 2, 'num_format': '#,##0.00'})
        
        currency_symbol = request.env.company.currency_id.symbol or '$'
        
        sheet.merge_range('A1:D1', 'Balance Sheet Report', title_format)
        sheet.merge_range('A2:D2', f'Company: {data["company_name"]}', subtitle_format)
        sheet.merge_range('A3:D3', f'Period: {date_from} to {date_to}', subtitle_format)
        sheet.merge_range('A4:D4', f'Currency: {currency_symbol}', subtitle_format)
        
        row = 6
        
        sheet.merge_range(row, 0, row, 3, 'ASSETS', header_format)
        row += 1
        
        if data.get('assets_current'):
            sheet.write(row, 0, 'Current Assets', account_format)
            sheet.write(row, 3, data['totals'].get('assets_current', 0), amount_format)
            row += 1
            for acc in data['assets_current']:
                sheet.write(row, 1, f"{acc['code']} - {acc['name']}", line_format)
                sheet.write(row, 3, acc['balance'], amount_format)
                row += 1
        
        if data.get('assets_non_current'):
            sheet.write(row, 0, 'Non-Current Assets', account_format)
            sheet.write(row, 3, data['totals'].get('assets_non_current', 0), amount_format)
            row += 1
            for acc in data['assets_non_current']:
                sheet.write(row, 1, f"{acc['code']} - {acc['name']}", line_format)
                sheet.write(row, 3, acc['balance'], amount_format)
                row += 1
        
        sheet.merge_range(row, 0, row, 2, 'TOTAL ASSETS', total_format)
        sheet.write(row, 3, data['totals'].get('total_assets', 0), total_format)
        row += 2
        
        sheet.merge_range(row, 0, row, 3, 'LIABILITIES AND EQUITY', header_format)
        row += 1
        
        if data.get('liabilities_current'):
            sheet.write(row, 0, 'Current Liabilities', account_format)
            sheet.write(row, 3, data['totals'].get('liabilities_current', 0), amount_format)
            row += 1
            for acc in data['liabilities_current']:
                sheet.write(row, 1, f"{acc['code']} - {acc['name']}", line_format)
                sheet.write(row, 3, acc['balance'], amount_format)
                row += 1
        
        if data.get('liabilities_non_current'):
            sheet.write(row, 0, 'Non-Current Liabilities', account_format)
            sheet.write(row, 3, data['totals'].get('liabilities_non_current', 0), amount_format)
            row += 1
            for acc in data['liabilities_non_current']:
                sheet.write(row, 1, f"{acc['code']} - {acc['name']}", line_format)
                sheet.write(row, 3, acc['balance'], amount_format)
                row += 1
        
        if data.get('equity'):
            sheet.write(row, 0, 'Equity', account_format)
            sheet.write(row, 3, data['totals'].get('total_equity', 0), amount_format)
            row += 1
            for acc in data['equity']:
                sheet.write(row, 1, f"{acc['code']} - {acc['name']}", line_format)
                sheet.write(row, 3, acc['balance'], amount_format)
                row += 1
        
        sheet.merge_range(row, 0, row, 2, 'TOTAL LIABILITIES AND EQUITY', total_format)
        sheet.write(row, 3, data['totals'].get('total_liabilities_equity', 0), total_format)
        
        sheet.set_column('A:A', 35)
        sheet.set_column('B:B', 35)
        sheet.set_column('C:C', 5)
        sheet.set_column('D:D', 15)
        
        workbook.close()
        output.seek(0)
        
        filename = f'Balance_Sheet_{date_from}_to_{date_to}.xlsx'
        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename={filename}')
            ]
        )
