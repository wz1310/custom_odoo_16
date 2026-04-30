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
            date_from: new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10),
            date_filter_type: "today",
            target_move: "posted",
            company_id: null,
            companies: [],
            journals: [],
            selected_journal_ids: [],
            journal_dropdown_open: false,
            journal_search: "",
            report_data: null,
            has_data: false,
            expandedDetails: new Set(),
        });

        onWillStart(async () => {
            await this.loadInitialData();
            this.state.date = new Date().toISOString().slice(0, 10);
            this.state.date_from = new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10);
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

            // Load journals
            await this.loadJournals();
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.notification.add('Failed to load initial data', { type: 'danger' });
        }
    }

    async loadJournals() {
        try {
            const domain = this.state.company_id ? [['company_id', '=', this.state.company_id]] : [];
            const journals = await this.rpc("/web/dataset/call_kw", {
                model: "account.journal",
                method: "search_read",
                args: [domain, ["id", "name", "type"]],
                kwargs: { order: "name asc" },
            });
            this.state.journals = journals;
        } catch (error) {
            console.error('Failed to load journals:', error);
        }
    }

    onDateChange(ev) {
        this.state.date = ev.target.value;
        this.state.date_filter_type = "specific";
    }

    onDateFromChange(ev) {
        this.state.date_from = ev.target.value;
        this.state.date_filter_type = "specific";
    }

    applyDatePreset(type) {
        const now = new Date();
        let targetDate = new Date();
        let fromDate = new Date(now.getFullYear(), 0, 1); // default: start of year

        if (type === "today") {
            targetDate = now;
            fromDate = new Date(now.getFullYear(), 0, 1);
        } else if (type === "end_month") {
            targetDate = new Date(now.getFullYear(), now.getMonth() + 1, 0);
            fromDate = new Date(now.getFullYear(), now.getMonth(), 1);
        } else if (type === "end_quarter") {
            const quarter = Math.floor(now.getMonth() / 3);
            targetDate = new Date(now.getFullYear(), (quarter + 1) * 3, 0);
            fromDate = new Date(now.getFullYear(), quarter * 3, 1);
        } else if (type === "end_year") {
            targetDate = new Date(now.getFullYear(), 12, 0);
            fromDate = new Date(now.getFullYear(), 0, 1);
        }

        this.state.date = targetDate.toISOString().slice(0, 10);
        this.state.date_from = fromDate.toISOString().slice(0, 10);
        this.state.date_filter_type = type;
        this.loadData();
    }

    onTargetMoveChange(ev) {
        this.state.target_move = ev.target.value;
    }

    onCompanyChange(ev) {
        this.state.company_id = ev.target.value ? parseInt(ev.target.value) : null;
        // Reload journals when company changes
        this.state.selected_journal_ids = [];
        this.loadJournals();
    }

    toggleJournal(journalId) {
        const idx = this.state.selected_journal_ids.indexOf(journalId);
        if (idx === -1) {
            this.state.selected_journal_ids = [...this.state.selected_journal_ids, journalId];
        } else {
            this.state.selected_journal_ids = this.state.selected_journal_ids.filter(id => id !== journalId);
        }
    }

    removeJournal(journalId) {
        this.state.selected_journal_ids = this.state.selected_journal_ids.filter(id => id !== journalId);
    }

    isJournalSelected(journalId) {
        return this.state.selected_journal_ids.includes(journalId);
    }

    selectAllJournals() {
        this.state.selected_journal_ids = this.state.journals.map(j => j.id);
    }

    clearAllJournals() {
        this.state.selected_journal_ids = [];
    }

    get selectedJournals() {
        return this.state.journals.filter(j => this.state.selected_journal_ids.includes(j.id));
    }

    get filteredJournals() {
        const q = (this.state.journal_search || "").toLowerCase().trim();
        if (!q) return this.state.journals;
        return this.state.journals.filter(j => j.name.toLowerCase().includes(q));
    }

    async loadData() {
        this.state.loading = true;
        this.state.has_data = false;
        try {
            const result = await this.rpc("/dynamic_balance_sheet_report/data", {
                date_from: this.state.date_from,
                date_to: this.state.date,
                target_move: this.state.target_move,
                company_ids: this.state.company_id,
                journal_ids: this.state.selected_journal_ids.length > 0 ? this.state.selected_journal_ids : false,
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

    get formattedDateFrom() {
        if (!this.state.date_from) return "";
        const [year, month, day] = this.state.date_from.split("-");
        return `${month}/${day}/${year}`;
    }

    async exportExcel() {
        const journalParam = this.state.selected_journal_ids.length > 0
            ? `&journal_ids=${this.state.selected_journal_ids.join(',')}`
            : '';
        const url = `/dynamic_balance_sheet_report/export/excel?` +
            `date_from=${this.state.date_from}` +
            `&date_to=${this.state.date}` +
            `&target_move=${this.state.target_move}` +
            `&company_id=${this.state.company_id || ''}` +
            journalParam;
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
