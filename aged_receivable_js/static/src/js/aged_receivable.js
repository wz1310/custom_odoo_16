/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class AgedReceivableReport extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.companyService = useService("company");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            partners: [],
            totals: {},
            currency: "",
            currencySymbol: "",
            currencyPosition: "after",
            expandedPartners: new Set(),
            today: "",
            selectedDate: new Date().toISOString().split('T')[0],
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const companyIds = this.companyService.allowedCompanyIds;
            const data = await this.rpc("/aged_receivable/data", {
                company_ids: companyIds,
                date_to: this.state.selectedDate,
            });
            this.state.partners = data.partners;
            this.state.totals = data.totals;
            this.state.currency = data.currency;
            this.state.currencySymbol = data.currency_symbol;
            this.state.currencyPosition = data.currency_position;
            this.state.today = data.today;
        } catch (error) {
            this.notification.add("Gagal memuat data report", { type: "danger" });
            console.error("Aged Receivable RPC Error:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async onDateChange(ev) {
        this.state.selectedDate = ev.target.value;
        await this.loadData();
    }

    togglePartner(partnerName) {
        if (this.state.expandedPartners.has(partnerName)) {
            this.state.expandedPartners.delete(partnerName);
        } else {
            this.state.expandedPartners.add(partnerName);
        }
    }

    openInvoice(moveId) {
        const url = `/web#id=${moveId}&model=account.move&view_type=form`;
        window.open(url, "_blank");
    }

    async registerPayment(moveId) {
        try {
            await this.action.doAction({
                name: "Register Payment",
                type: "ir.actions.act_window",
                res_model: "account.payment.register",
                views: [[false, "form"]],
                target: "new",
                context: {
                    active_model: "account.move",
                    active_ids: [moveId],
                },
            }, {
                onClose: async () => {
                    await this.loadData();
                },
            });
        } catch (error) {
            this.notification.add("Gagal membuka register payment", { type: "danger" });
        }
    }

    exportToExcel() {
        const companyIds = this.companyService.allowedCompanyIds.join(',');
        const url = `/aged_receivable/export?date_to=${this.state.selectedDate}&company_ids=${companyIds}`;
        window.location.href = url;
    }

    formatCurrency(amount) {
        const symbol = this.state.currencySymbol || "";
        const formatted = new Intl.NumberFormat("id-ID", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(amount);

        if (this.state.currencyPosition === "before") {
            return `${symbol} ${formatted}`;
        } else {
            return `${formatted} ${symbol}`;
        }
    }

    getBucketLabel(bucket) {
        const labels = {
            'current': 'Not Due',
            'b1_30': '1 - 30 Days',
            'b31_60': '31 - 60 Days',
            'b61_90': '61 - 90 Days',
            'b91_120': '91 - 120 Days',
            'older': 'Older'
        };
        return labels[bucket] || bucket;
    }
}

AgedReceivableReport.template = "aged_receivable_js.report_template";
registry.category("actions").add("aged_receivable_js.report", AgedReceivableReport);
