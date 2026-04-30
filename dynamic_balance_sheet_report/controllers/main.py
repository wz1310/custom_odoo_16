# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime
import io
from odoo.tools.misc import xlsxwriter

class BalanceSheetController(http.Controller):

    def _get_report_data(self, date_from, date_to, target_move, company_id, account_range_type, show_unposted, show_zero, journal_ids=None):
        model = request.env['balance.sheet.report']
        # Use first company id for the transient record (just for context), actual filtering uses company_id recordset
        first_company_id = company_id[0].id if company_id else False
        rec = model.create({
            'date_from': date_from,
            'date_to': date_to,
            'target_move': target_move,
            'company_id': first_company_id,
            'account_range_type': account_range_type,
            'show_unposted': show_unposted,
            'show_zero': show_zero,
        })
        try:
            return rec.get_balance_sheet_data(
                date_from=date_from, date_to=date_to,
                target_move=target_move, company_id=company_id,
                journal_ids=journal_ids
            )
        except Exception as e:
            request.env.cr.rollback()
            raise e
        finally:
            try:
                rec.unlink()
            except Exception:
                pass

    @http.route('/dynamic_balance_sheet_report/data', type='json', auth='user')
    def get_balance_sheet_data(self, **kwargs):
        date_str = kwargs.get('date_to')
        date_from_str = kwargs.get('date_from')
        company_ids = kwargs.get('company_ids')  # now a list or False
        target_move = kwargs.get('target_move', 'posted')
        account_range_type = kwargs.get('account_range_type', 'all')
        show_unposted = kwargs.get('show_unposted', False)
        show_zero = kwargs.get('show_zero', False)
        journal_ids = kwargs.get('journal_ids') or None

        if date_str:
            date_to = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date_to = datetime.now().date()

        if date_from_str:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        else:
            date_from = datetime.now().date().replace(month=1, day=1)

        # Support single id or list of ids
        if company_ids:
            if isinstance(company_ids, list):
                company_id = request.env['res.company'].browse(company_ids)
            else:
                company_id = request.env['res.company'].browse([company_ids])
        else:
            company_id = request.env.company

        return self._get_report_data(date_from, date_to, target_move, company_id, account_range_type, show_unposted, show_zero, journal_ids=journal_ids)

    def _write_section(self, sheet, row, section_label, accounts, total, total_label,
                       with_detail, fmt):
        """Write one balance sheet section (e.g. Current Assets) to the sheet."""
        if not accounts:
            return row

        # Section header
        sheet.write(row, 0, section_label, fmt['section'])
        sheet.write(row, 1, '', fmt['section'])
        sheet.write(row, 2, '', fmt['section'])
        sheet.write(row, 3, '', fmt['section'])
        if with_detail:
            sheet.write(row, 4, '', fmt['section'])
            sheet.write(row, 5, '', fmt['section'])
            sheet.write(row, 6, total, fmt['section_amount'])
        else:
            sheet.write(row, 4, total, fmt['section_amount'])
        row += 1

        for acc in accounts:
            # Account row — when with_detail, balance aligns with the detail Balance column (col 6)
            sheet.write(row, 1, acc['code'], fmt['account'])
            sheet.write(row, 2, acc['name'], fmt['account'])
            sheet.write(row, 3, '', fmt['account'])
            if with_detail:
                sheet.write(row, 4, '', fmt['account'])
                sheet.write(row, 5, '', fmt['account'])
                sheet.write(row, 6, acc['balance'], fmt['account_amount'])
            else:
                sheet.write(row, 4, acc['balance'], fmt['account_amount'])
            row += 1

            if with_detail:
                lines = acc.get('lines') or []
                if lines:
                    # Detail column headers
                    sheet.write(row, 2, 'Date', fmt['detail_header'])
                    sheet.write(row, 3, 'Reference', fmt['detail_header'])
                    sheet.write(row, 4, 'Debit', fmt['detail_header'])
                    sheet.write(row, 5, 'Credit', fmt['detail_header'])
                    sheet.write(row, 6, 'Balance', fmt['detail_header'])
                    row += 1
                    for line in lines:
                        raw_date = line.get('date', '')
                        if raw_date:
                            try:
                                fmt_date = datetime.strptime(str(raw_date), '%Y-%m-%d').strftime('%d/%m/%Y')
                            except Exception:
                                fmt_date = str(raw_date)
                        else:
                            fmt_date = ''
                        sheet.write(row, 2, fmt_date, fmt['detail'])
                        sheet.write(row, 3, line.get('move_name', ''), fmt['detail'])
                        sheet.write(row, 4, line.get('debit', 0), fmt['detail_amount'])
                        sheet.write(row, 5, line.get('credit', 0), fmt['detail_amount'])
                        sheet.write(row, 6, line.get('balance', 0), fmt['detail_amount'])
                        row += 1

        # Total row — also align with detail Balance column when with_detail
        sheet.write(row, 0, '', fmt['total'])
        sheet.write(row, 1, '', fmt['total'])
        sheet.write(row, 2, total_label, fmt['total'])
        sheet.write(row, 3, '', fmt['total'])
        if with_detail:
            sheet.write(row, 4, '', fmt['total'])
            sheet.write(row, 5, '', fmt['total'])
            sheet.write(row, 6, total, fmt['total_amount'])
        else:
            sheet.write(row, 4, total, fmt['total_amount'])
        row += 1

        return row

    @http.route('/dynamic_balance_sheet_report/export/excel', type='http', auth='user')
    def export_excel(self, **kwargs):
        date_from_str = kwargs.get('date_from')
        date_to_str = kwargs.get('date_to')
        target_move = kwargs.get('target_move', 'posted')
        company_id = kwargs.get('company_id', False)
        account_range_type = kwargs.get('account_range_type', 'all')
        show_unposted = kwargs.get('show_unposted', 'false') == 'true'
        show_zero = kwargs.get('show_zero', 'false') == 'true'
        journal_ids_str = kwargs.get('journal_ids', '')
        journal_ids = [int(x) for x in journal_ids_str.split(',') if x.strip()] if journal_ids_str else None
        with_detail = kwargs.get('with_detail', '0') == '1'

        if date_from_str:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        else:
            date_from = datetime.now().date().replace(month=1, day=1)

        if date_to_str:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        else:
            date_to = datetime.now().date()

        company_ids_str = kwargs.get('company_ids', '')
        company_ids_list = [int(x) for x in company_ids_str.split(',') if x.strip()] if company_ids_str else None
        company = request.env['res.company'].browse(company_ids_list) if company_ids_list else request.env.company
        data = self._get_report_data(date_from, date_to, target_move, company, account_range_type, show_unposted, show_zero, journal_ids=journal_ids)

        output = io.BytesIO()
        # Use wider columns when with_detail to accommodate transaction columns
        col_count = 7 if with_detail else 5
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Balance Sheet')

        # ── Formats ──────────────────────────────────────────────────────────
        fmt = {
            'title':          workbook.add_format({'bold': True, 'font_size': 15, 'font_color': '#1a73e8', 'bottom': 2}),
            'subtitle':       workbook.add_format({'font_size': 10, 'font_color': '#5f6368', 'italic': True}),
            'group':          workbook.add_format({'bold': True, 'bg_color': '#e5e7eb', 'font_size': 12, 'border': 1}),
            'section':        workbook.add_format({'bold': True, 'bg_color': '#f0f4f8', 'border': 1, 'indent': 1}),
            'section_amount': workbook.add_format({'bold': True, 'bg_color': '#f0f4f8', 'border': 1, 'num_format': '#,##0.00'}),
            'account':        workbook.add_format({'bg_color': '#ffffff', 'border': 1, 'indent': 2}),
            'account_amount': workbook.add_format({'bg_color': '#ffffff', 'border': 1, 'num_format': '#,##0.00'}),
            'detail_header':  workbook.add_format({'bold': True, 'bg_color': '#f9fafb', 'border': 1, 'font_size': 9, 'italic': True, 'indent': 3}),
            'detail':         workbook.add_format({'font_size': 9, 'border': 1, 'indent': 3}),
            'detail_amount':  workbook.add_format({'font_size': 9, 'border': 1, 'num_format': '#,##0.00'}),
            'total':          workbook.add_format({'bold': True, 'bg_color': '#e8f0fe', 'border': 2, 'indent': 1}),
            'total_amount':   workbook.add_format({'bold': True, 'bg_color': '#e8f0fe', 'border': 2, 'num_format': '#,##0.00'}),
            'grand_total':    workbook.add_format({'bold': True, 'bg_color': '#dbeafe', 'border': 2, 'font_size': 12}),
            'grand_amount':   workbook.add_format({'bold': True, 'bg_color': '#dbeafe', 'border': 2, 'font_size': 12, 'num_format': '#,##0.00'}),
        }

        # ── Column widths ─────────────────────────────────────────────────────
        sheet.set_column(0, 0, 4)    # indent spacer
        sheet.set_column(1, 1, 12)   # code
        sheet.set_column(2, 2, 40)   # name / description
        sheet.set_column(3, 3, 5)    # spacer
        sheet.set_column(4, 4, 18)   # balance
        if with_detail:
            sheet.set_column(5, 5, 18)   # debit
            sheet.set_column(6, 6, 18)   # credit / balance detail

        # ── Header ────────────────────────────────────────────────────────────
        merge_end = col_count - 1
        sheet.merge_range(0, 0, 0, merge_end, 'Balance Sheet Report', fmt['title'])
        sheet.merge_range(1, 0, 1, merge_end, f"Company: {data['company_name']}", fmt['subtitle'])
        sheet.merge_range(2, 0, 2, merge_end, f"Period: {date_from.strftime('%d/%m/%Y')}  to  {date_to.strftime('%d/%m/%Y')}", fmt['subtitle'])
        export_type = 'With Transaction Details' if with_detail else 'Summary Only'
        sheet.merge_range(3, 0, 3, merge_end, f"Export Type: {export_type}", fmt['subtitle'])

        row = 5

        # ── ASSETS ────────────────────────────────────────────────────────────
        sheet.merge_range(row, 0, row, merge_end, 'ASSETS', fmt['group'])
        row += 1

        row = self._write_section(sheet, row,
            'Current Assets', data.get('assets_current', []),
            data['totals']['assets_current'], 'Total Current Assets',
            with_detail, fmt)

        row = self._write_section(sheet, row,
            'Non-Current Assets', data.get('assets_non_current', []),
            data['totals']['assets_non_current'], 'Total Non-Current Assets',
            with_detail, fmt)

        # Grand total assets
        sheet.write(row, 0, '', fmt['grand_total'])
        sheet.write(row, 1, '', fmt['grand_total'])
        sheet.write(row, 2, 'TOTAL ASSETS', fmt['grand_total'])
        sheet.write(row, 3, '', fmt['grand_total'])
        if with_detail:
            sheet.write(row, 4, '', fmt['grand_total'])
            sheet.write(row, 5, '', fmt['grand_total'])
            sheet.write(row, 6, data['totals']['total_assets'], fmt['grand_amount'])
        else:
            sheet.write(row, 4, data['totals']['total_assets'], fmt['grand_amount'])
        row += 2

        # ── LIABILITIES AND EQUITY ────────────────────────────────────────────
        sheet.merge_range(row, 0, row, merge_end, 'LIABILITIES AND EQUITY', fmt['group'])
        row += 1

        row = self._write_section(sheet, row,
            'Current Liabilities', data.get('liabilities_current', []),
            data['totals']['liabilities_current'], 'Total Current Liabilities',
            with_detail, fmt)

        row = self._write_section(sheet, row,
            'Non-Current Liabilities', data.get('liabilities_non_current', []),
            data['totals']['liabilities_non_current'], 'Total Non-Current Liabilities',
            with_detail, fmt)

        row = self._write_section(sheet, row,
            'Equity', data.get('equity', []),
            data['totals']['total_equity'], 'Total Equity',
            with_detail, fmt)

        # Grand total liabilities & equity
        sheet.write(row, 0, '', fmt['grand_total'])
        sheet.write(row, 1, '', fmt['grand_total'])
        sheet.write(row, 2, 'TOTAL LIABILITIES AND EQUITY', fmt['grand_total'])
        sheet.write(row, 3, '', fmt['grand_total'])
        if with_detail:
            sheet.write(row, 4, '', fmt['grand_total'])
            sheet.write(row, 5, '', fmt['grand_total'])
            sheet.write(row, 6, data['totals']['total_liabilities_equity'], fmt['grand_amount'])
        else:
            sheet.write(row, 4, data['totals']['total_liabilities_equity'], fmt['grand_amount'])

        workbook.close()
        output.seek(0)

        suffix = '_with_details' if with_detail else '_summary'
        filename = f'Balance_Sheet_{date_from}_to_{date_to}{suffix}.xlsx'
        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename={filename}')
            ]
        )
