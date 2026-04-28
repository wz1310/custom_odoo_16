/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";

export class SalesTable extends Component {
    setup() {
        this.state = useState({
            searchQuery: "",
            expandedGroups: {},
            expandedRows: {},
        });
    }



    _toggleGroup(path) {
        this.state.expandedGroups[path] = !this.state.expandedGroups[path];
    }





    setLines(lines) {
        this.state.lines = lines;
    }

    setGroups(groups) {
        this.state.activeGroups = groups;
    }

    sortBy(column) {
        if (this.state.sortBy === column) {
            this.state.sortDirection = this.state.sortDirection === "asc" ? "desc" : "asc";
        } else {
            this.state.sortBy = column;
            this.state.sortDirection = "asc";
        }
        this._sortLines();
    }

    _sortLines() {
        const { sortBy, sortDirection } = this.state;
        this.state.lines.sort((a, b) => {
            let aVal = a[sortBy];
            let bVal = b[sortBy];

            if (typeof aVal === "string") aVal = aVal.toLowerCase();
            if (typeof bVal === "string") bVal = bVal.toLowerCase();

            if (aVal < bVal) return sortDirection === "asc" ? -1 : 1;
            if (aVal > bVal) return sortDirection === "asc" ? 1 : -1;
            return 0;
        });
    }

    search(query) {
        this.state.searchQuery = query;
        this._filterLines();
    }

    _filterLines() {
        const query = this.state.searchQuery.toLowerCase();
        const rows = document.querySelectorAll(".srm-row-detail");
        rows.forEach((row) => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(query) ? "table-row" : "none";
        });
    }

    goToPage(page) {
        this.state.currentPage = page;
    }

    formatCurrency(value) {
        return new Intl.NumberFormat("id-ID", {
            style: "currency",
            currency: "IDR",
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(value || 0);
    }

    formatNumber(value) {
        return new Intl.NumberFormat("id-ID").format(value || 0);
    }
}

SalesTable.template = "sales_analytics_dashboard.table_template";
