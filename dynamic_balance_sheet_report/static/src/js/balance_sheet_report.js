/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

class BalanceSheetComponent extends Component {
    static template = "dynamic_balance_sheet_report.BalanceSheetComponentTemplate";
    static props = ["reportData", "expandedDetails", "toggleDetail"];

    setup() {
        // Map of accCode -> number of visible lines (default 80)
        this.visibleLines = useState({});
    }

    static PAGE_SIZE = 80;

    getVisibleCount(accCode) {
        return this.visibleLines[accCode] || BalanceSheetComponent.PAGE_SIZE;
    }

    loadMore(accCode, totalLines) {
        const current = this.getVisibleCount(accCode);
        this.visibleLines[accCode] = Math.min(current + BalanceSheetComponent.PAGE_SIZE, totalLines);
    }

    getVisibleLines(acc) {
        const count = this.getVisibleCount(acc.code);
        return (acc.lines || []).slice(0, count);
    }

    hasMore(acc) {
        return (acc.lines || []).length > this.getVisibleCount(acc.code);
    }

    remainingCount(acc) {
        return (acc.lines || []).length - this.getVisibleCount(acc.code);
    }

    formatAmount(amount) {
        if (amount === null || amount === undefined) return "0.00";
        return Number(amount).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    formatDate(dateStr) {
        if (!dateStr) return "";
        const [year, month, day] = String(dateStr).slice(0, 10).split("-");
        return `${day}/${month}/${year}`;
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

            // Company multi-select
            companies: [],
            selected_company_ids: [],
            company_search: "",

            // Journal multi-select
            journals: [],
            selected_journal_ids: [],
            journal_search: "",

            report_data: null,
            has_data: false,
            expandedDetails: new Set(),
            show_export_modal: false,
        });

        onWillStart(async () => {
            await this.loadInitialData();
            this.state.date = new Date().toISOString().slice(0, 10);
            this.state.date_from = new Date(new Date().getFullYear(), 0, 1).toISOString().slice(0, 10);
        });
    }

    // ── Initial load ──────────────────────────────────────────────────────────

    async loadInitialData() {
        try {
            const companies = await this.rpc("/web/dataset/call_kw", {
                model: "res.company",
                method: "search_read",
                args: [[], ["id", "name"]],
                kwargs: { order: "name asc" },
            });
            this.state.companies = companies;

            // Pre-select current user's company
            const currentCompanyId = this.companyService.currentCompany.id;
            if (currentCompanyId) {
                this.state.selected_company_ids = [currentCompanyId];
            }

            await this.loadJournals();
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.notification.add('Failed to load initial data', { type: 'danger' });
        }
    }

    async loadJournals() {
        try {
            const domain = this.state.selected_company_ids.length > 0
                ? [['company_id', 'in', this.state.selected_company_ids]]
                : [];
            const journals = await this.rpc("/web/dataset/call_kw", {
                model: "account.journal",
                method: "search_read",
                args: [domain, ["id", "name", "type"]],
                kwargs: { order: "name asc" },
            });
            this.state.journals = journals;
            // Remove selected journals that no longer belong to selected companies
            const validIds = journals.map(j => j.id);
            this.state.selected_journal_ids = this.state.selected_journal_ids.filter(id => validIds.includes(id));
        } catch (error) {
            console.error('Failed to load journals:', error);
        }
    }

    // ── Date helpers ──────────────────────────────────────────────────────────

    _toDisplay(isoDate) {
        if (!isoDate) return "";
        const [year, month, day] = isoDate.split("-");
        return `${day}/${month}/${year}`;
    }

    get formattedDate() { return this._toDisplay(this.state.date); }
    get formattedDateFrom() { return this._toDisplay(this.state.date_from); }

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
        let fromDate = new Date(now.getFullYear(), 0, 1);

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

    // ── Target moves ──────────────────────────────────────────────────────────

    onTargetMoveChange(ev) {
        this.state.target_move = ev.target.value;
    }

    // ── Company multi-select ──────────────────────────────────────────────────

    toggleCompany(companyId) {
        const idx = this.state.selected_company_ids.indexOf(companyId);
        if (idx === -1) {
            this.state.selected_company_ids = [...this.state.selected_company_ids, companyId];
        } else {
            this.state.selected_company_ids = this.state.selected_company_ids.filter(id => id !== companyId);
        }
        this.loadJournals();
    }

    removeCompany(companyId) {
        this.state.selected_company_ids = this.state.selected_company_ids.filter(id => id !== companyId);
        this.loadJournals();
    }

    isCompanySelected(companyId) {
        return this.state.selected_company_ids.includes(companyId);
    }

    selectAllCompanies() {
        this.state.selected_company_ids = this.state.companies.map(c => c.id);
        this.loadJournals();
    }

    clearAllCompanies() {
        this.state.selected_company_ids = [];
        this.loadJournals();
    }

    get selectedCompanies() {
        return this.state.companies.filter(c => this.state.selected_company_ids.includes(c.id));
    }

    get filteredCompanies() {
        const q = (this.state.company_search || "").toLowerCase().trim();
        if (!q) return this.state.companies;
        return this.state.companies.filter(c => c.name.toLowerCase().includes(q));
    }

    // ── Journal multi-select ──────────────────────────────────────────────────

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

    // ── Load report data ──────────────────────────────────────────────────────

    async loadData() {
        this.state.loading = true;
        this.state.has_data = false;
        try {
            const result = await this.rpc("/dynamic_balance_sheet_report/data", {
                date_from: this.state.date_from,
                date_to: this.state.date,
                target_move: this.state.target_move,
                company_ids: this.state.selected_company_ids.length > 0 ? this.state.selected_company_ids : false,
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

    // ── Export ────────────────────────────────────────────────────────────────

    async exportExcel() {
        this.state.show_export_modal = true;
    }

    doExport(withDetail) {
        this.state.show_export_modal = false;
        const journalParam = this.state.selected_journal_ids.length > 0
            ? `&journal_ids=${this.state.selected_journal_ids.join(',')}`
            : '';
        const companyParam = this.state.selected_company_ids.length > 0
            ? `&company_ids=${this.state.selected_company_ids.join(',')}`
            : '';
        const url = `/dynamic_balance_sheet_report/export/excel?` +
            `date_from=${this.state.date_from}` +
            `&date_to=${this.state.date}` +
            `&target_move=${this.state.target_move}` +
            `&with_detail=${withDetail ? '1' : '0'}` +
            companyParam +
            journalParam;
        window.location = url;
    }

    cancelExport() {
        this.state.show_export_modal = false;
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
