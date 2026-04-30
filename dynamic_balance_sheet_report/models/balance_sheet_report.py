# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime

class BalanceSheetReport(models.TransientModel):
    _name = "balance.sheet.report"
    _description = "Balance Sheet Report"

    name = fields.Char(string='Report Name', default='Balance Sheet')
    date_from = fields.Date(string='Start Date', required=True, default=lambda self: fields.Date.from_string(fields.Date.today().replace(month=1, day=1)))
    date_to = fields.Date(string='End Date', required=True, default=lambda self: fields.Date.today())
    target_move = fields.Selection([('posted', 'All Posted Entries'), ('all', 'All Entries')], string='Target Moves', default='posted')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    account_range_type = fields.Selection([('all', 'All Accounts'), ('balance', 'Only Balance Accounts'), ('profit', 'Only Profit Accounts')], string='Account Range', default='all')
    show_unposted = fields.Boolean(string='Show Unposted Entries', default=False)
    show_zero = fields.Boolean(string='Show Zero Balance Accounts', default=False)

    @api.model
    def _get_account_balances_with_lines(self, date_from, date_to, target_move, company_id):
        """Calculate account balances with line details for balance sheet."""
        self.env.cr.execute("""
            SELECT 
                aa.id as account_id,
                aa.code,
                aa.name,
                aa.internal_group,
                aa.currency_id,
                SUM(aml.debit) as debit,
                SUM(aml.credit) as credit,
                COALESCE(SUM(aml.debit), 0) - COALESCE(SUM(aml.credit), 0) as balance,
                array_agg(DISTINCT aml.id) as line_ids
            FROM account_move_line aml
            JOIN account_account aa ON aa.id = aml.account_id
            JOIN account_move am ON am.id = aml.move_id
            WHERE aa.company_id = %s 
                AND aa.deprecated = FALSE
                AND am.state = %s
                AND aml.date <= %s
                AND (aml.date >= %s OR %s IS NULL)
            GROUP BY aa.id, aa.code, aa.name, aa.internal_group, aa.currency_id
            ORDER BY aa.code
        """, (company_id.id, target_move, date_to, date_from, date_from))
        
        results = self.env.cr.dictfetchall()
        
        # Fetch line details for each account
        for acc in results:
            line_ids = acc.pop('line_ids', []) or []
            if isinstance(line_ids, str):
                # Parse PostgreSQL array string
                line_ids = [int(x) for x in line_ids.strip('{}').split(',') if x]
            
            if line_ids:
                self.env.cr.execute("""
                    SELECT 
                        aml.id,
                        aml.move_id,
                        am.name as move_name,
                        aml.ref,
                        aml.date,
                        aml.debit,
                        aml.credit,
                        aml.balance
                    FROM account_move_line aml
                    JOIN account_move am ON am.id = aml.move_id
                    WHERE aml.id = ANY(%s)
                    ORDER BY aml.date, aml.id
                """, (line_ids,))
                acc['lines'] = self.env.cr.dictfetchall()
            else:
                acc['lines'] = []
        
        return results

    def _is_current_account(self, account):
        """Determine if account is current (typically receivable/payable/cash)."""
        current_codes = ['10', '11', '12', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '40', '41', '42', '43', '44', '45', '46', '47', '48', '49', '50', '51', '52', '53', '54', '58', '59', '60', '61', '62', '63', '64', '65', '66', '67', '68', '69', '70', '71', '72', '73', '74', '75', '76', '77', '78', '79', '80', '81', '82', '83', '84', '85', '86', '87', '88', '89', '90', '91', '92', '93', '94', '95', '96', '97', '98', '99']
        return account['code'][:2] in current_codes

    def get_balance_sheet_data(self, date_from=None, date_to=None, target_move=None, company_id=None, account_range_type='all', show_unposted=False, show_zero=False):
        """Get formatted balance sheet data with optional parameters."""
        # Use current record if available, otherwise create temp
        if self:
            self.ensure_one()
            date_from = date_from or self.date_from
            date_to = date_to or self.date_to
            target_move = target_move or self.target_move
            company_id = company_id or self.company_id
        
        if not company_id:
            company_id = self.env.company
        
        accounts_data = self._get_account_balances_with_lines(date_from, date_to, target_move, company_id)
        
        # Filter accounts if needed
        if account_range_type == 'balance':
            balance_codes = [str(i) for i in list(range(10, 50)) + list(range(50, 60)) + list(range(60, 70))]
            accounts_data = [acc for acc in accounts_data if acc['code'][:2] in balance_codes]
        elif account_range_type == 'profit':
            profit_codes = [str(i) for i in list(range(70, 100))]
            accounts_data = [acc for acc in accounts_data if acc['code'][:2] in profit_codes]
        
        # Group accounts by internal_group
        assets_current = []
        assets_non_current = []
        liabilities_current = []
        liabilities_non_current = []
        equity = []
        
        for acc in accounts_data:
            if not show_zero and acc['balance'] == 0:
                continue
            
            account_info = {
                'code': acc['code'],
                'name': acc['name'],
                'balance': float(acc['balance']) if acc['balance'] else 0.0,
                'debit': float(acc['debit']) if acc['debit'] else 0.0,
                'credit': float(acc['credit']) if acc['credit'] else 0.0,
                'currency_id': acc['currency_id'],
                'lines': acc.get('lines', []),  # Detail transaksi
            }
            
            if acc['internal_group'] == 'asset':
                if self._is_current_account(acc):
                    assets_current.append(account_info)
                else:
                    assets_non_current.append(account_info)
            elif acc['internal_group'] == 'liability':
                if self._is_current_account(acc):
                    liabilities_current.append(account_info)
                else:
                    liabilities_non_current.append(account_info)
            elif acc['internal_group'] == 'equity':
                equity.append(account_info)
        
        # Calculate totals
        total_assets_current = sum(a['balance'] for a in assets_current)
        total_assets_non_current = sum(a['balance'] for a in assets_non_current)
        total_liabilities_current = sum(a['balance'] for a in liabilities_current)
        total_liabilities_non_current = sum(a['balance'] for a in liabilities_non_current)
        total_equity = sum(a['balance'] for a in equity)
        
        return {
            'assets_current': assets_current,
            'assets_non_current': assets_non_current,
            'liabilities_current': liabilities_current,
            'liabilities_non_current': liabilities_non_current,
            'equity': equity,
            'totals': {
                'assets_current': total_assets_current,
                'assets_non_current': total_assets_non_current,
                'total_assets': total_assets_current + total_assets_non_current,
                'liabilities_current': total_liabilities_current,
                'liabilities_non_current': total_liabilities_non_current,
                'total_liabilities': total_liabilities_current + total_liabilities_non_current,
                'total_equity': total_equity,
                'total_liabilities_equity': total_liabilities_current + total_liabilities_non_current + total_equity,
            },
            'date_from': str(date_from),
            'date_to': str(date_to),
            'company_name': company_id.name if company_id else '',
        }
