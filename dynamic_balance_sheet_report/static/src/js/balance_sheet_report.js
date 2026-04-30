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

        this.state = useState({
            loading: false,
            date_from: new Date().toISOString().slice(0, 10),
            date_to: new Date().toISOString().slice(0, 10),
            target_move: "posted",
            company_id: null,
            companies: [],
            account_range_type: "all",
            show_unposted: false,
            show_zero: false,
            report_data: null,
            has_data: false,
            expandedDetails: new Set(),
        });

        onWillStart(async () => {
            await this.loadInitialData();
            this.state.date_from = new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10);
            this.state.date_to = new Date().toISOString().slice(0, 10);
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

    async loadData() {
        this.state.loading = true;
        this.state.has_data = false;
        try {
            const result = await this.rpc("/dynamic_balance_sheet_report/data", {
                date_from: this.state.date_from,
                date_to: this.state.date_to,
                target_move: this.state.target_move,
                company_ids: this.state.company_id,
                account_range_type: this.state.account_range_type,
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

    async exportExcel() {
        const url = `/dynamic_balance_sheet_report/export/excel?` +
            `date_from=${this.state.date_from}` +
            `&date_to=${this.state.date_to}` +
            `&target_move=${this.state.target_move}` +
            `&company_id=${this.state.company_id || ''}` +
            `&account_range_type=${this.state.account_range_type}` +
            `&show_unposted=${this.state.show_unposted}` +
            `&show_zero=${this.state.show_zero}`;
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
