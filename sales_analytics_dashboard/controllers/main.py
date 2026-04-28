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

    def _get_analytics_data_sql(self, date_from=None, date_to=None, company_ids=None, groupby=None):
        """Fetch analytics data using optimized SQL query"""
        query = """
            SELECT 
                so.id as order_id,
                so.name as order_name,
                so.date_order,
                rp.name as customer,
                so.partner_id as customer_id,
                pt.name as product,
                pp.id as product_id,
                ru_partner.name as salesperson,
                so.user_id as salesperson_id,
                st.name as team,
                sol.product_uom_qty as qty,
                sol.price_unit,
                sol.price_subtotal as subtotal,
                pc.name as category
            FROM sale_order_line sol
            JOIN sale_order so ON sol.order_id = so.id
            JOIN res_partner rp ON so.partner_id = rp.id
            JOIN product_product pp ON sol.product_id = pp.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            LEFT JOIN res_users ru ON so.user_id = ru.id
            LEFT JOIN res_partner ru_partner ON ru.partner_id = ru_partner.id
            LEFT JOIN crm_team st ON so.team_id = st.id
            LEFT JOIN product_category pc ON pt.categ_id = pc.id
            WHERE so.state IN ('sale', 'done')
        """
        params = []

        if date_from:
            query += " AND so.date_order >= %s"
            params.append(date_from)
        if date_to:
            query += " AND so.date_order <= %s"
            params.append(date_to)
        if company_ids:
            query += " AND so.company_id IN %s"
            params.append(tuple(company_ids))

        query += " ORDER BY so.date_order DESC"
        
        request.env.cr.execute(query, params)
        results = request.env.cr.dictfetchall()

        # Fetch product costs via ORM (since standard_price is a property field)
        product_ids = list(set(row['product_id'] for row in results))
        product_costs = {p['id']: p['standard_price'] for p in request.env['product.product'].sudo().browse(product_ids).read(['standard_price'])}

        # Build analytics tree and KPIs from SQL results
        analytics_data = {}
        all_lines = []
        total_revenue = 0.0
        total_qty = 0.0
        customer_set = set()
        product_set = set()
        order_set = set()
        total_margin = 0.0

        for row in results:
            cost = product_costs.get(row['product_id'], 0.0)
            margin = row['subtotal'] - (row['qty'] * cost)
            
            # Normalize translatable fields
            customer_name = row['customer']
            if isinstance(customer_name, dict):
                customer_name = customer_name.get(request.env.lang) or list(customer_name.values())[0] if customer_name else 'Unknown'
            
            product_name = row['product']
            if isinstance(product_name, dict):
                product_name = product_name.get(request.env.lang) or list(product_name.values())[0] if product_name else 'Unknown'
            
            category_name = row['category']
            if isinstance(category_name, dict):
                category_name = category_name.get(request.env.lang) or list(category_name.values())[0] if category_name else 'Uncategorized'
            
            salesperson_name = row['salesperson']
            if isinstance(salesperson_name, dict):
                salesperson_name = salesperson_name.get(request.env.lang) or list(salesperson_name.values())[0] if salesperson_name else 'Unassigned'
            
            team_name = row['team']
            if isinstance(team_name, dict):
                team_name = team_name.get(request.env.lang) or list(team_name.values())[0] if team_name else 'General'

            customer_set.add(row['customer_id'])
            product_set.add(row['product_id'])
            order_set.add(row['order_id'])
            total_revenue += row['subtotal']
            total_qty += row['qty']
            total_margin += margin

            line_info = {
                'order_id': row['order_id'],
                'order_name': row['order_name'],
                'date_order': row['date_order'].strftime('%Y-%m-%d') if row['date_order'] else '',
                'customer': customer_name,
                'customer_id': row['customer_id'],
                'product': product_name,
                'product_id': row['product_id'],
                'salesperson': salesperson_name,
                'salesperson_id': row['salesperson_id'],
                'team': team_name,
                'category': category_name,
                'qty': row['qty'],
                'price_unit': row['price_unit'],
                'subtotal': row['subtotal'],
                'margin': margin,
                'margin_pct': (margin / row['subtotal'] * 100) if row['subtotal'] > 0 else 0,
            }
            all_lines.append(line_info)

            if groupby:
                active_keys = []
                for key in groupby:
                    # Map the groupby key to the normalized name
                    if key == 'customer': key_val = customer_name
                    elif key == 'product': key_val = product_name
                    elif key == 'category': key_val = category_name
                    elif key == 'salesperson': key_val = salesperson_name
                    elif key == 'team': key_val = team_name
                    else: key_val = row.get(key) or 'Unknown'
                    
                    if isinstance(key_val, dict):
                        key_val = key_val.get(request.env.lang) or list(key_val.values())[0] if key_val else 'Unknown'
                    active_keys.append(key_val)
                
                current_level = analytics_data
                for i, key_val in enumerate(active_keys):
                    if key_val not in current_level:
                        current_level[key_val] = {
                            'total': 0.0, 
                            'qty': 0.0, 
                            'margin': 0.0,
                            'children': {}, 
                            'lines': [],
                            'order_ids': set()
                        }
                    current_level[key_val]['total'] += row['subtotal']
                    current_level[key_val]['qty'] += row['qty']
                    current_level[key_val]['margin'] += margin
                    current_level[key_val]['order_ids'].add(row['order_id'])
                    
                    if i == len(active_keys) - 1:
                        current_level[key_val]['lines'].append(line_info)
                    else:
                        current_level = current_level[key_val]['children']

        # Convert order sets to counts
        def _convert_order_sets(node):
            if 'order_ids' in node:
                node['order_count'] = len(node['order_ids'])
                del node['order_ids']
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
            'total_margin': total_margin,
        }
        
        return analytics_data, all_lines, kpi

    def _calculate_trends_sql(self, results, period='monthly'):
        """Calculate trends from SQL result set"""
        trends = {}
        for row in results:
            dt = row['date_order']
            if not dt: continue
            
            if period == 'monthly':
                key = dt.strftime('%Y-%m')
            elif period == 'weekly':
                key = dt.strftime('%Y-W%W')
            else:
                key = dt.strftime('%Y-%m-%d')
                
            if key not in trends:
                trends[key] = {'revenue': 0, 'orders': 0, 'qty': 0}
                
            trends[key]['revenue'] += row['subtotal']
            trends[key]['orders'] += 1 # This is per line, might need adjustment for unique orders
            trends[key]['qty'] += row['qty']
            
        return dict(sorted(trends.items()))

    @http.route('/sales_analytics/data', type='json', auth='user', methods=['POST'])
    def get_analytics_data(self, groupby=None, date_from=None, date_to=None, 
                          company_ids=None, **kw):
        """Get analytics data with optimized SQL filtering"""
        if groupby is None:
            groupby = ['customer']
        
        if isinstance(company_ids, str):
            try:
                company_ids = json.loads(company_ids)
            except:
                company_ids = None

        # Fetch using optimized SQL
        analytics_data, all_lines, kpi = self._get_analytics_data_sql(
            date_from=date_from, 
            date_to=date_to, 
            company_ids=company_ids, 
            groupby=groupby
        )
        
        # Calculate trends from same dataset
        # To get accurate order count for trends, we'd need unique order IDs per period
        trends = {}
        for row in all_lines: # all_lines is processed from SQL results
            dt_str = row['date_order']
            if not dt_str: continue
            key = dt_str[:7] # YYYY-MM
            if key not in trends:
                trends[key] = {'revenue': 0, 'orders': set(), 'qty': 0}
            trends[key]['revenue'] += row['subtotal']
            trends[key]['orders'].add(row['order_id'])
            trends[key]['qty'] += row['qty']
        
        for k in trends:
            trends[k]['orders'] = len(trends[k]['orders'])

        # Top customers by revenue
        customer_totals = {}
        for line in all_lines:
            c = line['customer']
            if isinstance(c, dict):
                c = c.get(request.env.lang) or list(c.values())[0] if c else 'Unknown'
            customer_totals[c] = customer_totals.get(c, 0) + line['subtotal']
        top_customers = sorted(customer_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Top products
        product_totals = {}
        for line in all_lines:
            p = line['product']
            if isinstance(p, dict):
                p = p.get(request.env.lang) or list(p.values())[0] if p else 'Unknown'
            product_totals[p] = product_totals.get(p, 0) + line['subtotal']
        top_products = sorted(product_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Sales by category
        category_totals = {}
        for line in all_lines:
            cat = line.get('category') or 'Uncategorized'
            if isinstance(cat, dict):
                cat = cat.get(request.env.lang) or list(cat.values())[0] if cat else 'Uncategorized'
            category_totals[cat] = category_totals.get(cat, 0) + line['subtotal']
        top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:5]

        period_label = f"{date_from or 'Start'} to {date_to or 'Now'}"

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
        """Export analytics to Excel using optimized data fetching"""
        groupby_list = json.loads(groupby) if groupby else []
        
        if isinstance(company_ids, str):
            try:
                company_ids = json.loads(company_ids)
            except:
                company_ids = None

        analytics_data, all_lines, kpi = self._get_analytics_data_sql(
            date_from=date_from, 
            date_to=date_to, 
            company_ids=company_ids, 
            groupby=groupby_list
        )

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
