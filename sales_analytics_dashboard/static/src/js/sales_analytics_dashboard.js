/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, onMounted, onWillUnmount, markup } from "@odoo/owl";
import { SalesChart } from "@sales_analytics_dashboard/js/sales_chart_component";
import { SalesKPI } from "@sales_analytics_dashboard/js/sales_kpi_component";
import { SalesTable } from "@sales_analytics_dashboard/js/sales_table_component";

export class SalesAnalyticsDashboard extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.action = useService("action");
        this.companyService = useService("company");

        this.state = useState({
            loading: true,
            initialized: false,
            analyticsData: {},
            allLines: [],
            activeGroups: ["customer"],
            dateFrom: "",
            dateTo: "",
            kpi: {
                total_revenue: 0,
                total_orders: 0,
                total_customers: 0,
                total_products: 0,
                total_qty: 0,
                avg_order_value: 0,
                total_margin: 0,
            },
            topCustomers: [],
            topProducts: [],
            topCategories: [],
            trends: {},
            periodLabel: "",
            isDarkMode: this._detectDarkMode(),
            refreshInterval: null,
            lastUpdate: null,
            isSidebarOpen: false,
            searchText: "",
        });

        // Auto-refresh timer
        this.autoRefreshInterval = null;

        onWillStart(async () => {
            await this.loadData();
            this._startAutoRefresh();
        });

        onMounted(() => {
            this._setupEventListeners();
            this._observeResize();
        });

        onWillUnmount(() => {
            this._cleanup();
        });
    }

    _detectDarkMode() {
        if (typeof window !== "undefined") {
            return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
        }
        return false;
    }

    _setupEventListeners() {
        // Dark mode toggle listener
        if (typeof window !== "undefined") {
            window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
                this.state.isDarkMode = e.matches;
                this._updateTheme();
            });

            // Keyboard shortcuts
            document.addEventListener("keydown", this._handleKeyboardShortcuts.bind(this));
        }
    }

    _observeResize() {
        if (typeof window !== "undefined") {
            this.resizeObserver = new ResizeObserver(() => {
                this._handleResize();
            });
        }
    }

    _handleKeyboardShortcuts(e) {
        // Ctrl/Cmd + F to focus filter
        if ((e.ctrlKey || e.metaKey) && e.key === "f") {
            e.preventDefault();
            const dateInput = document.querySelector("[name='date_from']");
            if (dateInput) dateInput.focus();
        }

        // Ctrl/Cmd + R to refresh
        if ((e.ctrlKey || e.metaKey) && e.key === "r") {
            e.preventDefault();
            this.loadData();
        }

        // Escape to close dropdowns
        if (e.key === "Escape") {
            this._closeAllDropdowns();
        }
    }

    _handleResize() {
        // Handle responsive behavior
        const width = window.innerWidth;
        const table = document.querySelector(".sales-table-container");
        if (table) {
            if (width < 768) {
                table.classList.add("mobile-view");
            } else {
                table.classList.remove("mobile-view");
            }
        }
    }

    _updateTheme() {
        const root = document.documentElement;
        if (this.state.isDarkMode) {
            root.setAttribute("data-theme", "dark");
        } else {
            root.setAttribute("data-theme", "light");
        }
    }

    _startAutoRefresh() {
        // Auto-refresh every 5 minutes
        this.autoRefreshInterval = setInterval(() => {
            this.loadData();
        }, 5 * 60 * 1000);
    }

    _cleanup() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        document.removeEventListener("keydown", this._handleKeyboardShortcuts);
    }

    _closeAllDropdowns() {
        document.querySelectorAll(".srm-dropdown-menu.open").forEach((el) => {
            el.classList.remove("open");
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.rpc("/sales_analytics/data", {
                groupby: [...this.state.activeGroups],
                date_from: this.state.dateFrom,
                date_to: this.state.dateTo,
                company_ids: this.companyService.allowedCompanyIds,
            });

            // Update state directly from JSON response
            this.state.analyticsData = data.analytics_data || {};
            this.state.allLines = data.all_lines || [];
            this.state.kpi = data.kpi || {};
            this.state.topCustomers = data.top_customers || [];
            this.state.topProducts = data.top_products || [];
            this.state.topCategories = data.top_categories || [];
            this.state.trends = data.trends || {};
            this.state.periodLabel = data.period_label || "";
            this.state.lastUpdate = new Date();
            this.state.initialized = true;
        } catch (e) {
            console.error("SalesAnalytics RPC error:", e);
            this.notification.add("Gagal memuat data analitik", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    search(query) {
        // Trigger search in SalesTable component if it exists
        const table = document.querySelector(".sales-table");
        if (table) {
            const rows = table.querySelectorAll(".sales-row-detail, .sales-row-group");
            const lowerQuery = query.toLowerCase();
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(lowerQuery) ? "" : "none";
            });
        }
    }



    async applyFilters() {
        // State is already updated via t-on-change in the template
        await this.loadData();
    }
 
    async clearFilters() {
        this.state.dateFrom = "";
        this.state.dateTo = "";
        this.state.activeGroups = ["customer"];
        this.state.searchText = "";
        
        // Explicitly clear DOM inputs as a fallback
        const searchInputs = document.querySelectorAll(".sales-header-search input");
        searchInputs.forEach((el, index) => {
            el.value = "";
        });
        
        // Reset search visibility in DOM
        this.search(""); 
        
        await this.loadData();
    }

    async addGroup(group) {
        if (!this.state.activeGroups.includes(group)) {
            this.state.activeGroups = [...this.state.activeGroups, group];
            await this.loadData();
        }
    }

    async removeGroup(group) {
        this.state.activeGroups = this.state.activeGroups.filter((g) => g !== group);
        await this.loadData();
    }

    async exportExcel() {
        const dateFrom = this.state.dateFrom;
        const dateTo = this.state.dateTo;
        const groupby = JSON.stringify(this.state.activeGroups);
        const companyIds = JSON.stringify(this.companyService.allowedCompanyIds);

        window.location.href = `/sales_analytics/export_excel?groupby=${encodeURIComponent(groupby)}&date_from=${dateFrom}&date_to=${dateTo}&company_ids=${encodeURIComponent(companyIds)}`;
    }

    toggleDropdown(e) {
        const dropdown = e.currentTarget.nextElementSibling;
        if (dropdown) {
            dropdown.classList.toggle("open");
        }
    }

    toggleDarkMode() {
        this.state.isDarkMode = !this.state.isDarkMode;
        this._updateTheme();
    }

    toggleSidebar() {
        this.state.isSidebarOpen = !this.state.isSidebarOpen;
    }

    getGroupLabel(group) {
        const labels = {
            customer: "👥 Pelanggan",
            product: "📦 Produk",
            salesperson: "👤 Sales",
            team: "🏷️ Tim",
            category: "🏷️ Kategori",
        };
        return labels[group] || group;
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

SalesAnalyticsDashboard.components = { SalesKPI, SalesTable };
SalesAnalyticsDashboard.template = "sales_analytics_dashboard.dashboard_template";
registry.category("actions").add("sales_analytics_dashboard.action", SalesAnalyticsDashboard);
