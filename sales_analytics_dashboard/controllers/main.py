from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
import json
import io
import base64

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

try:
    from odoo.tools import pdf
except ImportError:
    pdf = None


class SalesAnalyticsController(http.Controller):

    def _get_advanced_domain(self, date_from=None, date_to=None, customer_ids=None, product_ids=None, team_ids=None, company_ids=None):
        """Build advanced domain with multiple filter options"""
        domain = [('state', 'in', ['sale', 'done'])]
        
        if date_from:
            domain.append(('date_order', '>=', date_from))
        if date_to:
            domain.append(('date_order', '<=', date_to))
        if customer_ids:
            domain.append(('partner_id', 'in', customer_ids))
        if product_ids:
            domain.append(('order_line.product_id', 'in', product_ids))
        if team_ids:
            domain.append(('team_id', 'in', team_ids))
        if company_ids:
            domain.append(('company_id', 'in', company_ids))
            
        return domain

    def _calculate_trends(self, orders, period='monthly'):
        """Calculate sales trends over time"""
        trends = {}
        for order in orders:
            if period == 'monthly':
                key = order.date_order.strftime('%Y-%m')
            elif period == 'weekly':
                key = order.date_order.strftime('%Y-W%W')
            else:
                key = order.date_order.strftime('%Y-%m-%d')
                
            if key not in trends:
                trends[key] = {'revenue': 0, 'orders': 0, 'qty': 0}
                
            trends[key]['revenue'] += sum(order.order_line.mapped('price_subtotal'))
            trends[key]['orders'] += 1
            trends[key]['qty'] += sum(order.order_line.mapped('product_uom_qty'))
            
        return dict(sorted(trends.items()))

    def _build_analytics_tree(self, orders, groupby):
        """Build hierarchical analytics data tree"""
        analytics_data = {}
        all_lines = []
        total_revenue = 0.0
        total_qty = 0.0
        customer_set = set()
        product_set = set()
        order_set = set()

        for order in orders:
            customer_set.add(order.partner_id.id)
            order_set.add(order.id)
            
            for line in order.order_line:
                total_revenue += line.price_subtotal
                total_qty += line.product_uom_qty
                
                line_info = {
                    'order_id': order.id,
                    'order_name': order.name,
                    'date_order': order.date_order.strftime('%Y-%m-%d') if order.date_order else '',
                    'customer': order.partner_id.name or 'Unknown',
                    'customer_id': order.partner_id.id,
                    'product': line.product_id.display_name or 'Unknown',
                    'product_id': line.product_id.id,
                    'salesperson': order.user_id.name or 'Unassigned',
                    'salesperson_id': order.user_id.id,
                    'team': order.team_id.name if order.team_id else 'General',
                    'qty': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'subtotal': line.price_subtotal,
                    'margin': line.price_subtotal - (line.product_uom_qty * line.product_id.standard_price),
                    'margin_pct': ((line.price_subtotal - (line.product_uom_qty * line.product_id.standard_price)) / line.price_subtotal * 100) if line.price_subtotal > 0 else 0,
                }
                all_lines.append(line_info)
                product_set.add(line.product_id.id)

                if groupby:
                    active_keys = []
                    for key in groupby:
                        if key == 'customer':
                            active_keys.append(order.partner_id.name or 'Unknown')
                        elif key == 'product':
                            active_keys.append(line.product_id.display_name or 'Unknown')
                        elif key == 'salesperson':
                            active_keys.append(order.user_id.name or 'Unassigned')
                        elif key == 'team':
                            active_keys.append(order.team_id.name if order.team_id else 'General')
                        elif key == 'category':
                            active_keys.append(line.product_id.categ_id.name or 'Uncategorized')
                        else:
                            active_keys.append('Other')
                    
                    current_level = analytics_data
                    for i, key_val in enumerate(active_keys):
                        if key_val not in current_level:
                            current_level[key_val] = {
                                'total': 0.0, 
                                'qty': 0.0, 
                                'margin': 0.0,
                                'children': {}, 
                                'lines': [],
                                'orders': set()
                            }
                        current_level[key_val]['total'] += line.price_subtotal
                        current_level[key_val]['qty'] += line.product_uom_qty
                        current_level[key_val]['margin'] += line_info['margin']
                        current_level[key_val]['orders'].add(order.id)
                        
                        if i == len(active_keys) - 1:
                            current_level[key_val]['lines'].append(line_info)
                        else:
                            current_level = current_level[key_val]['children']

        # Convert order sets to counts
        def _convert_order_sets(node):
            if 'orders' in node:
                node['order_count'] = len(node['orders'])
                del node['orders']
            for child in node.get('children', {}).values():
                _convert_order_sets(child)
        
        _convert_order_sets(analytics_data)

        kpi = {
            'total_revenue': total_revenue,
            'total_orders': len(order_set),
            'total_customers': len(customer_set),
            'total_products': len(product_set),
            'total_qty': total_qty,
            'avg_order_value': total_revenue / len(order_set) if order_set else 0,
            'total_margin': sum(l['margin'] for l in all_lines),
        }
        
        return analytics_data, all_lines, kpi

    @http.route('/sales_analytics/data', type='json', auth='user', methods=['POST'])
    def get_analytics_data(self, groupby=None, date_from=None, date_to=None, 
                          customer_ids=None, product_ids=None, team_ids=None, company_ids=None, **kw):
        """Get analytics data with advanced filtering"""
        if groupby is None:
            groupby = ['customer']
        
        # Parse JSON arrays
        if isinstance(customer_ids, str):
            try:
                customer_ids = json.loads(customer_ids)
            except:
                customer_ids = None
        if isinstance(product_ids, str):
            try:
                product_ids = json.loads(product_ids)
            except:
                product_ids = None
        if isinstance(team_ids, str):
            try:
                team_ids = json.loads(team_ids)
            except:
                team_ids = None
        if isinstance(company_ids, str):
            try:
                company_ids = json.loads(company_ids)
            except:
                company_ids = None

        domain = self._get_advanced_domain(date_from, date_to, customer_ids, product_ids, team_ids, company_ids)
        orders = request.env['sale.order'].sudo().search(domain, order='date_order desc')
        
        analytics_data, all_lines, kpi = self._build_analytics_tree(orders, groupby)
        trends = self._calculate_trends(orders, 'monthly')
        
        # Top customers by revenue
        customer_totals = {}
        for line in all_lines:
            c = line['customer']
            customer_totals[c] = customer_totals.get(c, 0) + line['subtotal']
        top_customers = sorted(customer_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Top products
        product_totals = {}
        for line in all_lines:
            p = line['product']
            product_totals[p] = product_totals.get(p, 0) + line['subtotal']
        top_products = sorted(product_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Sales by category
        category_totals = {}
        for line in all_lines:
            cat = request.env['product.product'].browse(line['product_id']).categ_id.name
            category_totals[cat] = category_totals.get(cat, 0) + line['subtotal']
        top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]

        if date_from and date_to:
            period_label = f"{date_from} to {date_to}"
        elif date_from:
            period_label = f"From {date_from}"
        elif date_to:
            period_label = f"To {date_to}"
        else:
            period_label = "All Time"

        return {
            'analytics_data': analytics_data,
            'all_lines': all_lines,
            'active_groups': groupby,
            'date_from': date_from or '',
            'date_to': date_to or '',
            'period_label': period_label,
            'kpi': kpi,
            'top_customers': top_customers,
            'top_products': top_products,
            'top_categories': top_categories,
            'trends': trends,
        }

    @http.route('/sales_analytics/export_excel', type='http', auth='user', methods=['GET', 'POST'])
    def export_excel_advanced(self, groupby=None, date_from=None, date_to=None, company_ids=None, **kw):
        """Export analytics to Excel with hierarchical grouping"""
        groupby_list = json.loads(groupby) if groupby else []
        
        # Parse company_ids if passed as string
        if isinstance(company_ids, str):
            try:
                company_ids = json.loads(company_ids)
            except:
                company_ids = None

        domain = self._get_advanced_domain(date_from, date_to, company_ids=company_ids)
        orders = request.env['sale.order'].sudo().search(domain, order='date_order desc')
        analytics_data, all_lines, kpi = self._build_analytics_tree(orders, groupby_list)

        if not xlsxwriter:
            return request.make_response('xlsxwriter not installed', status=500)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # --- Formats ---
        title_fmt = workbook.add_format({'bold': True, 'font_size': 18, 'font_color': '#4f46e5', 'align': 'center'})
        subtitle_fmt = workbook.add_format({'italic': True, 'font_size': 12, 'font_color': '#64748b', 'align': 'center'})
        
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#4f46e5', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 11
        })
        
        group_fmt_list = [
            workbook.add_format({'bold': True, 'bg_color': '#eef2ff', 'border': 1, 'valign': 'vcenter', 'font_size': 12}),
            workbook.add_format({'bold': True, 'bg_color': '#f8fafc', 'border': 1, 'valign': 'vcenter', 'font_size': 11}),
            workbook.add_format({'bold': True, 'bg_color': '#ffffff', 'border': 1, 'valign': 'vcenter', 'font_size': 10}),
        ]
        
        normal_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        money_fmt = workbook.add_format({'num_format': '"Rp "#,##0', 'border': 1})
        money_bold_fmt = workbook.add_format({'num_format': '"Rp "#,##0', 'border': 1, 'bold': True})
        percent_fmt = workbook.add_format({'num_format': '0.00%', 'border': 1})
        date_fmt = workbook.add_format({'num_format': 'yyyy-mm-dd', 'border': 1})
        
        # --- Summary Sheet ---
        summary_sheet = workbook.add_worksheet('📊 Dashboard Summary')
        summary_sheet.merge_range('A1:D1', 'SALES ANALYTICS REPORT', title_fmt)
        summary_sheet.merge_range('A2:D2', f'Period: {date_from or "All Time"} to {date_to or "All Time"}', subtitle_fmt)
        
        kpi_headers = [
            ('Total Revenue', kpi['total_revenue'], money_bold_fmt),
            ('Total Orders', kpi['total_orders'], normal_fmt),
            ('Total Customers', kpi['total_customers'], normal_fmt),
            ('Total Quantity', kpi['total_qty'], normal_fmt),
            ('Avg Order Value', kpi['avg_order_value'], money_bold_fmt),
            ('Total Margin', kpi['total_margin'], money_bold_fmt),
        ]
        
        curr_row = 4
        for label, val, fmt in kpi_headers:
            summary_sheet.write(curr_row, 1, label, header_fmt)
            summary_sheet.write(curr_row, 2, val, fmt)
            curr_row += 1
            
        summary_sheet.set_column('B:C', 25)
        
        # --- Detail Sheet ---
        detail_sheet = workbook.add_worksheet('📝 Sales Detail')
        detail_sheet.freeze_panes(1, 0)
        
        headers = ['Reference', 'Date', 'Customer', 'Product', 'Salesperson', 'Team', 'Qty', 'Unit Price', 'Subtotal', 'Margin']
        for col, h in enumerate(headers):
            detail_sheet.write(0, col, h, header_fmt)
        
        self.row_counter = 1

        def _write_node(nodes, level, path=""):
            for key in sorted(nodes.keys()):
                node = nodes[key]
                fmt = group_fmt_list[min(level, len(group_fmt_list)-1)]
                
                # Write Group Header Row
                detail_sheet.set_row(self.row_counter, None, None, {'level': level, 'hidden': False})
                detail_sheet.write(self.row_counter, 0, f"{'  ' * level}📁 {key}", fmt)
                for c in range(1, 6): detail_sheet.write(self.row_counter, c, "", fmt)
                detail_sheet.write(self.row_counter, 6, node['qty'], fmt)
                detail_sheet.write(self.row_counter, 7, "-", fmt)
                detail_sheet.write(self.row_counter, 8, node['total'], money_bold_fmt)
                detail_sheet.write(self.row_counter, 9, node['margin'], money_bold_fmt)
                
                self.row_counter += 1
                
                # Subgroups
                if node.get('children'):
                    _write_node(node['children'], level + 1)
                
                # Lines
                if node.get('lines'):
                    for line in node['lines']:
                        detail_sheet.set_row(self.row_counter, None, None, {'level': level + 1, 'hidden': False})
                        detail_sheet.write(self.row_counter, 0, line['order_name'], normal_fmt)
                        detail_sheet.write(self.row_counter, 1, line['date_order'], date_fmt)
                        detail_sheet.write(self.row_counter, 2, line['customer'], normal_fmt)
                        detail_sheet.write(self.row_counter, 3, line['product'], normal_fmt)
                        detail_sheet.write(self.row_counter, 4, line['salesperson'], normal_fmt)
                        detail_sheet.write(self.row_counter, 5, line['team'], normal_fmt)
                        detail_sheet.write(self.row_counter, 6, line['qty'], normal_fmt)
                        detail_sheet.write(self.row_counter, 7, line['price_unit'], money_fmt)
                        detail_sheet.write(self.row_counter, 8, line['subtotal'], money_fmt)
                        detail_sheet.write(self.row_counter, 9, line['margin'], money_fmt)
                        self.row_counter += 1

        if groupby_list:
            _write_node(analytics_data, 0)
        else:
            # Flat list if no grouping
            for line in all_lines:
                detail_sheet.write(self.row_counter, 0, line['order_name'], normal_fmt)
                detail_sheet.write(self.row_counter, 1, line['date_order'], date_fmt)
                detail_sheet.write(self.row_counter, 2, line['customer'], normal_fmt)
                detail_sheet.write(self.row_counter, 3, line['product'], normal_fmt)
                detail_sheet.write(self.row_counter, 4, line['salesperson'], normal_fmt)
                detail_sheet.write(self.row_counter, 5, line['team'], normal_fmt)
                detail_sheet.write(self.row_counter, 6, line['qty'], normal_fmt)
                detail_sheet.write(self.row_counter, 7, line['price_unit'], money_fmt)
                detail_sheet.write(self.row_counter, 8, line['subtotal'], money_fmt)
                detail_sheet.write(self.row_counter, 9, line['margin'], money_fmt)
                self.row_counter += 1

        detail_sheet.set_column(0, 0, 25)
        detail_sheet.set_column(1, 1, 12)
        detail_sheet.set_column(2, 2, 25)
        detail_sheet.set_column(3, 3, 35)
        detail_sheet.set_column(4, 5, 20)
        detail_sheet.set_column(6, 6, 10)
        detail_sheet.set_column(7, 9, 15)
        
        workbook.close()
        output.seek(0)
        
        filename = f"Sales_Analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return request.make_response(output.read(), [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename={filename}')
        ])
