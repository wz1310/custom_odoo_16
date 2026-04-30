/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, xml } from "@odoo/owl";

class BalanceSheetComponent extends Component {
    static template = "dynamic_balance_sheet_report.BalanceSheetComponentTemplate";
    static props = ["reportData", "expandedDetails", "toggleDetail"];

    formatAmount(amount) {
        if (amount === null || amount === undefined) return "0.00";
        return Number(amount).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }
}


export class BalanceSheetReport extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.companyService = useService("company");
        this.notification = useService("notification");
        this.toggleDetail = this.toggleDetail.bind(this);

        this.state = useState({
            loading: false,
            date: new Date().toISOString().slice(0, 10),
            date_filter_type: "today",
            target_move: "posted",
            company_id: null,
            companies: [],
            report_data: null,
            has_data: false,
            expandedDetails: new Set(),
        });

        onWillStart(async () => {
            await this.loadInitialData();
            this.state.date = new Date().toISOString().slice(0, 10);
        });
    }

    async loadInitialData() {
        try {
            const companies = await this.rpc("/web/dataset/call_kw", {
                model: "res.company",
                method: "search_read",
                args: [[], ["id", "name"]],
                kwargs: {},
            });
            this.state.companies = companies;

            const userCompany = await this.rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "read",
                args: [[this.companyService.currentCompany.id], ["company_id"]],
                kwargs: {},
            });
            if (userCompany && userCompany[0] && userCompany[0].company_id) {
                this.state.company_id = userCompany[0].company_id[0];
            }
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.notification.add('Failed to load initial data', { type: 'danger' });
        }
    }

    onDateChange(ev) {
        this.state.date = ev.target.value;
        this.state.date_filter_type = "specific";
    }

    applyDatePreset(type) {
        const now = new Date();
        let targetDate = new Date();

        if (type === "today") {
            targetDate = now;
        } else if (type === "end_month") {
            targetDate = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        } else if (type === "end_quarter") {
            const quarter = Math.floor(now.getMonth() / 3);
            targetDate = new Date(now.getFullYear(), (quarter + 1) * 3, 0);
        } else if (type === "end_year") {
            targetDate = new Date(now.getFullYear(), 12, 0);
        }

        this.state.date = targetDate.toISOString().slice(0, 10);
        this.state.date_filter_type = type;
        this.loadData();
    }

    onTargetMoveChange(ev) {
        this.state.target_move = ev.target.value;
    }

    onCompanyChange(ev) {
        this.state.company_id = ev.target.value ? parseInt(ev.target.value) : null;
    }

    async loadData() {
        this.state.loading = true;
        this.state.has_data = false;
        try {
            const result = await this.rpc("/dynamic_balance_sheet_report/data", {
                date_from: false,
                date_to: this.state.date,
                target_move: this.state.target_move,
                company_ids: this.state.company_id,
                show_unposted: this.state.show_unposted,
                show_zero: this.state.show_zero,
            });
            this.state.report_data = result;
            this.state.has_data = true;
        } catch (error) {
            console.error('Failed to generate report:', error);
            this.notification.add('Failed to generate report', { type: 'danger' });
        }
        this.state.loading = false;
    }

    toggleDetail(key) {
        if (this.state.expandedDetails.has(key)) {
            this.state.expandedDetails.delete(key);
        } else {
            this.state.expandedDetails.add(key);
        }
    }

    get formattedDate() {
        if (!this.state.date) return "";
        const [year, month, day] = this.state.date.split("-");
        return `${month}/${day}/${year}`;
    }

    async exportExcel() {
        const url = `/dynamic_balance_sheet_report/export/excel?` +
            `date_to=${this.state.date}` +
            `&target_move=${this.state.target_move}` +
            `&company_id=${this.state.company_id || ''}`;
        window.location = url;
    }

    get hasData() {
        return this.state.has_data;
    }
}

BalanceSheetReport.template = "dynamic_balance_sheet_report.BalanceSheetReportTemplate";
BalanceSheetReport.components = { BalanceSheetComponent };
BalanceSheetReport.props = ["action", "actionId", "className"];

const actionRegistry = registry.category("actions");
actionRegistry.add("dynamic_balance_sheet_report.balance_sheet_report", BalanceSheetReport);
