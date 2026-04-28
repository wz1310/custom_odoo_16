{
    "name": "Sales Report Example",
    "version": "18.0.1.0",
    "summary": "Example sales report addon with grouping and Excel export",
    "depends": ["sale", "web"],
    "data": [
        "views/client_action.xml",
        "views/report_html_template.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sale_sales_report_example/static/src/js/sales_report_client.js",
            "sale_sales_report_example/static/src/xml/sales_report_client.xml",
        ],
    },
}
