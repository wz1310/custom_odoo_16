/** @odoo-module **/

import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

const { Component, onPatched, onWillStart, useState, markup } = owl;

const REPORT_STATE_KEY = "sale_sales_report_example.ui_state";

export class SalesReportExampleClientAction extends Component {
    setup() {
        this.action = useService("action");
        this.rpc = useService("rpc");
        this.chart = null;
        this.chartLibraryPromise = null;
        this.chartRenderToken = 0;
        this.pendingRestore = false;
        this.state = useState({
            html_content: "",
            loading: true,
            groupby: ["customer"],
            date_from: "",
            date_to: "",
            search_term: "",
            view_mode: "list",
            chart_granularity: "month",
        });

        this.loadSavedState();

        onWillStart(async () => {
            await this.fetchReportHtml();
        });

        onPatched(() => {
            if (this.pendingRestore) {
                this.restoreViewState();
                this.pendingRestore = false;
            }
            this.applyViewClasses();
            if (this.state.view_mode === "graph") {
                this.renderChartView();
            } else {
                this.destroyChart();
            }
        });
    }

    loadSavedState() {
        const savedState = window.sessionStorage.getItem(REPORT_STATE_KEY);
        if (!savedState) {
            return;
        }
        try {
            const parsedState = JSON.parse(savedState);
            this.state.groupby = Array.isArray(parsedState.groupby) && parsedState.groupby.length
                ? parsedState.groupby
                : ["customer"];
            this.state.date_from = parsedState.date_from || "";
            this.state.date_to = parsedState.date_to || "";
            this.state.search_term = parsedState.search_term || "";
            this.state.view_mode = parsedState.view_mode || "list";
            this.state.chart_granularity = parsedState.chart_granularity || "month";
        } catch {
            window.sessionStorage.removeItem(REPORT_STATE_KEY);
        }
    }

    getCurrentViewState() {
        const expandedRows = [...document.querySelectorAll(".row-clickable.is-expanded")]
            .map((row) => row.getAttribute("data-id"))
            .filter(Boolean);
        const tableWrap = document.querySelector(".o_sales_report_example .table-wrap");
        return {
            groupby: [...this.state.groupby],
            date_from: this.state.date_from,
            date_to: this.state.date_to,
            search_term: this.state.search_term,
            view_mode: this.state.view_mode,
            chart_granularity: this.state.chart_granularity,
            expanded_rows: expandedRows,
            scroll_top: tableWrap ? tableWrap.scrollTop : 0,
        };
    }

    saveViewState() {
        window.sessionStorage.setItem(REPORT_STATE_KEY, JSON.stringify(this.getCurrentViewState()));
    }

    saveQueryState() {
        window.sessionStorage.setItem(REPORT_STATE_KEY, JSON.stringify({
            groupby: [...this.state.groupby],
            date_from: this.state.date_from,
            date_to: this.state.date_to,
            search_term: this.state.search_term,
            view_mode: this.state.view_mode,
            chart_granularity: this.state.chart_granularity,
            expanded_rows: [],
            scroll_top: 0,
        }));
    }

    setMobileMenu(open) {
        const root = document.querySelector(".o_sales_report_example");
        if (!root) {
            return;
        }
        root.classList.toggle("mobile-menu-open", open);
    }

    ensureChartLibrary() {
        if (window.Chart) {
            return Promise.resolve();
        }
        if (!this.chartLibraryPromise) {
            this.chartLibraryPromise = loadJS("/web/static/lib/Chart/Chart.js");
        }
        return this.chartLibraryPromise;
    }

    destroyChart() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    applyViewClasses() {
        const root = document.querySelector(".o_sales_report_example");
        if (!root) {
            return;
        }
        root.classList.toggle("view-mode-graph", this.state.view_mode === "graph");
        root.querySelectorAll(".js_view_mode").forEach((button) => {
            button.classList.toggle("is-active", button.getAttribute("data-view-mode") === this.state.view_mode);
        });
        root.querySelectorAll(".js_chart_granularity").forEach((button) => {
            button.classList.toggle(
                "is-active",
                button.getAttribute("data-chart-granularity") === this.state.chart_granularity
            );
        });
    }

    updateChartSummary(summary = {}) {
        const root = document.querySelector(".o_sales_report_example");
        if (!root) {
            return;
        }
        const formatMoney = (value) => Number(value || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        const formatPercent = (value) => `${Number(value || 0).toFixed(2)}%`;

        const setText = (selector, value) => {
            const el = root.querySelector(selector);
            if (el) {
                el.textContent = value;
            }
        };

        setText(".js_chart_total_sales", formatMoney(summary.total_sales));
        setText(".js_chart_avg_ratio", formatPercent(summary.avg_ratio));
        setText(".js_chart_best_ratio", formatPercent(summary.best_ratio));
        setText(".js_chart_best_sales", formatMoney(summary.best_sales));
    }

    openChartBucket(bucket) {
        if (!bucket) {
            return;
        }
        this.state.date_from = bucket.date_from || "";
        this.state.date_to = bucket.date_to || "";
        this.state.view_mode = "list";
        this.saveQueryState();
        this.fetchReportHtml();
    }

    restoreViewState() {
        const savedState = window.sessionStorage.getItem(REPORT_STATE_KEY);
        if (!savedState) {
            return;
        }
        try {
            const parsedState = JSON.parse(savedState);
            const expandedRows = parsedState.expanded_rows || [];
            expandedRows.forEach((rowId) => {
                const row = document.querySelector(`.row-clickable[data-id="${rowId}"]`);
                if (!row) {
                    return;
                }
                row.classList.add("is-expanded");
                document.querySelectorAll(`.child-of-${rowId}`).forEach((child) => {
                    child.style.display = "table-row";
                });
            });
            const tableWrap = document.querySelector(".o_sales_report_example .table-wrap");
            if (tableWrap && Number.isFinite(parsedState.scroll_top)) {
                tableWrap.scrollTop = parsedState.scroll_top;
            }
        } catch {
            window.sessionStorage.removeItem(REPORT_STATE_KEY);
        }
    }

    async fetchReportHtml() {
        this.state.loading = true;
        try {
            const html = await this.rpc("/sales_report_example/report_html", {
                groupby: [...this.state.groupby],
                date_from: this.state.date_from,
                date_to: this.state.date_to,
                search_term: this.state.search_term,
            });
            this.state.html_content = markup(html);
            this.pendingRestore = true;
        } finally {
            this.state.loading = false;
        }
    }

    async renderChartView() {
        const root = document.querySelector(".o_sales_report_example");
        if (!root || this.state.view_mode !== "graph") {
            this.destroyChart();
            return;
        }

        const renderToken = ++this.chartRenderToken;
        await this.ensureChartLibrary();
        if (renderToken !== this.chartRenderToken || this.state.view_mode !== "graph") {
            return;
        }

        const payload = await this.rpc("/sales_report_example/chart_data", {
            granularity: this.state.chart_granularity,
            date_from: this.state.date_from,
            date_to: this.state.date_to,
            search_term: this.state.search_term,
        });
        if (renderToken !== this.chartRenderToken || this.state.view_mode !== "graph") {
            return;
        }

        this.updateChartSummary(payload.summary || {});

        const emptyState = root.querySelector(".js_chart_empty");
        const canvas = root.querySelector(".js_sales_chart_canvas");
        if (!canvas) {
            return;
        }

        this.destroyChart();

        if (!payload.labels || !payload.labels.length) {
            if (emptyState) {
                emptyState.classList.add("is-visible");
            }
            return;
        }

        if (emptyState) {
            emptyState.classList.remove("is-visible");
        }

        const context = canvas.getContext("2d");
        this.chart = new window.Chart(context, {
            type: "bar",
            data: {
                labels: payload.labels,
                datasets: [
                    {
                        label: "Sales",
                        data: payload.sales,
                        backgroundColor: "rgba(15, 23, 42, 0.88)",
                        borderRadius: 6,
                        maxBarThickness: 30,
                    },
                    {
                        label: "Cost",
                        data: payload.cost,
                        backgroundColor: "rgba(148, 163, 184, 0.68)",
                        borderRadius: 6,
                        maxBarThickness: 30,
                    },
                    {
                        label: "Margin Ratio %",
                        data: payload.ratio,
                        type: "line",
                        yAxisID: "ratio",
                        borderColor: "#0f766e",
                        backgroundColor: "rgba(15, 118, 110, 0.16)",
                        borderWidth: 2,
                        fill: false,
                        tension: 0.35,
                        pointRadius: 3,
                        pointHoverRadius: 4,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                onClick: (_event, elements) => {
                    if (!elements || !elements.length) {
                        return;
                    }
                    const index = elements[0]._index;
                    if (index === undefined) {
                        return;
                    }
                    this.openChartBucket(payload.buckets && payload.buckets[index]);
                },
                legend: {
                    position: "bottom",
                    labels: {
                        boxWidth: 10,
                        fontColor: "#475569",
                    },
                },
                tooltips: {
                    mode: "index",
                    intersect: false,
                },
                scales: {
                    xAxes: [{
                        gridLines: {
                            display: false,
                        },
                        ticks: {
                            fontColor: "#64748b",
                        },
                    }],
                    yAxes: [
                        {
                            ticks: {
                                beginAtZero: true,
                                fontColor: "#64748b",
                                callback: (value) => Number(value).toLocaleString(),
                            },
                            gridLines: {
                                color: "rgba(226, 232, 240, 0.85)",
                            },
                        },
                        {
                            id: "ratio",
                            position: "right",
                            ticks: {
                                beginAtZero: true,
                                fontColor: "#0f766e",
                                callback: (value) => `${value}%`,
                            },
                            gridLines: {
                                drawOnChartArea: false,
                            },
                        },
                    ],
                },
            },
        });
    }

    handleMainClick(ev) {
        const target = ev.target;

        if (target.closest(".js_export_excel")) {
            this.setMobileMenu(false);
            this.exportToExcel();
            return;
        }

        const viewModeButton = target.closest(".js_view_mode");
        if (viewModeButton) {
            const mode = viewModeButton.getAttribute("data-view-mode");
            if (mode && mode !== this.state.view_mode) {
                this.state.view_mode = mode;
                this.saveViewState();
                this.applyViewClasses();
                if (mode === "graph") {
                    this.renderChartView();
                } else {
                    this.destroyChart();
                }
            }
            this.setMobileMenu(false);
            return;
        }

        const chartGranularityButton = target.closest(".js_chart_granularity");
        if (chartGranularityButton) {
            const granularity = chartGranularityButton.getAttribute("data-chart-granularity");
            if (granularity && granularity !== this.state.chart_granularity) {
                this.state.chart_granularity = granularity;
                this.saveViewState();
                this.applyViewClasses();
                this.renderChartView();
            }
            return;
        }

        if (target.closest(".js_mobile_menu_toggle")) {
            this.setMobileMenu(true);
            return;
        }

        if (target.closest(".js_mobile_menu_close")) {
            this.setMobileMenu(false);
            return;
        }

        const orderRow = target.closest(".js-open-order");
        if (orderRow) {
            const orderId = orderRow.getAttribute("data-order-id");
            if (orderId) {
                this.setMobileMenu(false);
                this.saveViewState();
                this.action.doAction({
                    type: "ir.actions.act_window",
                    name: _t("Sales Order"),
                    res_model: "sale.order",
                    res_id: parseInt(orderId, 10),
                    views: [[false, "form"]],
                    target: "current",
                });
            }
            return;
        }

        const groupButton = target.closest(".js_toggle_groupby");
        if (groupButton) {
            ev.preventDefault();
            const value = groupButton.getAttribute("data-groupby");
            if (value) {
                const current = [...this.state.groupby];
                this.state.groupby = current.includes(value)
                    ? current.filter((item) => item !== value)
                    : [...current, value];
                this.setMobileMenu(false);
                this.saveQueryState();
                this.fetchReportHtml();
            }
            return;
        }

        if (target.tagName === "INPUT" && (target.name === "date_from" || target.name === "date_to")) {
            target.onchange = (event) => {
                this.state[event.target.name] = event.target.value;
                this.setMobileMenu(false);
                this.saveQueryState();
                this.fetchReportHtml();
            };
            return;
        }

        if (target.tagName === "INPUT" && target.name === "search_term") {
            target.onchange = (event) => {
                this.state.search_term = event.target.value.trim();
                this.setMobileMenu(false);
                this.saveQueryState();
                this.fetchReportHtml();
            };
            return;
        }

        const row = target.closest(".row-clickable");
        if (row) {
            const id = row.getAttribute("data-id");
            if (!id) {
                return;
            }
            if (row.classList.contains("is-expanded")) {
                row.classList.remove("is-expanded");
                this.hideChildren(id);
            } else {
                row.classList.add("is-expanded");
                document.querySelectorAll(`.child-of-${id}`).forEach((child) => {
                    child.style.display = "table-row";
                });
            }
            this.saveViewState();
        }
    }

    hideChildren(parentId) {
        document.querySelectorAll(`.child-of-${parentId}`).forEach((child) => {
            child.style.display = "none";
            child.classList.remove("is-expanded");
            const childId = child.getAttribute("data-id");
            if (childId) {
                this.hideChildren(childId);
            }
        });
    }

    exportToExcel() {
        this.saveViewState();
        const groupby = JSON.stringify(this.state.groupby);
        const params = new URLSearchParams({
            groupby,
            date_from: this.state.date_from || "",
            date_to: this.state.date_to || "",
            search_term: this.state.search_term || "",
        });
        window.location.href = `/sales_report_example/export_excel?${params.toString()}`;
    }
}

SalesReportExampleClientAction.template = "sale_sales_report_example.sales_report_client_template";
registry.category("actions").add("sale_sales_report_example.sales_client_action", SalesReportExampleClientAction);
