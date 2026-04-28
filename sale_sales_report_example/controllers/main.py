import io
import json
from datetime import date, datetime, timedelta

from odoo import http
from odoo.http import request

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class SalesReportExampleController(http.Controller):
    def _build_where_clause(self, date_from=None, date_to=None, search_term=None):
        clauses = [
            "so.state = ANY(%s)",
            "sol.display_type IS NULL",
        ]
        params = [["sale", "done"]]

        if date_from:
            clauses.append("so.date_order::date >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("so.date_order::date <= %s")
            params.append(date_to)

        if search_term:
            like_term = f"%{search_term}%"
            clauses.append(
                """(
                    so.name ILIKE %s
                    OR COALESCE(rp_customer.name, '') ILIKE %s
                    OR COALESCE(sol.name, '') ILIKE %s
                    OR COALESCE(rp_salesperson.name, '') ILIKE %s
                )"""
            )
            params.extend([like_term, like_term, like_term, like_term])

        return " AND ".join(clauses), params

    def _fetch_report_rows(self, date_from=None, date_to=None, search_term=None, order_direction="DESC"):
        where_clause, params = self._build_where_clause(
            date_from=date_from,
            date_to=date_to,
            search_term=search_term,
        )
        direction = "ASC" if str(order_direction).upper() == "ASC" else "DESC"
        query = f"""
            SELECT
                so.id AS order_id,
                so.name AS ref,
                so.company_id AS company_id,
                COALESCE(rp_customer.name, '') AS customer,
                COALESCE(sol.name, '') AS product,
                sol.product_id AS product_id,
                COALESCE(rp_salesperson.name, '') AS salesperson,
                COALESCE(sol.product_uom_qty, 0.0) AS qty,
                COALESCE(sol.price_unit, 0.0) AS price_unit,
                COALESCE(sol.price_subtotal, 0.0) AS subtotal,
                so.date_order::date AS date_order_value,
                TO_CHAR(so.date_order::date, 'DD/MM/YYYY') AS date_order
            FROM sale_order_line sol
            JOIN sale_order so ON so.id = sol.order_id
            LEFT JOIN res_partner rp_customer ON rp_customer.id = so.partner_id
            LEFT JOIN res_users ru ON ru.id = so.user_id
            LEFT JOIN res_partner rp_salesperson ON rp_salesperson.id = ru.partner_id
            WHERE {where_clause}
            ORDER BY so.date_order {direction}, so.id {direction}, sol.id ASC
        """
        request.env.cr.execute(query, params)
        rows = request.env.cr.dictfetchall()
        self._attach_costs_with_orm(rows)
        return rows

    def _attach_costs_with_orm(self, rows):
        if not rows:
            return

        product_ids = {row["product_id"] for row in rows if row.get("product_id")}
        if not product_ids:
            for row in rows:
                row["cost_unit"] = 0.0
                row["cost_total"] = 0.0
                row["margin"] = row["subtotal"]
            return

        products = request.env["product.product"].sudo().browse(list(product_ids)).exists()
        product_map = {product.id: product for product in products}

        cost_cache = {}
        for row in rows:
            product_id = row.get("product_id")
            company_id = row.get("company_id")
            qty = row.get("qty") or 0.0

            if not product_id or product_id not in product_map:
                cost_unit = 0.0
            else:
                cache_key = (product_id, company_id)
                if cache_key not in cost_cache:
                    product = product_map[product_id]
                    cost_cache[cache_key] = product.with_company(company_id).standard_price or 0.0
                cost_unit = cost_cache[cache_key]

            cost_total = cost_unit * qty
            row["cost_unit"] = cost_unit
            row["cost_total"] = cost_total
            row["margin"] = row["subtotal"] - cost_total

    def _get_group_value(self, row, key):
        mapping = {
            "customer": row["customer"] or "No Customer",
            "salesperson": row["salesperson"] or "No Salesperson",
            "order": row["ref"] or "No Reference",
            "product": row["product"] or "No Product",
        }
        return mapping.get(key, "Other")

    def _build_report_payload(self, rows, groupby):
        report_data = {}
        all_lines = list(rows)

        if not groupby:
            return report_data, all_lines

        for row in rows:
            current_level = report_data
            active_keys = [self._get_group_value(row, key) for key in groupby]
            for index, value in enumerate(active_keys):
                if value not in current_level:
                    current_level[value] = {"total": 0.0, "margin": 0.0, "children": {}, "lines": []}

                current_level[value]["total"] += row["subtotal"]
                current_level[value]["margin"] += row["margin"]

                if index == len(active_keys) - 1:
                    current_level[value]["lines"].append(row)
                else:
                    current_level = current_level[value]["children"]

        return report_data, all_lines

    def _build_summary(self, rows):
        order_ids = {row["order_id"] for row in rows}
        return {
            "total_sales": sum(row["subtotal"] for row in rows),
            "total_cost": sum(row["cost_total"] for row in rows),
            "total_margin": sum(row["margin"] for row in rows),
            "total_qty": sum(row["qty"] for row in rows),
            "total_orders": len(order_ids),
            "total_lines": len(rows),
        }

    def _format_period_label(self, date_from=None, date_to=None):
        months = {
            1: "Januari",
            2: "Februari",
            3: "Maret",
            4: "April",
            5: "Mei",
            6: "Juni",
            7: "Juli",
            8: "Agustus",
            9: "September",
            10: "Oktober",
            11: "November",
            12: "Desember",
        }

        def format_indo(value):
            if not value:
                return False
            if isinstance(value, str):
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    return value
            return f"{value.day} {months[value.month]} {value.year}"

        if date_from and date_to:
            return f"{format_indo(date_from)} - {format_indo(date_to)}"
        if date_from:
            return f"Mulai {format_indo(date_from)}"
        if date_to:
            return f"Hingga {format_indo(date_to)}"
        return f"Hari Ini ({format_indo(date.today())})"

    def _get_bucket_key_and_label(self, order_date, granularity):
        if granularity == "week":
            iso_year, iso_week, _ = order_date.isocalendar()
            return f"{iso_year}-W{iso_week:02d}", f"Week {iso_week:02d}, {iso_year}"
        if granularity == "year":
            return str(order_date.year), str(order_date.year)
        return f"{order_date.year}-{order_date.month:02d}", order_date.strftime("%b %Y")

    def _get_bucket_range(self, order_date, granularity):
        if granularity == "week":
            start_date = order_date - timedelta(days=order_date.weekday())
            end_date = start_date + timedelta(days=6)
            return start_date, end_date
        if granularity == "year":
            return date(order_date.year, 1, 1), date(order_date.year, 12, 31)

        start_date = date(order_date.year, order_date.month, 1)
        if order_date.month == 12:
            end_date = date(order_date.year, 12, 31)
        else:
            end_date = date(order_date.year, order_date.month + 1, 1) - timedelta(days=1)
        return start_date, end_date

    def _build_chart_payload(self, rows, granularity="month"):
        buckets = {}

        for row in rows:
            order_date = row["date_order_value"]
            if not order_date:
                continue

            bucket_key, bucket_label = self._get_bucket_key_and_label(order_date, granularity)
            bucket_start, bucket_end = self._get_bucket_range(order_date, granularity)
            bucket = buckets.setdefault(
                bucket_key,
                {
                    "label": bucket_label,
                    "date_from": bucket_start.isoformat(),
                    "date_to": bucket_end.isoformat(),
                    "sales": 0.0,
                    "cost": 0.0,
                    "margin": 0.0,
                    "orders": set(),
                },
            )

            bucket["sales"] += row["subtotal"]
            bucket["cost"] += row["cost_total"]
            bucket["margin"] += row["margin"]
            bucket["orders"].add(row["order_id"])

        labels = []
        sales_values = []
        cost_values = []
        margin_values = []
        ratio_values = []
        order_counts = []
        bucket_ranges = []

        for key in sorted(buckets.keys()):
            bucket = buckets[key]
            sales = bucket["sales"]
            margin = bucket["margin"]
            ratio = (margin / sales * 100.0) if sales else 0.0

            labels.append(bucket["label"])
            sales_values.append(round(sales, 2))
            cost_values.append(round(bucket["cost"], 2))
            margin_values.append(round(margin, 2))
            ratio_values.append(round(ratio, 2))
            order_counts.append(len(bucket["orders"]))
            bucket_ranges.append({
                "label": bucket["label"],
                "date_from": bucket["date_from"],
                "date_to": bucket["date_to"],
            })

        return {
            "labels": labels,
            "sales": sales_values,
            "cost": cost_values,
            "margin": margin_values,
            "ratio": ratio_values,
            "orders": order_counts,
            "buckets": bucket_ranges,
            "summary": {
                "best_ratio": max(ratio_values) if ratio_values else 0.0,
                "best_sales": max(sales_values) if sales_values else 0.0,
                "total_sales": round(sum(sales_values), 2),
                "avg_ratio": round(sum(ratio_values) / len(ratio_values), 2) if ratio_values else 0.0,
            },
        }

    @http.route("/sales_report_example/report_html", type="json", auth="user")
    def get_report_html(self, groupby=None, date_from=None, date_to=None, search_term=None, **kwargs):
        groupby = groupby if groupby is not None else ["customer"]
        rows = self._fetch_report_rows(
            date_from=date_from,
            date_to=date_to,
            search_term=search_term,
            order_direction="DESC",
        )
        report_data, all_lines = self._build_report_payload(rows, groupby)
        summary = self._build_summary(rows)

        return request.env["ir.ui.view"]._render_template(
            "sale_sales_report_example.report_sales_html_screen",
            {
                "report_data": report_data,
                "all_lines": all_lines,
                "summary": summary,
                "active_groups": groupby,
                "date_from": date_from,
                "date_to": date_to,
                "search_term": search_term or "",
                "periode_label": self._format_period_label(date_from, date_to),
            },
        )

    @http.route("/sales_report_example/chart_data", type="json", auth="user")
    def get_chart_data(self, granularity="month", date_from=None, date_to=None, search_term=None, **kwargs):
        granularity = granularity if granularity in {"week", "month", "year"} else "month"
        rows = self._fetch_report_rows(
            date_from=date_from,
            date_to=date_to,
            search_term=search_term,
            order_direction="ASC",
        )
        return self._build_chart_payload(rows, granularity=granularity)

    @http.route("/sales_report_example/export_excel", type="http", auth="user")
    def export_excel(self, groupby=None, date_from=None, date_to=None, search_term=None, **kwargs):
        if xlsxwriter is None:
            return request.not_found()

        groupby = json.loads(groupby) if groupby else []
        rows = self._fetch_report_rows(
            date_from=date_from,
            date_to=date_to,
            search_term=search_term,
            order_direction="DESC",
        )
        report_data, all_lines = self._build_report_payload(rows, groupby)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Sales Report")

        head_fmt = workbook.add_format({"bold": True, "bg_color": "#1d4ed8", "font_color": "#FFFFFF", "border": 1})
        group_fmt = workbook.add_format({"bold": True, "bg_color": "#e2e8f0", "border": 1})
        text_fmt = workbook.add_format({"border": 1})
        money_fmt = workbook.add_format({"border": 1, "num_format": "#,##0.00"})

        headers = [
            "Reference / Group",
            "Date",
            "Customer",
            "Product",
            "Salesperson",
            "Qty",
            "Cost",
            "Unit Price",
            "Sales",
            "Margin",
        ]
        for col, header in enumerate(headers):
            sheet.write(0, col, header, head_fmt)

        row_number = 1

        def write_line(row_idx, line, indent=""):
            sheet.write(row_idx, 0, f"{indent}{line['ref']}", text_fmt)
            sheet.write(row_idx, 1, line["date_order"], text_fmt)
            sheet.write(row_idx, 2, line["customer"], text_fmt)
            sheet.write(row_idx, 3, line["product"], text_fmt)
            sheet.write(row_idx, 4, line["salesperson"], text_fmt)
            sheet.write(row_idx, 5, line["qty"], text_fmt)
            sheet.write(row_idx, 6, line["cost_total"], money_fmt)
            sheet.write(row_idx, 7, line["price_unit"], money_fmt)
            sheet.write(row_idx, 8, line["subtotal"], money_fmt)
            sheet.write(row_idx, 9, line["margin"], money_fmt)

        def write_nodes(nodes, level=0):
            nonlocal row_number
            for key in sorted(nodes.keys()):
                sheet.write(row_number, 0, f"{'    ' * level}{key}", group_fmt)
                sheet.write(row_number, 8, nodes[key]["total"], group_fmt)
                sheet.write(row_number, 9, nodes[key]["margin"], group_fmt)
                row_number += 1
                if nodes[key]["children"]:
                    write_nodes(nodes[key]["children"], level + 1)
                for line in nodes[key]["lines"]:
                    write_line(row_number, line, indent="    " * (level + 1))
                    row_number += 1

        if groupby:
            write_nodes(report_data)
        else:
            for line in all_lines:
                write_line(row_number, line)
                row_number += 1

        sheet.set_column(0, 0, 28)
        sheet.set_column(1, 1, 14)
        sheet.set_column(2, 4, 24)
        sheet.set_column(5, 9, 14)

        workbook.close()
        output.seek(0)
        file_name = f"sales_report_example_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return request.make_response(
            output.read(),
            [
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Disposition", f"attachment; filename={file_name}"),
            ],
        )
