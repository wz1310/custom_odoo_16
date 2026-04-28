/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, useState, markup } = owl;

export class SalesReportClientAction extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            html_content: "",
            loading: true,
            groupby: ["customer"],
            date_from: "",
            date_to: "", 
        });

        onWillStart(async () => {
            await this.fetchReportHtml();
        });
    }

    async fetchReportHtml() {
        this.state.loading = true;
        try {
            // Gunakan spread operator agar Owl mendeteksi perubahan array
            const data = await this.rpc("/sales_report/report_html", {
                groupby: [...this.state.groupby],
                date_from: this.state.date_from,
                date_to: this.state.date_to,
            });
            
            this.state.html_content = markup(data);
            this.state.loading = false;
        } catch (error) {
            console.error("RPC Error:", error);
            this.state.loading = false;
        }
    }

    handleMainClick(ev) {
        const target = ev.target;

        // 1. Logika EXCEL
        if (target.closest('.js_export_excel')) {
            this.exportToExcel();
            return;
        }

        // 2. Logika FILTER TANGGAL (Pemicu Otomatis)
        // Kita tangkap jika user berinteraksi dengan input
        if (target.tagName === 'INPUT' && (target.name === 'date_from' || target.name === 'date_to')) {
            target.onchange = (e) => {
                this.state[e.target.name] = e.target.value;
                this.fetchReportHtml();
            };
            return; 
        }

        // 3. Logika GROUP BY (Tambah atau Hapus)
        const groupBtn = target.closest('.js_group_by, .js_remove_groupby, [data-group], [data-groupby]');
        if (groupBtn) {
            const val = groupBtn.getAttribute('data-group') || groupBtn.getAttribute('data-groupby');
            if (val) {
                let currentGroups = [...this.state.groupby];
                if (currentGroups.includes(val)) {
                    currentGroups = currentGroups.filter(g => g !== val);
                } else {
                    currentGroups.push(val);
                }
                this.state.groupby = currentGroups;
                this.fetchReportHtml();
                return;
            }
        }

        // 4. Logika UNFOLD/COLLAPSE
        const headerRow = target.closest('.row-clickable');
        if (headerRow) {
            const id = headerRow.getAttribute('data-id');
            if (!id) return;

            if (headerRow.classList.contains('is-expanded')) {
                headerRow.classList.remove('is-expanded');
                this._recursiveHide(id);
            } else {
                headerRow.classList.add('is-expanded');
                document.querySelectorAll(`.child-of-${id}`).forEach(c => {
                    c.style.setProperty('display', 'table-row', 'important');
                });
            }
            return;
        }
    }

    _recursiveHide(parentId) {
        const children = document.querySelectorAll(`.child-of-${parentId}`);
        children.forEach(c => {
            c.style.setProperty('display', 'none', 'important');
            c.classList.remove('is-expanded');
            const childId = c.getAttribute('data-id');
            if (childId) this._recursiveHide(childId);
        });
    }

    exportToExcel() {
        // const table = document.querySelector('.table-main');
        // if (!table) return;

        // let csvContent = "\uFEFF"; 
        // const rows = table.querySelectorAll("tr");
        // rows.forEach(row => {
        //     const style = window.getComputedStyle(row);
        //     if (style.display !== 'none') {
        //         const cols = row.querySelectorAll("th, td");
        //         const rowData = [];
        //         cols.forEach(col => {
        //             let text = col.innerText.replace(/\s+/g, ' ').replace(/[▸▾展开收起]/g, '').trim();
        //             rowData.push('"' + text.replace(/"/g, '""') + '"');
        //         });
        //         csvContent += rowData.join(",") + "\r\n";
        //     }
        // });

        // const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        // const link = document.createElement("a");
        // link.href = URL.createObjectURL(blob);
        // link.download = `Sales_Report_${new Date().getTime()}.csv`;
        // document.body.appendChild(link);
        // link.click();
        // document.body.removeChild(link);
        const groupby = JSON.stringify(this.state.groupby);
        const date_from = this.state.date_from || '';
        const date_to = this.state.date_to || '';

        // 2. Buat URL dengan query params
        const url = `/sales_report/export_excel?groupby=${groupby}&date_from=${date_from}&date_to=${date_to}`;

        // 3. Trigger download dengan window.location
        window.location.href = url;
    }
}

SalesReportClientAction.template = "sale_sales_report.sales_report_client_template";
registry.category("actions").add("sale_sales_report.sales_client_action", SalesReportClientAction);