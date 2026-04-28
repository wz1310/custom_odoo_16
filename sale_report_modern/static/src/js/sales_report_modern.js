/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, useState, markup } = owl;

export class SalesReportModern extends Component {
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
            await this.fetchReport();
        });
    }

    async fetchReport() {
        this.state.loading = true;
        try {
            const data = await this.rpc("/sale_report_modern/data", {
                groupby: [...this.state.groupby],
                date_from: this.state.date_from,
                date_to: this.state.date_to,
            });
            this.state.html_content = markup(data);
        } catch (e) {
            console.error("SalesReportModern RPC error:", e);
        } finally {
            this.state.loading = false;
        }
    }

    handleClick(ev) {
        const t = ev.target;

        // Export Excel
        if (t.closest(".js_export_excel")) {
            this._exportExcel();
            return;
        }

        // Apply filter button
        if (t.closest(".js_apply_filter")) {
            this._readDateInputs();
            this.fetchReport();
            return;
        }

        // Date input change — attach onchange lazily
        if (t.tagName === "INPUT" && (t.name === "date_from" || t.name === "date_to")) {
            t.onchange = (e) => {
                this.state[e.target.name] = e.target.value;
            };
            return;
        }

        // Toggle dropdown
        if (t.closest(".js_toggle_dropdown")) {
            const menu = document.getElementById("srm_group_dropdown");
            if (menu) menu.classList.toggle("open");
            return;
        }

        // Add groupby
        const addBtn = t.closest(".js_add_groupby");
        if (addBtn) {
            const val = addBtn.getAttribute("data-groupby");
            if (val && !this.state.groupby.includes(val)) {
                this.state.groupby = [...this.state.groupby, val];
                this.fetchReport();
            }
            const menu = document.getElementById("srm_group_dropdown");
            if (menu) menu.classList.remove("open");
            return;
        }

        // Remove groupby
        const removeBtn = t.closest(".js_remove_groupby");
        if (removeBtn) {
            const val = removeBtn.getAttribute("data-groupby");
            this.state.groupby = this.state.groupby.filter((g) => g !== val);
            this.fetchReport();
            return;
        }

        // Expand / collapse group row
        const groupRow = t.closest(".srm-clickable");
        if (groupRow) {
            const id = groupRow.getAttribute("data-id");
            if (!id) return;
            if (groupRow.classList.contains("expanded")) {
                groupRow.classList.remove("expanded");
                this._hideChildren(id);
            } else {
                groupRow.classList.add("expanded");
                document.querySelectorAll(`.child-of-${id}`).forEach((el) => {
                    el.style.setProperty("display", "table-row", "important");
                });
            }
            return;
        }

        // Close dropdown when clicking outside
        const menu = document.getElementById("srm_group_dropdown");
        if (menu && !t.closest(".srm-dropdown")) {
            menu.classList.remove("open");
        }
    }

    _hideChildren(parentId) {
        document.querySelectorAll(`.child-of-${parentId}`).forEach((el) => {
            el.style.setProperty("display", "none", "important");
            el.classList.remove("expanded");
            const childId = el.getAttribute("data-id");
            if (childId) this._hideChildren(childId);
        });
    }

    _readDateInputs() {
        const df = document.querySelector('input[name="date_from"]');
        const dt = document.querySelector('input[name="date_to"]');
        if (df) this.state.date_from = df.value;
        if (dt) this.state.date_to = dt.value;
    }

    _exportExcel() {
        const groupby = JSON.stringify(this.state.groupby);
        const date_from = this.state.date_from || "";
        const date_to = this.state.date_to || "";
        window.location.href = `/sale_report_modern/export_excel?groupby=${encodeURIComponent(groupby)}&date_from=${date_from}&date_to=${date_to}`;
    }
}

SalesReportModern.template = "sale_report_modern.client_template";
registry.category("actions").add("sale_report_modern.client_action", SalesReportModern);
